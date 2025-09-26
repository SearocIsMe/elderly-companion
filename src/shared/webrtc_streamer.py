#!/usr/bin/env python3
"""
WebRTC Streamer for Elderly Companion Robdog.

Provides real-time video streaming to family members during emergencies.
Integrates with MediaMTX and provides secure video access.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

import asyncio
import threading
import time
import json
import ssl
import uuid
from typing import Dict, List, Optional, Tuple, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import base64

# WebRTC and streaming imports
try:
    import cv2
    import numpy as np
    from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
    from aiortc.contrib.media import MediaPlayer, MediaRelay
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False
    print("Warning: WebRTC dependencies not available, using mock implementation")

# HTTP and WebSocket imports
import aiohttp
from aiohttp import web, WSMsgType
import websockets
import requests

# ROS2 message imports
from sensor_msgs.msg import Image, CompressedImage
from std_msgs.msg import Header, String, Bool
from elderly_companion.msg import EmergencyAlert, HealthStatus


class StreamState(Enum):
    """Video stream states."""
    IDLE = "idle"
    INITIALIZING = "initializing"
    STREAMING = "streaming"
    PAUSED = "paused"
    ERROR = "error"
    TERMINATED = "terminated"


class StreamQuality(Enum):
    """Video quality levels."""
    LOW = "low"          # 480p, 15fps, 500kbps
    MEDIUM = "medium"    # 720p, 30fps, 1Mbps
    HIGH = "high"        # 1080p, 30fps, 2Mbps
    EMERGENCY = "emergency"  # Optimized for emergency viewing


@dataclass
class StreamSession:
    """Video stream session data."""
    session_id: str
    family_member_id: str
    stream_type: str  # emergency, monitoring, communication
    quality: StreamQuality
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: int = 0
    emergency_context: bool = False
    access_token: str = ""
    stream_url: str = ""
    viewer_count: int = 0


@dataclass
class StreamConfig:
    """WebRTC stream configuration."""
    width: int
    height: int
    fps: int
    bitrate: int
    codec: str = "H264"


class WebRTCStreamerNode(Node):
    """
    WebRTC Streamer Node for elderly companion robot video streaming.
    
    Responsibilities:
    - Capture video from robot cameras
    - Stream video to family members via WebRTC
    - Provide emergency video access with secure authentication
    - Handle multiple concurrent viewers
    - Optimize streaming for network conditions
    - Integration with MediaMTX for stream routing
    """

    def __init__(self):
        super().__init__('webrtc_streamer_node')
        
        # Initialize parameters
        self.declare_parameters(
            namespace='',
            parameters=[
                ('webrtc.server_port', 8889),
                ('webrtc.signaling_port', 8890),
                ('webrtc.stun_server', 'stun:stun.l.google.com:19302'),
                ('webrtc.turn_server', ''),
                ('webrtc.turn_username', ''),
                ('webrtc.turn_password', ''),
                ('camera.device_index', 0),
                ('camera.width', 1280),
                ('camera.height', 720),
                ('camera.fps', 30),
                ('streaming.default_quality', 'medium'),
                ('streaming.emergency_quality', 'high'),
                ('streaming.max_concurrent_viewers', 5),
                ('security.enable_authentication', True),
                ('security.session_timeout_minutes', 30),
                ('integration.mediamtx_url', 'http://localhost:9997'),
                ('integration.mediamtx_enabled', True),
            ]
        )
        
        # Get parameters
        self.server_port = self.get_parameter('webrtc.server_port').value
        self.signaling_port = self.get_parameter('webrtc.signaling_port').value
        self.stun_server = self.get_parameter('webrtc.stun_server').value
        self.camera_device = self.get_parameter('camera.device_index').value
        self.camera_width = self.get_parameter('camera.width').value
        self.camera_height = self.get_parameter('camera.height').value
        self.camera_fps = self.get_parameter('camera.fps').value
        self.max_viewers = self.get_parameter('streaming.max_concurrent_viewers').value
        self.auth_enabled = self.get_parameter('security.enable_authentication').value
        self.mediamtx_enabled = self.get_parameter('integration.mediamtx_enabled').value
        self.mediamtx_url = self.get_parameter('integration.mediamtx_url').value
        
        # Stream management
        self.active_streams: Dict[str, StreamSession] = {}
        self.stream_configs = self.initialize_stream_configs()
        self.current_state = StreamState.IDLE
        
        # WebRTC components
        self.peer_connections: Dict[str, RTCPeerConnection] = {}
        self.media_relay = None
        self.video_track = None
        
        # Camera and video
        self.camera = None
        self.frame_queue = asyncio.Queue(maxsize=30)
        
        # Authentication
        self.access_tokens: Dict[str, Dict[str, Any]] = {}
        
        # QoS profiles
        default_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )
        
        # Subscribers
        self.emergency_alert_sub = self.create_subscription(
            EmergencyAlert,
            '/emergency/alert',
            self.handle_emergency_alert_callback,
            default_qos
        )
        
        self.camera_image_sub = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.camera_image_callback,
            sensor_qos
        )
        
        # Publishers
        self.stream_status_pub = self.create_publisher(
            String,
            '/webrtc/stream_status',
            default_qos
        )
        
        self.stream_access_pub = self.create_publisher(
            String,
            '/webrtc/stream_access',
            default_qos
        )
        
        # Initialize streaming components
        if WEBRTC_AVAILABLE:
            self.initialize_webrtc_components()
        else:
            self.get_logger().warning("WebRTC not available - using mock implementation")
        
        # Start HTTP server for WebRTC signaling
        self.start_signaling_server()
        
        self.get_logger().info("WebRTC Streamer Node initialized - Emergency video streaming ready")

    def initialize_stream_configs(self) -> Dict[StreamQuality, StreamConfig]:
        """Initialize video quality configurations."""
        return {
            StreamQuality.LOW: StreamConfig(
                width=640, height=480, fps=15, bitrate=500000
            ),
            StreamQuality.MEDIUM: StreamConfig(
                width=1280, height=720, fps=30, bitrate=1000000
            ),
            StreamQuality.HIGH: StreamConfig(
                width=1920, height=1080, fps=30, bitrate=2000000
            ),
            StreamQuality.EMERGENCY: StreamConfig(
                width=1280, height=720, fps=30, bitrate=1500000
            )
        }

    def initialize_webrtc_components(self):
        """Initialize WebRTC components."""
        try:
            if not WEBRTC_AVAILABLE:
                return
            
            # Initialize GStreamer
            Gst.init(None)
            
            # Initialize media relay
            self.media_relay = MediaRelay()
            
            # Initialize camera
            self.initialize_camera()
            
            self.get_logger().info("WebRTC components initialized")
            
        except Exception as e:
            self.get_logger().error(f"WebRTC components initialization error: {e}")

    def initialize_camera(self):
        """Initialize camera for video capture."""
        try:
            if not WEBRTC_AVAILABLE:
                return
            
            # Initialize camera with OpenCV
            self.camera = cv2.VideoCapture(self.camera_device)
            
            if not self.camera.isOpened():
                raise Exception(f"Could not open camera device {self.camera_device}")
            
            # Set camera properties
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera_width)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera_height)
            self.camera.set(cv2.CAP_PROP_FPS, self.camera_fps)
            
            self.get_logger().info(f"Camera initialized: {self.camera_width}x{self.camera_height}@{self.camera_fps}fps")
            
        except Exception as e:
            self.get_logger().error(f"Camera initialization error: {e}")
            self.camera = None

    def handle_emergency_alert_callback(self, msg: EmergencyAlert):
        """Handle emergency alert and start emergency streaming."""
        try:
            self.get_logger().critical(f"EMERGENCY: Starting video stream for {msg.emergency_type}")
            
            # Create emergency stream session
            session = self.create_emergency_stream_session(msg)
            
            # Generate secure access token
            access_token = self.generate_access_token(session)
            
            # Start emergency stream
            self.start_emergency_stream(session, access_token)
            
            # Publish stream access information
            self.publish_stream_access(session, access_token)
            
        except Exception as e:
            self.get_logger().error(f"Emergency streaming setup error: {e}")

    def create_emergency_stream_session(self, alert: EmergencyAlert) -> StreamSession:
        """Create emergency stream session."""
        session_id = f"emergency_{int(time.time())}"
        
        session = StreamSession(
            session_id=session_id,
            family_member_id="emergency_access",
            stream_type="emergency",
            quality=StreamQuality.EMERGENCY,
            start_time=datetime.now(),
            emergency_context=True,
            access_token="",  # Will be generated
            stream_url=""     # Will be set when stream starts
        )
        
        self.active_streams[session_id] = session
        return session

    def generate_access_token(self, session: StreamSession) -> str:
        """Generate secure access token for stream."""
        try:
            token_data = {
                'session_id': session.session_id,
                'family_member_id': session.family_member_id,
                'stream_type': session.stream_type,
                'created_at': session.start_time.isoformat(),
                'expires_at': (session.start_time + timedelta(hours=2)).isoformat(),
                'emergency': session.emergency_context
            }
            
            # In production, this would be properly signed JWT
            token = base64.b64encode(json.dumps(token_data).encode()).decode()
            
            session.access_token = token
            self.access_tokens[token] = token_data
            
            return token
            
        except Exception as e:
            self.get_logger().error(f"Access token generation error: {e}")
            return ""

    def start_emergency_stream(self, session: StreamSession, access_token: str):
        """Start emergency video stream."""
        try:
            if self.mediamtx_enabled:
                # Use MediaMTX for stream distribution
                stream_url = self.start_mediamtx_stream(session)
            else:
                # Direct WebRTC streaming
                stream_url = self.start_direct_webrtc_stream(session)
            
            session.stream_url = stream_url
            self.current_state = StreamState.STREAMING
            
            self.get_logger().critical(f"Emergency stream started: {stream_url}")
            
        except Exception as e:
            self.get_logger().error(f"Emergency stream start error: {e}")
            self.current_state = StreamState.ERROR

    def start_mediamtx_stream(self, session: StreamSession) -> str:
        """Start stream via MediaMTX."""
        try:
            # Configure MediaMTX stream
            stream_path = f"emergency_feed_{session.session_id}"
            
            # MediaMTX will handle WebRTC signaling
            stream_url = f"http://localhost:8888/{stream_path}/whep"
            
            # Start GStreamer pipeline to MediaMTX
            self.start_gstreamer_pipeline(stream_path, session.quality)
            
            return stream_url
            
        except Exception as e:
            self.get_logger().error(f"MediaMTX stream start error: {e}")
            return ""

    def start_gstreamer_pipeline(self, stream_path: str, quality: StreamQuality):
        """Start GStreamer pipeline for video streaming."""
        try:
            if not WEBRTC_AVAILABLE:
                return
            
            config = self.stream_configs[quality]
            
            # Create GStreamer pipeline for camera capture and WebRTC streaming
            pipeline_str = f"""
            v4l2src device=/dev/video{self.camera_device} ! 
            video/x-raw,width={config.width},height={config.height},framerate={config.fps}/1 ! 
            videoconvert ! 
            x264enc bitrate={config.bitrate//1000} tune=zerolatency speed-preset=ultrafast ! 
            h264parse ! 
            rtph264pay ! 
            webrtcsink name=webrtcsink signaller::uri="ws://localhost:8889/{stream_path}"
            """
            
            # In a full implementation, this would start the actual GStreamer pipeline
            self.get_logger().info(f"GStreamer pipeline configured for {stream_path}")
            
        except Exception as e:
            self.get_logger().error(f"GStreamer pipeline error: {e}")

    def publish_stream_access(self, session: StreamSession, access_token: str):
        """Publish stream access information for family app."""
        try:
            access_info = {
                'session_id': session.session_id,
                'stream_url': session.stream_url,
                'access_token': access_token,
                'stream_type': session.stream_type,
                'quality': session.quality.value,
                'emergency_context': session.emergency_context,
                'expires_at': (session.start_time + timedelta(hours=2)).isoformat(),
                'viewer_instructions': {
                    'web_url': f"https://family-app.elderly-companion.com/stream/{session.session_id}?token={access_token}",
                    'mobile_deep_link': f"elderlycompanion://emergency/stream/{session.session_id}?token={access_token}",
                    'backup_rtsp': f"rtsp://localhost:8554/{session.session_id}"
                }
            }
            
            access_msg = String()
            access_msg.data = json.dumps(access_info)
            self.stream_access_pub.publish(access_msg)
            
            self.get_logger().critical(f"Stream access published for emergency: {session.session_id}")
            
        except Exception as e:
            self.get_logger().error(f"Stream access publishing error: {e}")

    def camera_image_callback(self, msg: Image):
        """Handle camera image from ROS2 camera node."""
        try:
            if self.current_state != StreamState.STREAMING:
                return
            
            # Convert ROS Image to OpenCV format
            if WEBRTC_AVAILABLE:
                # This would convert and add to frame queue for WebRTC streaming
                pass
            
        except Exception as e:
            self.get_logger().error(f"Camera image callback error: {e}")

    def start_signaling_server(self):
        """Start WebRTC signaling server."""
        try:
            def run_server():
                if WEBRTC_AVAILABLE:
                    # Start aiohttp server for WebRTC signaling
                    self.start_aiohttp_signaling_server()
                else:
                    # Mock server
                    self.get_logger().info("Mock signaling server started")
            
            # Start server in separate thread
            threading.Thread(target=run_server, daemon=True).start()
            
        except Exception as e:
            self.get_logger().error(f"Signaling server start error: {e}")

    def start_aiohttp_signaling_server(self):
        """Start aiohttp server for WebRTC signaling."""
        try:
            app = web.Application()
            
            # Add routes
            app.router.add_post('/api/stream/start', self.handle_stream_start_request)
            app.router.add_post('/api/stream/offer', self.handle_webrtc_offer)
            app.router.add_post('/api/stream/answer', self.handle_webrtc_answer)
            app.router.add_post('/api/stream/ice', self.handle_ice_candidate)
            app.router.add_get('/api/stream/status/{session_id}', self.handle_stream_status)
            
            # CORS middleware for family app access
            app.middlewares.append(self.cors_middleware)
            
            # Start server
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            web.run_app(app, host='0.0.0.0', port=self.signaling_port)
            
        except Exception as e:
            self.get_logger().error(f"Aiohttp signaling server error: {e}")

    async def cors_middleware(self, request, handler):
        """Handle CORS middleware for cross-origin requests."""
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response

    async def handle_stream_start_request(self, request):
        """Handle stream start request from family app."""
        try:
            data = await request.json()
            
            # Validate access token
            token = data.get('access_token', '')
            if self.auth_enabled and not self.validate_access_token(token):
                return web.json_response({'error': 'Invalid access token'}, status=401)
            
            # Create stream session
            session_id = data.get('session_id', str(uuid.uuid4()))
            quality = StreamQuality(data.get('quality', 'medium'))
            
            session = StreamSession(
                session_id=session_id,
                family_member_id=data.get('family_member_id', 'unknown'),
                stream_type=data.get('stream_type', 'monitoring'),
                quality=quality,
                start_time=datetime.now(),
                emergency_context=data.get('emergency', False)
            )
            
            self.active_streams[session_id] = session
            
            # Generate stream URL
            if self.mediamtx_enabled:
                stream_url = f"http://localhost:8888/{session_id}/whep"
            else:
                stream_url = f"http://localhost:{self.signaling_port}/stream/{session_id}"
            
            session.stream_url = stream_url
            
            return web.json_response({
                'success': True,
                'session_id': session_id,
                'stream_url': stream_url,
                'signaling_url': f"ws://localhost:{self.signaling_port}/ws/{session_id}"
            })
            
        except Exception as e:
            self.get_logger().error(f"Stream start request error: {e}")
            return web.json_response({'error': str(e)}, status=500)

    async def handle_webrtc_offer(self, request):
        """Handle WebRTC offer from client."""
        try:
            data = await request.json()
            session_id = data['session_id']
            offer = data['offer']
            
            # Create peer connection
            pc = RTCPeerConnection(configuration={
                'iceServers': [{'urls': self.stun_server}]
            })
            
            self.peer_connections[session_id] = pc
            
            # Add video track
            if self.video_track:
                pc.addTrack(self.video_track)
            
            # Handle offer
            await pc.setRemoteDescription(RTCSessionDescription(
                sdp=offer['sdp'], 
                type=offer['type']
            ))
            
            # Create answer
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)
            
            return web.json_response({
                'success': True,
                'answer': {
                    'type': answer.type,
                    'sdp': answer.sdp
                }
            })
            
        except Exception as e:
            self.get_logger().error(f"WebRTC offer handling error: {e}")
            return web.json_response({'error': str(e)}, status=500)

    async def handle_webrtc_answer(self, request):
        """Handle WebRTC answer from client."""
        try:
            data = await request.json()
            session_id = data['session_id']
            answer = data['answer']
            
            pc = self.peer_connections.get(session_id)
            if not pc:
                return web.json_response({'error': 'Session not found'}, status=404)
            
            await pc.setRemoteDescription(RTCSessionDescription(
                sdp=answer['sdp'],
                type=answer['type']
            ))
            
            return web.json_response({'success': True})
            
        except Exception as e:
            self.get_logger().error(f"WebRTC answer handling error: {e}")
            return web.json_response({'error': str(e)}, status=500)

    async def handle_ice_candidate(self, request):
        """Handle ICE candidate from client."""
        try:
            data = await request.json()
            session_id = data['session_id']
            candidate = data['candidate']
            
            pc = self.peer_connections.get(session_id)
            if not pc:
                return web.json_response({'error': 'Session not found'}, status=404)
            
            # Add ICE candidate
            # In full implementation, would handle ICE candidates properly
            
            return web.json_response({'success': True})
            
        except Exception as e:
            self.get_logger().error(f"ICE candidate handling error: {e}")
            return web.json_response({'error': str(e)}, status=500)

    async def handle_stream_status(self, request):
        """Handle stream status request."""
        try:
            session_id = request.match_info['session_id']
            session = self.active_streams.get(session_id)
            
            if not session:
                return web.json_response({'error': 'Session not found'}, status=404)
            
            status = {
                'session_id': session.session_id,
                'state': self.current_state.value,
                'quality': session.quality.value,
                'viewer_count': session.viewer_count,
                'duration_seconds': int((datetime.now() - session.start_time).total_seconds()),
                'stream_url': session.stream_url
            }
            
            return web.json_response(status)
            
        except Exception as e:
            self.get_logger().error(f"Stream status request error: {e}")
            return web.json_response({'error': str(e)}, status=500)

    def validate_access_token(self, token: str) -> bool:
        """Validate access token."""
        try:
            if not self.auth_enabled:
                return True
            
            token_data = self.access_tokens.get(token)
            if not token_data:
                return False
            
            # Check expiration
            expires_at = datetime.fromisoformat(token_data['expires_at'])
            if datetime.now() > expires_at:
                del self.access_tokens[token]
                return False
            
            return True
            
        except Exception as e:
            self.get_logger().error(f"Token validation error: {e}")
            return False

    def cleanup_expired_streams(self):
        """Clean up expired stream sessions."""
        try:
            current_time = datetime.now()
            expired_sessions = []
            
            for session_id, session in self.active_streams.items():
                # Clean up sessions older than 2 hours or completed
                if (current_time - session.start_time).total_seconds() > 7200:
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                self.terminate_stream_session(session_id)
                
        except Exception as e:
            self.get_logger().error(f"Stream cleanup error: {e}")

    def terminate_stream_session(self, session_id: str):
        """Terminate stream session."""
        try:
            session = self.active_streams.get(session_id)
            if not session:
                return
            
            # Close peer connection
            pc = self.peer_connections.get(session_id)
            if pc:
                # Close peer connection
                del self.peer_connections[session_id]
            
            # Update session
            session.end_time = datetime.now()
            session.duration_seconds = int((session.end_time - session.start_time).total_seconds())
            
            # Remove from active streams
            del self.active_streams[session_id]
            
            self.get_logger().info(f"Stream session terminated: {session_id}")
            
        except Exception as e:
            self.get_logger().error(f"Stream termination error: {e}")

    def __del__(self):
        """Clean up when node is destroyed."""
        try:
            if hasattr(self, 'camera') and self.camera:
                self.camera.release()
            
            for pc in self.peer_connections.values():
                # Close peer connections
                pass
                
        except:
            pass


def main(args=None):
    """Run the main entry point."""
    rclpy.init(args=args)
    
    try:
        node = WebRTCStreamerNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()