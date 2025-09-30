#!/usr/bin/env python3
"""
Text-to-Speech Engine Node for Elderly Companion Robdog.

Provides audio output for the Router Agent system with elderly-optimized settings.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

import threading
import time
import queue
from typing import Optional

# Audio/TTS imports
try:
    import pyttsx3
    HAS_PYTTSX3 = True
except ImportError:
    HAS_PYTTSX3 = False

# ROS2 message imports
from std_msgs.msg import String, Bool
from sensor_msgs.msg import Audio


class TTSEngineNode(Node):
    """
    Text-to-Speech Engine Node for elderly-optimized audio output.
    """

    def __init__(self):
        super().__init__('tts_engine_node')
        
        # Initialize parameters
        self.declare_parameters(
            namespace='',
            parameters=[
                ('tts.engine', 'pyttsx3'),
                ('tts.voice_id', 'zh'),
                ('tts.rate', 150),           # Slower for elderly
                ('tts.volume', 0.8),
                ('tts.elderly_optimized', True),
                ('audio.output_device', -1),  # Default device
            ]
        )
        
        # Get parameters
        self.engine_type = self.get_parameter('tts.engine').value
        self.voice_id = self.get_parameter('tts.voice_id').value
        self.speech_rate = self.get_parameter('tts.rate').value
        self.volume = self.get_parameter('tts.volume').value
        self.elderly_optimized = self.get_parameter('tts.elderly_optimized').value
        
        # Initialize TTS engine
        self.tts_engine = None
        self.is_speaking = False
        self.speech_queue = queue.Queue()
        
        self.initialize_tts_engine()
        
        # QoS profiles
        default_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        # Subscribers
        self.tts_request_sub = self.create_subscription(
            String,
            '/tts/request',
            self.handle_tts_request,
            default_qos
        )
        
        # Publishers
        self.tts_status_pub = self.create_publisher(
            Bool,
            '/tts/status',
            default_qos
        )
        
        # Start TTS processing thread
        self.tts_thread = threading.Thread(target=self.tts_processing_loop, daemon=True)
        self.tts_thread.start()
        
        self.get_logger().info("TTS Engine Node initialized successfully")

    def initialize_tts_engine(self):
        """Initialize the TTS engine."""
        try:
            if self.engine_type == 'pyttsx3' and HAS_PYTTSX3:
                self.tts_engine = pyttsx3.init()
                
                # Configure for elderly users
                self.tts_engine.setProperty('rate', self.speech_rate)
                self.tts_engine.setProperty('volume', self.volume)
                
                # Try to set voice (Chinese if available)
                voices = self.tts_engine.getProperty('voices')
                if voices:
                    for voice in voices:
                        if 'chinese' in voice.name.lower() or 'zh' in voice.id.lower():
                            self.tts_engine.setProperty('voice', voice.id)
                            break
                
                self.get_logger().info(f"TTS engine initialized: {self.engine_type}")
                
            else:
                self.get_logger().warning("TTS engine not available, using fallback")
                self.tts_engine = None
                
        except Exception as e:
            self.get_logger().error(f"TTS engine initialization failed: {e}")
            self.tts_engine = None

    def handle_tts_request(self, msg: String):
        """Handle TTS request."""
        try:
            text = msg.data.strip()
            if text:
                self.get_logger().info(f"TTS request: '{text}'")
                self.speech_queue.put(text)
                
        except Exception as e:
            self.get_logger().error(f"TTS request handling error: {e}")

    def tts_processing_loop(self):
        """Main TTS processing loop."""
        while rclpy.ok():
            try:
                # Get text from queue with timeout
                text = self.speech_queue.get(timeout=1.0)
                
                # Process TTS
                self.speak_text(text)
                
            except queue.Empty:
                continue
            except Exception as e:
                self.get_logger().error(f"TTS processing loop error: {e}")

    def speak_text(self, text: str):
        """Speak the given text."""
        try:
            self.is_speaking = True
            self.publish_tts_status(True)
            
            if self.tts_engine:
                # Use pyttsx3 for actual speech
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
            else:
                # Fallback: just print and simulate delay
                print(f"🔊 TTS: {text}")
                # Simulate speech time (roughly 10 characters per second for elderly pace)
                speech_time = len(text) / 10.0
                time.sleep(max(1.0, speech_time))
            
            self.get_logger().info(f"TTS completed: '{text}'")
            
        except Exception as e:
            self.get_logger().error(f"TTS speech error: {e}")
        finally:
            self.is_speaking = False
            self.publish_tts_status(False)

    def publish_tts_status(self, speaking: bool):
        """Publish TTS status."""
        try:
            status_msg = Bool()
            status_msg.data = speaking
            self.tts_status_pub.publish(status_msg)
            
        except Exception as e:
            self.get_logger().error(f"TTS status publishing error: {e}")


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)
    
    try:
        node = TTSEngineNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()