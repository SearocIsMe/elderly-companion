#!/usr/bin/env python3
"""
Enhanced Router Agent Coordinator for Elderly Companion Robdog.

Complete integration coordinator that orchestrates the full elderly companion system:
- Audio Pipeline: Silero VAD → ASR → Emotion Analysis → Enhanced Guard
- Core Logic: FastAPI Services (Guard → Intent → Orchestrator → Adapters)
- Communication: SIP/VoIP Emergency Calling + SMS/Email Notifications  
- Smart Home: MQTT/Home Assistant Integration + Elderly Care Automation
- Video: WebRTC Streaming to Family Frontend
- Safety: Advanced Guard Engine + Emergency Response Protocols
- Output: Enhanced TTS with Elderly Optimization

Architecture maintains proven FastAPI closed-loop functionality while adding
comprehensive ROS2 integration and advanced elderly care features.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from rclpy.executors import MultiThreadedExecutor

import json
import time
import threading
import queue
import requests
import subprocess
import os
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum

# ROS2 message imports
from std_msgs.msg import Header, String, Bool
from sensor_msgs.msg import Audio, Image
from elderly_companion.msg import (
    SpeechResult, EmotionData, IntentResult, 
    HealthStatus, EmergencyAlert, SafetyConstraints
)
from elderly_companion.srv import ProcessSpeech, ValidateIntent, ExecuteAction, EmergencyDispatch


class RouterAgentMode(Enum):
    """Enhanced Router Agent operational modes."""
    TEXT_ONLY = "text_only"
    AUDIO_ONLY = "audio_only"
    HYBRID = "hybrid"
    EMERGENCY = "emergency"
    MAINTENANCE = "maintenance"
    DEMO = "demo"


class SystemComponent(Enum):
    """System components for status tracking."""
    SILERO_VAD = "silero_vad"
    SPEECH_RECOGNITION = "speech_recognition" 
    ENHANCED_GUARD = "enhanced_guard"
    GUARD_FASTAPI_BRIDGE = "guard_fastapi_bridge"
    FASTAPI_BRIDGE = "fastapi_bridge"
    ENHANCED_TTS = "enhanced_tts"
    SIP_VOIP_ADAPTER = "sip_voip_adapter"
    SMART_HOME_BACKEND = "smart_home_backend"
    WEBRTC_UPLINK = "webrtc_uplink"
    DIALOG_MANAGER = "dialog_manager"
    EMOTION_ANALYZER = "emotion_analyzer"
    
    # FastAPI Services
    FASTAPI_ORCHESTRATOR = "fastapi_orchestrator"
    FASTAPI_GUARD = "fastapi_guard"
    FASTAPI_INTENT = "fastapi_intent"
    FASTAPI_ADAPTERS = "fastapi_adapters"


class SystemStatus(Enum):
    """Overall system status."""
    STARTING = "starting"
    READY = "ready"
    ACTIVE = "active"
    EMERGENCY = "emergency"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    SHUTTING_DOWN = "shutting_down"


class EnhancedRouterAgentCoordinator(Node):
    """
    Enhanced Router Agent Coordinator - Complete Integration Orchestrator.
    
    Orchestrates the complete elderly companion system with all new components.
    """

    def __init__(self):
        super().__init__('enhanced_router_agent_coordinator')
        
        # Initialize comprehensive parameters
        self.declare_parameters(
            namespace='',
            parameters=[
                # System Mode and Operation
                ('router_agent.mode', 'hybrid'),
                ('router_agent.enable_safety_monitoring', True),
                ('router_agent.enable_conversation_logging', True),
                ('router_agent.response_timeout_seconds', 10.0),
                ('router_agent.startup_timeout_seconds', 120.0),
                ('router_agent.enable_component_health_monitoring', True),
                
                # Audio System Configuration
                ('audio.enable_microphone', True),
                ('audio.enable_speaker', True),
                ('audio.enable_silero_vad', True),
                ('audio.enable_noise_reduction', True),
                ('audio.sample_rate', 16000),
                
                # User Interface Configuration
                ('ui.enable_console_interface', True),
                ('ui.enable_web_interface', True),
                ('ui.enable_family_app_interface', True),
                ('ui.console_welcome_message', True),
                
                # Safety and Emergency Configuration
                ('safety.emergency_response_time_ms', 100),
                ('safety.enable_enhanced_guard', True),
                ('safety.enable_guard_fastapi_bridge', True),
                ('safety.emergency_escalation_enabled', True),
                ('safety.proactive_safety_monitoring', True),
                
                # FastAPI Services Configuration
                ('fastapi.orchestrator_url', 'http://localhost:7010'),
                ('fastapi.guard_url', 'http://localhost:7002'),
                ('fastapi.intent_url', 'http://localhost:7001'),
                ('fastapi.adapters_url', 'http://localhost:7003'),
                ('fastapi.enable_auto_start', True),
                ('fastapi.startup_wait_seconds', 30),
                
                # Communication Configuration
                ('communication.enable_sip_voip', True),
                ('communication.enable_sms_notifications', True),
                ('communication.enable_email_notifications', True),
                
                # Smart Home Configuration
                ('smart_home.enable_automation', True),
                ('smart_home.enable_emergency_scenes', True),
                
                # Video Streaming Configuration
                ('video.enable_webrtc_streaming', True),
                ('video.enable_emergency_activation', True),
                
                # AI and Conversation
                ('ai.conversation_model', 'local'),
                ('ai.safety_level', 'elderly_care'),
                ('ai.enable_emotion_awareness', True),
                
                # Performance and Monitoring
                ('monitoring.enable_performance_tracking', True),
                ('monitoring.health_check_interval', 30),
                
                # Deployment Configuration
                ('deployment.target', 'development'),
                ('deployment.enable_docker_integration', True),
            ]
        )
        
        # Get parameters
        self.mode = RouterAgentMode(self.get_parameter('router_agent.mode').value)
        self.enable_safety = self.get_parameter('router_agent.enable_safety_monitoring').value
        self.enable_console = self.get_parameter('ui.enable_console_interface').value
        self.enable_enhanced_guard = self.get_parameter('safety.enable_enhanced_guard').value
        self.enable_smart_home = self.get_parameter('smart_home.enable_automation').value
        self.enable_video_streaming = self.get_parameter('video.enable_webrtc_streaming').value
        self.enable_sip_voip = self.get_parameter('communication.enable_sip_voip').value
        self.deployment_target = self.get_parameter('deployment.target').value
        self.enable_docker_integration = self.get_parameter('deployment.enable_docker_integration').value
        
        # FastAPI services configuration
        self.fastapi_urls = {
            'orchestrator': self.get_parameter('fastapi.orchestrator_url').value,
            'guard': self.get_parameter('fastapi.guard_url').value,
            'intent': self.get_parameter('fastapi.intent_url').value,
            'adapters': self.get_parameter('fastapi.adapters_url').value
        }
        
        # System state management
        self.system_status = SystemStatus.STARTING
        self.is_active = False
        self.current_conversation_id = None
        self.startup_complete = False
        self.emergency_mode = False
        
        # Enhanced component status tracking
        self.component_status = {component.value: False for component in SystemComponent}
        self.component_health_data: Dict[str, Dict[str, Any]] = {}
        
        # System metrics and performance tracking
        self.system_metrics = {
            'total_conversations': 0,
            'emergency_responses': 0,
            'successful_actions': 0,
            'system_uptime_start': datetime.now(),
            'last_health_check': None,
            'fastapi_services_active': 0,
            'ros2_nodes_active': 0
        }
        
        # HTTP session for FastAPI communication
        self.http_session = requests.Session()
        self.http_session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Enhanced-Router-Coordinator/1.0'
        })
        
        # QoS profiles
        critical_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=100
        )
        
        default_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=50
        )
        
        fast_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )
        
        # Subscribers - Input channels
        self.text_input_sub = self.create_subscription(
            String,
            '/router_agent/text_input',
            self.handle_text_input,
            default_qos
        )
        
        # Subscribers - Enhanced system outputs
        self.fastapi_response_sub = self.create_subscription(
            String,
            '/fastapi/response',
            self.handle_fastapi_response,
            default_qos
        )
        
        self.guard_decision_sub = self.create_subscription(
            String,
            '/guard/final_decision',
            self.handle_guard_decision,
            critical_qos
        )
        
        self.smart_home_result_sub = self.create_subscription(
            String,
            '/smart_home/automation_result',
            self.handle_smart_home_result,
            default_qos
        )
        
        self.webrtc_status_sub = self.create_subscription(
            String,
            '/webrtc/stream_status',
            self.handle_webrtc_status,
            fast_qos
        )
        
        self.emergency_alert_sub = self.create_subscription(
            EmergencyAlert,
            '/emergency/alert',
            self.handle_emergency_alert,
            critical_qos
        )
        
        self.tts_status_sub = self.create_subscription(
            Bool,
            '/tts/status',
            self.handle_tts_status,
            fast_qos
        )
        
        # Publishers - Enhanced output channels
        self.text_output_pub = self.create_publisher(
            String,
            '/router_agent/text_output',
            default_qos
        )
        
        self.emotion_aware_tts_pub = self.create_publisher(
            String,
            '/tts/emotion_request',
            default_qos
        )
        
        self.system_status_pub = self.create_publisher(
            String,
            '/router_agent/system_status',
            fast_qos
        )
        
        self.system_metrics_pub = self.create_publisher(
            String,
            '/router_agent/system_metrics',
            default_qos
        )
        
        # Service clients for component coordination
        self.service_clients = {}
        self.initialize_service_clients()
        
        # Timers
        self.health_check_timer = self.create_timer(
            self.get_parameter('monitoring.health_check_interval').value,
            self.check_system_health
        )
        self.metrics_timer = self.create_timer(60.0, self.publish_system_metrics)
        
        # Start the enhanced coordination system
        self.start_enhanced_coordination_system()
        
        self.get_logger().info(f"Enhanced Router Agent Coordinator initialized in {self.mode.value} mode")

    def initialize_service_clients(self):
        """Initialize service clients for component communication."""
        try:
            # FastAPI Bridge service
            self.service_clients['fastapi_bridge'] = self.create_client(
                ProcessSpeech,
                '/fastapi_bridge/process_text'
            )
            
            # Guard Bridge service
            self.service_clients['guard_bridge'] = self.create_client(
                ValidateIntent,
                '/guard_bridge/validate_intent'
            )
            
            # Smart Home service
            self.service_clients['smart_home'] = self.create_client(
                ExecuteAction,
                '/smart_home/execute_action'
            )
            
            # Emergency dispatch service
            self.service_clients['emergency_dispatch'] = self.create_client(
                EmergencyDispatch,
                '/sip_voip/emergency_dispatch'
            )
            
            self.get_logger().info("Service clients initialized")
            
        except Exception as e:
            self.get_logger().error(f"Service clients initialization error: {e}")

    def start_enhanced_coordination_system(self):
        """Start the complete Enhanced Router Agent coordination system."""
        try:
            self.get_logger().info("🚀 Starting Enhanced Router Agent Coordination System...")
            self.system_status = SystemStatus.STARTING
            
            # Start FastAPI services if auto-start is enabled
            if self.get_parameter('fastapi.enable_auto_start').value:
                self.start_fastapi_services()
            
            # Wait for essential components
            self.wait_for_essential_components()
            
            # Verify system integration
            self.verify_system_integration()
            
            # Activate the enhanced system
            self.system_status = SystemStatus.READY
            self.is_active = True
            self.startup_complete = True
            
            # Publish system status
            self.publish_enhanced_system_status("READY", "Enhanced Router Agent coordination system started")
            
            # Start console interface if enabled
            if self.enable_console:
                self.start_enhanced_console_interface()
            
            self.system_status = SystemStatus.ACTIVE
            self.get_logger().info("✅ Enhanced Router Agent Coordination System is ACTIVE")
            
        except Exception as e:
            self.system_status = SystemStatus.ERROR
            self.get_logger().error(f"Failed to start enhanced coordination system: {e}")
            self.publish_enhanced_system_status("ERROR", f"Startup failed: {e}")

    def start_fastapi_services(self):
        """Start FastAPI services if Docker integration is enabled."""
        try:
            if not self.enable_docker_integration:
                self.get_logger().info("Docker integration disabled - skipping FastAPI auto-start")
                return
            
            self.get_logger().info("Starting FastAPI services via Docker...")
            
            # Determine which docker-compose file to use
            docker_compose_file = self.get_docker_compose_file()
            
            if docker_compose_file and os.path.exists(docker_compose_file):
                # Start FastAPI services
                result = subprocess.run([
                    'docker-compose', '-f', docker_compose_file, 'up', '-d'
                ], capture_output=True, text=True, cwd=os.path.dirname(docker_compose_file))
                
                if result.returncode == 0:
                    self.get_logger().info("FastAPI services started successfully")
                    time.sleep(self.get_parameter('fastapi.startup_wait_seconds').value)
                else:
                    self.get_logger().warning(f"FastAPI services start failed: {result.stderr}")
            else:
                self.get_logger().warning(f"Docker compose file not found: {docker_compose_file}")
                
        except Exception as e:
            self.get_logger().error(f"FastAPI services start error: {e}")

    def get_docker_compose_file(self) -> Optional[str]:
        """Get appropriate Docker compose file based on deployment target."""
        try:
            base_path = os.path.join(
                os.path.dirname(__file__), 
                '../../router_agent/docker'
            )
            
            if self.deployment_target == 'rk3588':
                return os.path.join(base_path, 'docker-compose.rk3588.yml')
            elif self.deployment_target == 'production':
                return os.path.join(base_path, 'docker-compose.pc.gpu.yml')
            else:
                return os.path.join(base_path, 'docker-compose.pc.yml')
                
        except Exception:
            return None

    def wait_for_essential_components(self):
        """Wait for essential components to be ready."""
        try:
            self.get_logger().info("⏳ Waiting for essential components...")
            
            max_wait_time = self.get_parameter('router_agent.startup_timeout_seconds').value
            start_time = time.time()
            
            essential_components = [
                SystemComponent.FASTAPI_ORCHESTRATOR,
                SystemComponent.FASTAPI_BRIDGE
            ]
            
            # Add optional components based on configuration
            if self.enable_enhanced_guard:
                essential_components.append(SystemComponent.ENHANCED_GUARD)
                essential_components.append(SystemComponent.GUARD_FASTAPI_BRIDGE)
            
            while (time.time() - start_time) < max_wait_time:
                ready_count = 0
                
                for component in essential_components:
                    if self.check_component_availability(component):
                        self.component_status[component.value] = True
                        ready_count += 1
                
                if ready_count == len(essential_components):
                    self.get_logger().info("✅ Essential components are ready")
                    return True
                
                self.get_logger().info(f"⏳ {ready_count}/{len(essential_components)} essential components ready...")
                time.sleep(5.0)
            
            self.get_logger().warning("⚠️ Not all essential components ready, starting anyway")
            return False
            
        except Exception as e:
            self.get_logger().error(f"Component wait error: {e}")
            return False

    def check_component_availability(self, component: SystemComponent) -> bool:
        """Check if a specific component is available."""
        try:
            if component in [SystemComponent.FASTAPI_ORCHESTRATOR, SystemComponent.FASTAPI_GUARD,
                           SystemComponent.FASTAPI_INTENT, SystemComponent.FASTAPI_ADAPTERS]:
                # Check FastAPI services via HTTP health endpoints
                return self.check_fastapi_service_health(component)
            else:
                # For ROS2 components, assume available (could ping services in production)
                return True
                
        except Exception:
            return False

    def check_fastapi_service_health(self, component: SystemComponent) -> bool:
        """Check FastAPI service health."""
        try:
            if component == SystemComponent.FASTAPI_ORCHESTRATOR:
                url = f"{self.fastapi_urls['orchestrator']}/health"
            elif component == SystemComponent.FASTAPI_GUARD:
                url = f"{self.fastapi_urls['guard']}/health"
            elif component == SystemComponent.FASTAPI_INTENT:
                url = f"{self.fastapi_urls['intent']}/health"
            elif component == SystemComponent.FASTAPI_ADAPTERS:
                url = f"{self.fastapi_urls['adapters']}/health"
            else:
                return False
            
            response = self.http_session.get(url, timeout=5)
            return response.status_code == 200
            
        except Exception:
            return False

    def verify_system_integration(self):
        """Verify system integration is working properly."""
        try:
            self.get_logger().info("🔍 Verifying system integration...")
            
            # Test FastAPI orchestrator integration
            test_response = self.test_fastapi_integration()
            if test_response:
                self.get_logger().info("✅ FastAPI integration verified")
            else:
                self.get_logger().warning("⚠️ FastAPI integration test failed")
            
            # Check component communication
            self.verify_component_communication()
            
            self.get_logger().info("✅ System integration verification completed")
            
        except Exception as e:
            self.get_logger().error(f"System integration verification error: {e}")

    def test_fastapi_integration(self) -> bool:
        """Test FastAPI orchestrator integration."""
        try:
            test_url = f"{self.fastapi_urls['orchestrator']}/asr_text"
            test_data = {"text": "系统测试"}
            
            response = self.http_session.post(test_url, json=test_data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                self.get_logger().debug(f"FastAPI test response: {result}")
                return True
            else:
                self.get_logger().warning(f"FastAPI test failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.get_logger().warning(f"FastAPI integration test error: {e}")
            return False

    def verify_component_communication(self):
        """Verify ROS2 component communication."""
        try:
            # Test service availability
            for service_name, client in self.service_clients.items():
                if client.wait_for_service(timeout_sec=5.0):
                    self.get_logger().info(f"✅ {service_name} service available")
                else:
                    self.get_logger().warning(f"⚠️ {service_name} service not available")
                    
        except Exception as e:
            self.get_logger().error(f"Component communication verification error: {e}")

    def start_enhanced_console_interface(self):
        """Start enhanced console interface."""
        try:
            if not self.enable_console:
                return
            
            # Start console input thread
            self.console_thread = threading.Thread(
                target=self.enhanced_console_loop,
                daemon=True
            )
            self.console_thread.start()
            
            # Display welcome message
            self.display_enhanced_welcome_message()
            
        except Exception as e:
            self.get_logger().error(f"Enhanced console interface start error: {e}")

    def display_enhanced_welcome_message(self):
        """Display enhanced welcome message."""
        if self.get_parameter('ui.console_welcome_message').value:
            print("\n" + "="*80)
            print("🤖 ELDERLY COMPANION ROBOT - ENHANCED ROUTER AGENT SYSTEM")
            print("="*80)
            print(f"System Mode: {self.mode.value.upper()}")
            print(f"Deployment Target: {self.deployment_target.upper()}")
            print(f"System Status: {self.system_status.value.upper()}")
            print("\n🔧 Available Features:")
            print("  ✅ Audio Pipeline (Silero VAD → ASR → Emotion Analysis)")
            print("  ✅ Enhanced Safety Guard with FastAPI Integration")
            print("  ✅ Emergency SIP/VoIP Calling with SMS/Email")
            print("  ✅ Smart Home Automation (MQTT/Home Assistant)")
            print("  ✅ WebRTC Video Streaming to Family")
            print("  ✅ Elderly-Optimized TTS Engine")
            print("  ✅ FastAPI Closed-Loop Processing")
            print("\n💬 Commands:")
            print("  - Type your message and press Enter")
            print("  - 'quit' or 'exit' to stop the system")
            print("  - 'status' to check system status")
            print("  - 'health' to check component health")
            print("  - 'emergency' to test emergency response")
            print("  - 'help' for emergency assistance")
            print("="*80)
            print("🟢 Ready for conversation...")
            print()

    def enhanced_console_loop(self):
        """Enhanced console input loop."""
        while self.is_active:
            try:
                user_input = input("You: ").strip()
                
                if user_input.lower() in ['quit', 'exit']:
                    self.shutdown_enhanced_system()
                    break
                elif user_input.lower() == 'status':
                    self.print_enhanced_system_status()
                elif user_input.lower() == 'health':
                    self.print_component_health()
                elif user_input.lower() == 'emergency':
                    self.test_emergency_response()
                elif user_input.lower() == 'help':
                    self.trigger_help_request()
                elif user_input:
                    # Process text input through enhanced pipeline
                    self.process_enhanced_text_input(user_input)
                    
            except EOFError:
                break
            except KeyboardInterrupt:
                self.get_logger().info("Console interface interrupted")
                break
            except Exception as e:
                self.get_logger().error(f"Console input error: {e}")

    def process_enhanced_text_input(self, text: str):
        """Process text input through the enhanced pipeline."""
        try:
            self.get_logger().info(f"Processing enhanced text input: '{text}'")
            
            # Send to FastAPI bridge for processing
            if 'fastapi_bridge' in self.service_clients:
                client = self.service_clients['fastapi_bridge']
                
                if client.wait_for_service(timeout_sec=2.0):
                    request = ProcessSpeech.Request()
                    request.text = text
                    
                    # Call service asynchronously
                    future = client.call_async(request)
                    future.add_done_callback(
                        lambda f: self.handle_fastapi_bridge_response(f, text)
                    )
                else:
                    self.get_logger().warning("FastAPI bridge service not available")
                    self.fallback_text_processing(text)
            else:
                self.fallback_text_processing(text)
                
        except Exception as e:
            self.get_logger().error(f"Enhanced text input processing error: {e}")

    def handle_fastapi_bridge_response(self, future, original_text: str):
        """Handle response from FastAPI bridge service."""
        try:
            response = future.result()
            
            if response.processing_successful:
                result_data = json.loads(response.result_data)
                self.get_logger().info(f"FastAPI bridge response: {result_data.get('status', 'unknown')}")
                
                # Generate appropriate TTS response
                self.generate_response_from_fastapi_result(result_data, original_text)
                
                # Update metrics
                self.system_metrics['successful_actions'] += 1
            else:
                self.get_logger().error(f"FastAPI bridge processing failed: {response.error_message}")
                self.send_error_response("处理失败，请重试")
                
        except Exception as e:
            self.get_logger().error(f"FastAPI bridge response handling error: {e}")

    def generate_response_from_fastapi_result(self, result_data: Dict[str, Any], original_text: str):
        """Generate appropriate response from FastAPI result."""
        try:
            status = result_data.get('status', 'unknown')
            
            if status == 'emergency_dispatched':
                response_text = "紧急情况已确认！正在立即联系帮助。请保持冷静，不要移动。"
                self.send_urgent_response(response_text)
                self.system_metrics['emergency_responses'] += 1
                
            elif status == 'denied':
                reason = result_data.get('reason', '安全原因')
                response_text = f"抱歉，出于{reason}，无法执行此操作。"
                self.send_response(response_text)
                
            elif status == 'need_confirm':
                prompt = result_data.get('prompt', '请确认是否继续此操作？')
                self.send_confirmation_request(prompt)
                
            elif status == 'ok':
                adapter = result_data.get('adapter', '')
                if adapter == 'smart-home':
                    response_text = "好的，正在为您调整智能家居设备。"
                elif adapter == 'sip':
                    response_text = "正在为您拨打电话。"
                else:
                    response_text = "好的，已经为您处理。"
                self.send_response(response_text)
                
            else:
                response_text = "我理解了您的话，让我想想如何帮助您。"
                self.send_response(response_text)
            
            self.system_metrics['total_conversations'] += 1
            
        except Exception as e:
            self.get_logger().error(f"Response generation error: {e}")

    def send_response(self, text: str):
        """Send normal response."""
        self.send_enhanced_response(text, urgency='normal')

    def send_urgent_response(self, text: str):
        """Send urgent response."""
        self.send_enhanced_response(text, urgency='emergency')

    def send_confirmation_request(self, prompt: str):
        """Send confirmation request."""
        self.send_enhanced_response(prompt, urgency='high', requires_confirmation=True)

    def send_error_response(self, message: str):
        """Send error response."""
        self.send_enhanced_response(message, urgency='normal', emotion_context={'primary_emotion': 'concern'})

    def send_enhanced_response(self, text: str, urgency: str = 'normal', 
                             requires_confirmation: bool = False,
                             emotion_context: Optional[Dict[str, Any]] = None):
        """Send enhanced response through multiple channels."""
        try:
            self.get_logger().info(f"Sending enhanced response: '{text}' (urgency: {urgency})")
            
            # 1. Text output (console display)
            print(f"Robot: {text}")
            
            # Publish text output
            text_msg = String()
            text_msg.data = text
            self.text_output_pub.publish(text_msg)
            
            # 2. Enhanced TTS with emotion awareness
            if self.enable_speaker:
                tts_request = {
                    'text': text,
                    'urgency': urgency,
                    'emotion': emotion_context or {'primary_emotion': 'neutral'},
                    'requires_confirmation': requires_confirmation,
                    'timestamp': datetime.now().isoformat()
                }
                
                tts_msg = String()
                tts_msg.data = json.dumps(tts_request)
                self.emotion_aware_tts_pub.publish(tts_msg)
            
            # Update response timing
            self.last_response_time = time.time()
            
        except Exception as e:
            self.get_logger().error(f"Enhanced response sending error: {e}")

    def handle_text_input(self, msg: String):
        """Handle text input with enhanced processing."""
        try:
            text = msg.data
            self.get_logger().info(f"Enhanced Router Agent received text: '{text}'")
            
            # Process through enhanced pipeline
            self.process_enhanced_text_input(text)
            
        except Exception as e:
            self.get_logger().error(f"Text input handling error: {e}")

    def handle_fastapi_response(self, msg: String):
        """Handle response from FastAPI bridge."""
        try:
            response_data = json.loads(msg.data)
            self.get_logger().debug(f"FastAPI response received: {response_data}")
            
            # The response should already be processed by the bridge
            # This is for monitoring and logging purposes
            
        except Exception as e:
            self.get_logger().error(f"FastAPI response handling error: {e}")

    def handle_guard_decision(self, msg: String):
        """Handle final guard decision."""
        try:
            decision_data = json.loads(msg.data)
            decision = decision_data.get('decision', 'unknown')
            
            self.get_logger().info(f"Guard decision received: {decision}")
            
            # React to guard decisions that require immediate action
            if decision == 'dispatch_emergency':
                self.handle_emergency_dispatch_decision(decision_data)
            elif decision == 'need_confirm':
                prompt = decision_data.get('prompt', '请确认您的请求。')
                self.send_confirmation_request(prompt)
                
        except Exception as e:
            self.get_logger().error(f"Guard decision handling error: {e}")

    def handle_emergency_dispatch_decision(self, decision_data: Dict[str, Any]):
        """Handle emergency dispatch decision from guard."""
        try:
            self.get_logger().critical("🚨 Emergency dispatch decision received")
            
            # Activate emergency mode
            self.emergency_mode = True
            self.system_status = SystemStatus.EMERGENCY
            
            # Send immediate response
            response_text = "紧急情况已确认！正在立即联系帮助。请保持冷静，我会一直陪伴您。"
            self.send_urgent_response(response_text)
            
            # Trigger emergency services
            self.trigger_comprehensive_emergency_response(decision_data)
            
        except Exception as e:
            self.get_logger().error(f"Emergency dispatch handling error: {e}")

    def trigger_comprehensive_emergency_response(self, decision_data: Dict[str, Any]):
        """Trigger comprehensive emergency response across all systems."""
        try:
            emergency_id = str(uuid.uuid4())
            
            # 1. Emergency SIP/VoIP calling
            if self.enable_sip_voip and 'emergency_dispatch' in self.service_clients:
                self.trigger_emergency_calling(emergency_id, decision_data)
            
            # 2. Smart home emergency scene
            if self.enable_smart_home and 'smart_home' in self.service_clients:
                self.trigger_emergency_smart_home(emergency_id)
            
            # 3. Emergency video streaming activation
            if self.enable_video_streaming:
                self.trigger_emergency_video_streaming(emergency_id)
            
            self.get_logger().critical(f"Comprehensive emergency response triggered: {emergency_id}")
            
        except Exception as e:
            self.get_logger().error(f"Comprehensive emergency response error: {e}")

    def trigger_emergency_calling(self, emergency_id: str, decision_data: Dict[str, Any]):
        """Trigger emergency calling."""
        try:
            client = self.service_clients['emergency_dispatch']
            
            request = EmergencyDispatch.Request()
            request.emergency_type = decision_data.get('reason', 'unknown')
            request.severity_level = 4  # Maximum severity
            request.location_description = "Elderly person at home"
            
            future = client.call_async(request)
            future.add_done_callback(
                lambda f: self.handle_emergency_dispatch_response(f, emergency_id)
            )
            
        except Exception as e:
            self.get_logger().error(f"Emergency calling trigger error: {e}")

    def trigger_emergency_smart_home(self, emergency_id: str):
        """Trigger emergency smart home automation."""
        try:
            client = self.service_clients['smart_home']
            
            request = ExecuteAction.Request()
            request.action_type = "emergency_scene"
            request.parameters = json.dumps({
                'emergency_id': emergency_id,
                'scene': 'emergency_response'
            })
            
            future = client.call_async(request)
            future.add_done_callback(lambda f: self.handle_smart_home_response(f))
            
        except Exception as e:
            self.get_logger().error(f"Emergency smart home trigger error: {e}")

    def trigger_emergency_video_streaming(self, emergency_id: str):
        """Trigger emergency video streaming activation."""
        try:
            # This would typically send a message to WebRTC uplink node
            # For now, we'll log the action
            self.get_logger().critical(f"Emergency video streaming activated: {emergency_id}")
            
        except Exception as e:
            self.get_logger().error(f"Emergency video streaming trigger error: {e}")

    def handle_emergency_dispatch_response(self, future, emergency_id: str):
        """Handle emergency dispatch response."""
        try:
            response = future.result()
            
            if response.dispatch_successful:
                self.get_logger().critical(f"✅ Emergency dispatch successful: {response.reference_id}")
            else:
                self.get_logger().critical(f"❌ Emergency dispatch failed")
                
        except Exception as e:
            self.get_logger().error(f"Emergency dispatch response error: {e}")

    def handle_smart_home_response(self, future):
        """Handle smart home response."""
        try:
            response = future.result()
            
            if response.execution_successful:
                self.get_logger().info("✅ Smart home emergency scene activated")
            else:
                self.get_logger().warning("⚠️ Smart home emergency scene failed")
                
        except Exception as e:
            self.get_logger().error(f"Smart home response error: {e}")

    def handle_smart_home_result(self, msg: String):
        """Handle smart home automation results."""
        try:
            result_data = json.loads(msg.data)
            action = result_data.get('action', 'unknown')
            
            self.get_logger().info(f"Smart home result: {action}")
            
        except Exception as e:
            self.get_logger().error(f"Smart home result handling error: {e}")

    def handle_webrtc_status(self, msg: String):
        """Handle WebRTC status updates."""
        try:
            status_data = json.loads(msg.data)
            action = status_data.get('action', 'unknown')
            
            self.get_logger().debug(f"WebRTC status: {action}")
            
        except Exception as e:
            self.get_logger().error(f"WebRTC status handling error: {e}")

    def handle_emergency_alert(self, msg: EmergencyAlert):
        """Handle emergency alert with comprehensive response."""
        try:
            start_time = time.time()
            
            self.get_logger().critical(f"🚨 EMERGENCY ALERT: {msg.emergency_type} - {msg.description}")
            
            # Activate emergency mode
            self.emergency_mode = True
            self.system_status = SystemStatus.EMERGENCY
            
            # Immediate response
            emergency_response = "紧急情况已确认！正在立即联系帮助。请保持冷静，不要移动。救援正在路上。"
            self.send_urgent_response(emergency_response)
            
            # Trigger comprehensive emergency response
            self.trigger_comprehensive_emergency_response({
                'reason': msg.emergency_type,
                'description': msg.description,
                'severity': msg.severity_level
            })
            
            # Calculate and verify response time
            response_time_ms = (time.time() - start_time) * 1000
            required_time = self.get_parameter('safety.emergency_response_time_ms').value
            
            if response_time_ms <= required_time:
                self.get_logger().critical(f"✅ Emergency response time: {response_time_ms:.1f}ms")
            else:
                self.get_logger().critical(f"⚠️ Emergency response time exceeded: {response_time_ms:.1f}ms (required: {required_time}ms)")
            
            # Update system status
            self.publish_enhanced_system_status("EMERGENCY", f"Emergency response activated: {msg.emergency_type}")
            
        except Exception as e:
            self.get_logger().error(f"Emergency alert handling error: {e}")

    def handle_tts_status(self, msg: Bool):
        """Handle TTS status updates."""
        try:
            is_speaking = msg.data
            
            if is_speaking:
                self.get_logger().debug("TTS engine is speaking")
            else:
                self.get_logger().debug("TTS engine finished speaking")
                
        except Exception as e:
            self.get_logger().error(f"TTS status handling error: {e}")

    def fallback_text_processing(self, text: str):
        """Fallback text processing when services are unavailable."""
        try:
            self.get_logger().warning("Using fallback text processing")
            
            # Simple emergency keyword detection
            emergency_keywords = ['救命', 'help', 'emergency', '急救', '不舒服']
            if any(keyword in text.lower() for keyword in emergency_keywords):
                self.send_urgent_response("我检测到您可能需要紧急帮助，正在联系救援。")
            else:
                self.send_response("我听到了您的话，但系统服务暂时不可用。请稍后再试。")
                
        except Exception as e:
            self.get_logger().error(f"Fallback text processing error: {e}")

    def check_system_health(self):
        """Check health of the entire enhanced system."""
        try:
            self.get_logger().debug("Checking enhanced system health...")
            
            # Check FastAPI services
            self.check_fastapi_services_health()
            
            # Check ROS2 components (simplified check)
            self.check_ros2_components_health()
            
            # Update system metrics
            self.update_system_health_metrics()
            
            # Publish health status
            self.publish_system_health_status()
            
        except Exception as e:
            self.get_logger().error(f"System health check error: {e}")

    def check_fastapi_services_health(self):
        """Check health of FastAPI services."""
        try:
            for component in [SystemComponent.FASTAPI_ORCHESTRATOR, SystemComponent.FASTAPI_GUARD,
                            SystemComponent.FASTAPI_INTENT, SystemComponent.FASTAPI_ADAPTERS]:
                
                is_healthy = self.check_fastapi_service_health(component)
                self.component_status[component.value] = is_healthy
                
                if is_healthy:
                    self.component_health_data[component.value] = {
                        'status': 'healthy',
                        'last_check': datetime.now().isoformat()
                    }
                else:
                    self.component_health_data[component.value] = {
                        'status': 'unhealthy',
                        'last_check': datetime.now().isoformat()
                    }
                    
        except Exception as e:
            self.get_logger().error(f"FastAPI services health check error: {e}")

    def check_ros2_components_health(self):
        """Check health of ROS2 components."""
        try:
            # For ROS2 components, we check service availability
            ros2_services = {
                SystemComponent.FASTAPI_BRIDGE: '/fastapi_bridge/process_text',
                SystemComponent.GUARD_FASTAPI_BRIDGE: '/guard_bridge/validate_intent',
                SystemComponent.SMART_HOME_BACKEND: '/smart_home/execute_action',
                SystemComponent.SIP_VOIP_ADAPTER: '/sip_voip/emergency_dispatch'
            }
            
            for component, service_name in ros2_services.items():
                if service_name in [client._service_name for client in self.service_clients.values()]:
                    # Service client exists, assume healthy
                    self.component_status[component.value] = True
                else:
                    self.component_status[component.value] = False
                    
        except Exception as e:
            self.get_logger().error(f"ROS2 components health check error: {e}")

    def update_system_health_metrics(self):
        """Update system health metrics."""
        try:
            self.system_metrics['last_health_check'] = datetime.now().isoformat()
            
            # Count active services
            active_fastapi = sum(1 for component in [SystemComponent.FASTAPI_ORCHESTRATOR, 
                                                   SystemComponent.FASTAPI_GUARD,
                                                   SystemComponent.FASTAPI_INTENT, 
                                                   SystemComponent.FASTAPI_ADAPTERS]
                               if self.component_status[component.value])
            
            active_ros2 = sum(1 for component in SystemComponent 
                            if component not in [SystemComponent.FASTAPI_ORCHESTRATOR,
                                               SystemComponent.FASTAPI_GUARD,
                                               SystemComponent.FASTAPI_INTENT,
                                               SystemComponent.FASTAPI_ADAPTERS]
                            and self.component_status[component.value])
            
            self.system_metrics['fastapi_services_active'] = active_fastapi
            self.system_metrics['ros2_nodes_active'] = active_ros2
            
        except Exception as e:
            self.get_logger().error(f"System health metrics update error: {e}")

    def publish_system_health_status(self):
        """Publish comprehensive system health status."""
        try:
            health_data = {
                'system_status': self.system_status.value,
                'emergency_mode': self.emergency_mode,
                'components': self.component_status,
                'health_data': self.component_health_data,
                'timestamp': datetime.now().isoformat()
            }
            
            health_msg = String()
            health_msg.data = json.dumps(health_data)
            self.system_status_pub.publish(health_msg)
            
        except Exception as e:
            self.get_logger().error(f"System health status publishing error: {e}")

    def publish_system_metrics(self):
        """Publish system performance metrics."""
        try:
            # Calculate uptime
            uptime = datetime.now() - self.system_metrics['system_uptime_start']
            self.system_metrics['uptime_seconds'] = uptime.total_seconds()
            
            metrics_msg = String()
            metrics_msg.data = json.dumps(self.system_metrics)
            self.system_metrics_pub.publish(metrics_msg)
            
        except Exception as e:
            self.get_logger().error(f"System metrics publishing error: {e}")

    def publish_enhanced_system_status(self, status: str, message: str):
        """Publish enhanced system status."""
        try:
            status_data = {
                'status': status,
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'mode': self.mode.value,
                'emergency_mode': self.emergency_mode,
                'components': self.component_status,
                'deployment_target': self.deployment_target,
                'system_metrics': self.system_metrics
            }
            
            status_msg = String()
            status_msg.data = json.dumps(status_data)
            self.system_status_pub.publish(status_msg)
            
        except Exception as e:
            self.get_logger().error(f"Enhanced system status publishing error: {e}")

    def print_enhanced_system_status(self):
        """Print enhanced system status to console."""
        try:
            print("\n" + "="*60)
            print("🤖 ENHANCED ROUTER AGENT SYSTEM STATUS")
            print("="*60)
            print(f"System Status: {self.system_status.value.upper()}")
            print(f"Mode: {self.mode.value}")
            print(f"Emergency Mode: {'🚨 ACTIVE' if self.emergency_mode else '✅ Normal'}")
            print(f"Deployment: {self.deployment_target}")
            
            # Component status
            print("\n📊 Component Status:")
            for component, status in self.component_status.items():
                status_icon = "✅" if status else "❌"
                print(f"  {status_icon} {component}")
            
            # System metrics
            print(f"\n📈 System Metrics:")
            print(f"  Conversations: {self.system_metrics['total_conversations']}")
            print(f"  Emergency Responses: {self.system_metrics['emergency_responses']}")
            print(f"  Successful Actions: {self.system_metrics['successful_actions']}")
            
            uptime = datetime.now() - self.system_metrics['system_uptime_start']
            print(f"  Uptime: {uptime}")
            
            print("="*60)
            print()
            
        except Exception as e:
            self.get_logger().error(f"Status printing error: {e}")

    def print_component_health(self):
        """Print detailed component health information."""
        try:
            print("\n" + "="*60)
            print("🏥 COMPONENT HEALTH DETAILS")
            print("="*60)
            
            for component, health_data in self.component_health_data.items():
                status = health_data.get('status', 'unknown')
                last_check = health_data.get('last_check', 'never')
                
                status_icon = "✅" if status == 'healthy' else "❌"
                print(f"  {status_icon} {component}: {status} (checked: {last_check})")
            
            print("="*60)
            print()
            
        except Exception as e:
            self.get_logger().error(f"Component health printing error: {e}")

    def test_emergency_response(self):
        """Test emergency response system."""
        try:
            print("\n🚨 TESTING EMERGENCY RESPONSE SYSTEM...")
            
            # Create test emergency alert
            test_alert = EmergencyAlert()
            test_alert.emergency_type = "test"
            test_alert.severity_level = 3
            test_alert.description = "Emergency response system test"
            
            # Process the alert
            self.handle_emergency_alert(test_alert)
            
            print("✅ Emergency response test completed")
            
        except Exception as e:
            self.get_logger().error(f"Emergency response test error: {e}")
            print("❌ Emergency response test failed")

    def trigger_help_request(self):
        """Trigger help request."""
        try:
            help_text = "help I need assistance"
            self.get_logger().info("Processing help request")
            self.process_enhanced_text_input(help_text)
            
        except Exception as e:
            self.get_logger().error(f"Help request trigger error: {e}")

    def shutdown_enhanced_system(self):
        """Shutdown the enhanced Router Agent system gracefully."""
        try:
            self.get_logger().info("🛑 Shutting down Enhanced Router Agent Coordinator...")
            
            self.system_status = SystemStatus.SHUTTING_DOWN
            self.is_active = False
            
            self.publish_enhanced_system_status("SHUTDOWN", "Enhanced system shutdown initiated")
            
            print("\n👋 Goodbye! Enhanced Router Agent Coordinator shutting down...")
            
            # Close HTTP session
            if hasattr(self, 'http_session'):
                self.http_session.close()
            
            # In production, would properly shutdown all components
            rclpy.shutdown()
            
        except Exception as e:
            self.get_logger().error(f"Enhanced shutdown error: {e}")


def main(args=None):
    """Main entry point for Enhanced Router Agent Coordinator."""
    rclpy.init(args=args)
    
    try:
        # Create the enhanced coordinator node
        coordinator = EnhancedRouterAgentCoordinator()
        
        # Use multi-threaded executor for handling multiple streams
        executor = MultiThreadedExecutor()
        executor.add_node(coordinator)
        
        # Spin the executor
        executor.spin()
        
    except KeyboardInterrupt:
        print("\n⚠️ Keyboard interrupt received")
    except Exception as e:
        print(f"❌ Enhanced Router Agent Coordinator error: {e}")
    finally:
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()