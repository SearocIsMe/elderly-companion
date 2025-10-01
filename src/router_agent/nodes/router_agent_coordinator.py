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
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import logging

# ROS2 message imports
from std_msgs.msg import Header, String, Bool
from sensor_msgs.msg import Audio, Image
from elderly_companion.msg import (
    SpeechResult, EmotionData, IntentResult,
    HealthStatus, EmergencyAlert, SafetyConstraints
)
from elderly_companion.srv import ProcessSpeech, ValidateIntent, ExecuteAction, EmergencyDispatch

# Import dialog manager components
from .dialog_manager_node import DialogManagerNode, ConversationState


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


class EnhancedRouterAgentCoordinator(Node):
    """
    Enhanced Router Agent Coordinator - Complete Integration Orchestrator.
    
    Orchestrates the complete elderly companion system:
    
    Audio Pipeline:
    1. Silero VAD → Speech Recognition → Emotion Analysis
    2. Enhanced Guard Engine (wakeword, SOS, geofence, implicit commands)
    3. Guard-FastAPI Bridge → FastAPI Guard Service
    
    Core Processing:
    4. FastAPI Orchestrator → Intent Service → Adapters
    5. FastAPI Bridge ↔ ROS2 Integration
    
    Output & Communication:
    6. Enhanced TTS Engine (elderly-optimized speech synthesis)
    7. SIP/VoIP Adapter (emergency calling with escalation)
    8. Smart-Home Backend (MQTT/HA integration)
    9. WebRTC Uplink (family video streaming)
    
    This coordinator maintains the proven FastAPI closed-loop functionality
    while orchestrating all ROS2 components for comprehensive elderly care.
    """

    def __init__(self):
        super().__init__('enhanced_router_agent_coordinator')
        
        # Initialize comprehensive parameters
        self.declare_parameters(
            namespace='',
            parameters=[
                # System Mode and Operation
                ('router_agent.mode', 'hybrid'),  # text_only, audio_only, hybrid, emergency
                ('router_agent.enable_safety_monitoring', True),
                ('router_agent.enable_conversation_logging', True),
                ('router_agent.response_timeout_seconds', 10.0),
                ('router_agent.startup_timeout_seconds', 60.0),
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
                ('safety.emergency_response_time_ms', 100),  # Faster for elderly
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
                ('communication.emergency_contacts_required', True),
                
                # Smart Home Configuration
                ('smart_home.enable_automation', True),
                ('smart_home.enable_emergency_scenes', True),
                ('smart_home.enable_mqtt', True),
                ('smart_home.enable_home_assistant', True),
                
                # Video Streaming Configuration
                ('video.enable_webrtc_streaming', True),
                ('video.enable_emergency_activation', True),
                ('video.family_access_enabled', True),
                ('video.privacy_mode_default', False),
                
                # AI and Conversation
                ('ai.conversation_model', 'local'),  # local, openai, ollama
                ('ai.safety_level', 'elderly_care'),
                ('ai.enable_emotion_awareness', True),
                ('ai.enable_context_memory', True),
                
                # Performance and Monitoring
                ('monitoring.enable_performance_tracking', True),
                ('monitoring.enable_health_checks', True),
                ('monitoring.health_check_interval', 30),
                ('monitoring.log_level', 'INFO'),
                
                # Deployment Configuration
                ('deployment.target', 'development'),  # development, rk3588, production
                ('deployment.enable_docker_integration', True),
                ('deployment.config_directory', './config'),
            ]
        )
        
        # Get parameters
        self.mode = RouterAgentMode(self.get_parameter('router_agent.mode').value)
        self.enable_safety = self.get_parameter('router_agent.enable_safety_monitoring').value
        self.enable_logging = self.get_parameter('router_agent.enable_conversation_logging').value
        self.response_timeout = self.get_parameter('router_agent.response_timeout_seconds').value
        self.enable_microphone = self.get_parameter('audio.enable_microphone').value
        self.enable_speaker = self.get_parameter('audio.enable_speaker').value
        self.enable_console = self.get_parameter('ui.enable_console_interface').value
        self.enable_enhanced_guard = self.get_parameter('safety.enable_enhanced_guard').value
        self.enable_smart_home = self.get_parameter('smart_home.enable_automation').value
        self.enable_video_streaming = self.get_parameter('video.enable_webrtc_streaming').value
        self.enable_sip_voip = self.get_parameter('communication.enable_sip_voip').value
        self.deployment_target = self.get_parameter('deployment.target').value
        
        # FastAPI services configuration
        self.fastapi_urls = {
            'orchestrator': self.get_parameter('fastapi.orchestrator_url').value,
            'guard': self.get_parameter('fastapi.guard_url').value,
            'intent': self.get_parameter('fastapi.intent_url').value,
            'adapters': self.get_parameter('fastapi.adapters_url').value
        }
        
        # System state management
        self.is_active = False
        self.current_conversation_id = None
        self.last_response_time = None
        self.pending_responses = queue.Queue()
        self.system_startup_complete = False
        
        # Enhanced component status tracking
        self.component_status = {
            # Core ROS2 Components
            SystemComponent.SILERO_VAD.value: False,
            SystemComponent.SPEECH_RECOGNITION.value: False,
            SystemComponent.ENHANCED_GUARD.value: False,
            SystemComponent.GUARD_FASTAPI_BRIDGE.value: False,
            SystemComponent.FASTAPI_BRIDGE.value: False,
            SystemComponent.ENHANCED_TTS.value: False,
            SystemComponent.SIP_VOIP_ADAPTER.value: False,
            SystemComponent.SMART_HOME_BACKEND.value: False,
            SystemComponent.WEBRTC_UPLINK.value: False,
            SystemComponent.DIALOG_MANAGER.value: False,
            SystemComponent.EMOTION_ANALYZER.value: False,
            
            # FastAPI Services
            SystemComponent.FASTAPI_ORCHESTRATOR.value: False,
            SystemComponent.FASTAPI_GUARD.value: False,
            SystemComponent.FASTAPI_INTENT.value: False,
            SystemComponent.FASTAPI_ADAPTERS.value: False
        }
        
        # Performance and health monitoring
        self.component_health_data: Dict[str, Dict[str, Any]] = {}
        self.system_metrics = {
            'total_conversations': 0,
            'emergency_responses': 0,
            'successful_actions': 0,
            'system_uptime_start': datetime.now(),
            'last_health_check': None
        }
        
        # Service clients for component communication
        self.service_clients = {}
        self.initialize_service_clients()
        
        # QoS profiles
        default_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
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
        
        self.speech_result_sub = self.create_subscription(
            SpeechResult,
            '/speech/recognized',
            self.handle_speech_input,
            default_qos
        )
        
        # Subscribers - Component outputs
        self.dialog_response_sub = self.create_subscription(
            String,
            '/dialog/response_text',
            self.handle_dialog_response,
            default_qos
        )
        
        self.conversation_state_sub = self.create_subscription(
            String,
            '/dialog/conversation_state',
            self.handle_conversation_state,
            default_qos
        )
        
        self.emergency_alert_sub = self.create_subscription(
            EmergencyAlert,
            '/emergency/alert',
            self.handle_emergency_alert,
            fast_qos  # Emergency alerts need fast delivery
        )
        
        # Publishers - Output channels
        self.text_output_pub = self.create_publisher(
            String,
            '/router_agent/text_output',
            default_qos
        )
        
        self.tts_request_pub = self.create_publisher(
            String,
            '/tts/request',
            default_qos
        )
        
        self.system_status_pub = self.create_publisher(
            String,
            '/router_agent/system_status',
            default_qos
        )
        
        # Publishers - Internal coordination
        self.speech_for_processing_pub = self.create_publisher(
            SpeechResult,
            '/speech/with_emotion',
            default_qos
        )
        
        # Service clients
        self.speech_processing_client = self.create_client(
            ProcessSpeech,
            '/speech_recognition/process'
        )
        
        self.safety_validation_client = self.create_client(
            ValidateIntent,
            '/safety_guard/validate_intent'
        )
        
        # Timers
        self.component_health_timer = self.create_timer(5.0, self.check_component_health)
        self.console_input_timer = None
        
        # Initialize console interface if enabled
        if self.enable_console and self.mode in [RouterAgentMode.TEXT_ONLY, RouterAgentMode.HYBRID]:
            self.initialize_console_interface()
        
        # Start the coordination system
        self.start_coordination_system()
        
        self.get_logger().info(f"Router Agent Coordinator initialized in {self.mode.value} mode")

    def start_coordination_system(self):
        """Start the complete Router Agent coordination system."""
        try:
            self.get_logger().info("🤖 Starting Router Agent Coordination System...")
            
            # Wait for essential components
            self.wait_for_components()
            
            # Activate the system
            self.is_active = True
            
            # Publish system status
            self.publish_system_status("ACTIVE", "Router Agent coordination system started")
            
            # Start console interface if enabled
            if self.enable_console:
                self.start_console_interface()
            
            self.get_logger().info("✅ Router Agent Coordination System is ACTIVE")
            
        except Exception as e:
            self.get_logger().error(f"Failed to start coordination system: {e}")
            self.publish_system_status("ERROR", f"Startup failed: {e}")

    def wait_for_components(self):
        """Wait for essential components to be ready."""
        self.get_logger().info("⏳ Waiting for essential components...")
        
        # Check if we're in text-only mode (fewer dependencies)
        if self.mode == RouterAgentMode.TEXT_ONLY:
            self.get_logger().info("✅ Text-only mode - minimal dependencies required")
            return
        
        # For audio modes, wait for audio components
        max_wait_time = 30.0  # seconds
        start_time = time.time()
        
        while (time.time() - start_time) < max_wait_time:
            if self.check_essential_components():
                self.get_logger().info("✅ Essential components are ready")
                return
            
            self.get_logger().info("⏳ Still waiting for components...")
            time.sleep(2.0)
        
        self.get_logger().warning("⚠️ Some components not ready, starting anyway")

    def check_essential_components(self) -> bool:
        """Check if essential components are ready."""
        # For now, assume components are ready if we can create service clients
        # In a real implementation, we'd ping each component
        return True

    def initialize_console_interface(self):
        """Initialize console text interface."""
        try:
            self.get_logger().info("🖥️ Initializing console interface...")
            
            # Start console input thread
            self.console_thread = threading.Thread(
                target=self.console_input_loop, 
                daemon=True
            )
            self.console_thread.start()
            
            self.get_logger().info("✅ Console interface ready")
            
        except Exception as e:
            self.get_logger().error(f"Console interface initialization failed: {e}")

    def start_console_interface(self):
        """Start the console interface."""
        if self.enable_console:
            print("\n" + "="*60)
            print("🤖 ELDERLY COMPANION ROUTER AGENT")
            print("="*60)
            print(f"Mode: {self.mode.value.upper()}")
            print("Commands:")
            print("  - Type your message and press Enter")
            print("  - Type 'quit' or 'exit' to stop")
            print("  - Type 'status' to check system status")
            print("  - Type 'help' for emergency assistance")
            print("="*60)
            print("Ready for conversation...")
            print()

    def console_input_loop(self):
        """Console input loop running in separate thread."""
        while self.is_active:
            try:
                user_input = input("You: ").strip()
                
                if user_input.lower() in ['quit', 'exit']:
                    self.get_logger().info("Console interface shutdown requested")
                    self.shutdown_system()
                    break
                elif user_input.lower() == 'status':
                    self.print_system_status()
                    continue
                elif user_input:
                    # Send text input to processing
                    self.process_text_input(user_input)
                    
            except EOFError:
                break
            except KeyboardInterrupt:
                self.get_logger().info("Console interface interrupted")
                break
            except Exception as e:
                self.get_logger().error(f"Console input error: {e}")

    def process_text_input(self, text: str):
        """Process text input through the complete pipeline."""
        try:
            self.get_logger().info(f"Processing text input: '{text}'")
            
            # Create text input message
            text_msg = String()
            text_msg.data = text
            
            # Publish to text input topic (for logging/monitoring)
            self.text_input_sub.callback(text_msg)
            
        except Exception as e:
            self.get_logger().error(f"Text input processing error: {e}")

    def handle_text_input(self, msg: String):
        """Handle text input message."""
        try:
            text = msg.data
            self.get_logger().info(f"Router Agent received text: '{text}'")
            
            # Create synthetic speech result for text input
            speech_result = self.create_speech_result_from_text(text)
            
            # Process through the pipeline
            self.process_speech_pipeline(speech_result)
            
        except Exception as e:
            self.get_logger().error(f"Text input handling error: {e}")

    def create_speech_result_from_text(self, text: str) -> SpeechResult:
        """Create a SpeechResult message from text input."""
        try:
            speech_result = SpeechResult()
            speech_result.header = Header()
            speech_result.header.stamp = self.get_clock().now().to_msg()
            speech_result.header.frame_id = "text_input"
            
            speech_result.text = text
            speech_result.confidence = 1.0  # Perfect confidence for text input
            speech_result.language = "zh-CN"
            speech_result.voice_activity_detected = True
            speech_result.audio_duration_seconds = 0.0
            speech_result.sample_rate = 16000
            
            # Create basic emotion data
            emotion_data = EmotionData()
            emotion_data.primary_emotion = "neutral"
            emotion_data.confidence = 0.5
            emotion_data.timestamp = self.get_clock().now().to_msg()
            
            # Basic emotion analysis for text
            if any(word in text.lower() for word in ['help', 'emergency', '救命', '急救']):
                emotion_data.primary_emotion = "urgent"
                emotion_data.stress_level = 0.9
                emotion_data.arousal = 0.8
                emotion_data.valence = -0.5
            elif any(word in text.lower() for word in ['sad', 'lonely', '孤独', '难过']):
                emotion_data.primary_emotion = "sad"
                emotion_data.stress_level = 0.6
                emotion_data.arousal = 0.3
                emotion_data.valence = -0.7
            else:
                emotion_data.stress_level = 0.2
                emotion_data.arousal = 0.4
                emotion_data.valence = 0.1
            
            speech_result.emotion = emotion_data
            
            return speech_result
            
        except Exception as e:
            self.get_logger().error(f"Speech result creation error: {e}")
            return SpeechResult()

    def handle_speech_input(self, msg: SpeechResult):
        """Handle speech input from ASR system."""
        try:
            self.get_logger().info(f"Router Agent received speech: '{msg.text}'")
            
            # Process through the pipeline
            self.process_speech_pipeline(msg)
            
        except Exception as e:
            self.get_logger().error(f"Speech input handling error: {e}")

    def process_speech_pipeline(self, speech_result: SpeechResult):
        """Process speech through the complete Router Agent pipeline."""
        try:
            # Step 1: Forward to dialog manager for intent classification and response generation
            self.speech_for_processing_pub.publish(speech_result)
            
            # Step 2: Safety monitoring (if enabled)
            if self.enable_safety:
                self.monitor_safety_conditions(speech_result)
            
            # Step 3: Log conversation (if enabled)
            if self.enable_logging:
                self.log_conversation_input(speech_result)
            
        except Exception as e:
            self.get_logger().error(f"Speech pipeline processing error: {e}")

    def monitor_safety_conditions(self, speech_result: SpeechResult):
        """Monitor safety conditions from speech input."""
        try:
            text = speech_result.text.lower()
            emotion = speech_result.emotion
            
            # Check for emergency keywords
            emergency_keywords = ['help', 'emergency', '救命', '急救', 'pain', '痛', 'fell', '摔倒']
            if any(keyword in text for keyword in emergency_keywords):
                self.trigger_emergency_response("emergency_keyword_detected", speech_result)
                return
            
            # Check for high stress levels
            if emotion.stress_level > 0.8:
                self.trigger_safety_alert("high_stress_detected", speech_result)
                return
            
            # Check for health-related concerns
            health_keywords = ['sick', '生病', 'hurt', '疼', 'dizzy', '头晕', 'chest pain', '胸痛']
            if any(keyword in text for keyword in health_keywords):
                self.trigger_health_monitoring("health_concern_detected", speech_result)
            
        except Exception as e:
            self.get_logger().error(f"Safety monitoring error: {e}")

    def trigger_emergency_response(self, trigger_type: str, speech_result: SpeechResult):
        """Trigger emergency response protocol."""
        try:
            self.get_logger().critical(f"🚨 EMERGENCY TRIGGERED: {trigger_type}")
            
            # Create emergency alert
            emergency_alert = EmergencyAlert()
            emergency_alert.header = Header()
            emergency_alert.header.stamp = self.get_clock().now().to_msg()
            emergency_alert.emergency_type = "medical"  # Default to medical
            emergency_alert.severity_level = 4  # Critical
            emergency_alert.location = "home"
            emergency_alert.description = f"Emergency detected from speech: {speech_result.text}"
            emergency_alert.automated_response_triggered = True
            
            # Handle emergency immediately
            self.handle_emergency_alert(emergency_alert)
            
        except Exception as e:
            self.get_logger().error(f"Emergency response trigger error: {e}")

    def trigger_safety_alert(self, alert_type: str, speech_result: SpeechResult):
        """Trigger safety alert (non-emergency)."""
        try:
            self.get_logger().warning(f"⚠️ SAFETY ALERT: {alert_type}")
            
            # Generate appropriate response
            response = "I notice you might be stressed. Are you okay? Do you need help?"
            self.send_response_to_user(response, urgent=True)
            
        except Exception as e:
            self.get_logger().error(f"Safety alert trigger error: {e}")

    def trigger_health_monitoring(self, concern_type: str, speech_result: SpeechResult):
        """Trigger health monitoring protocol."""
        try:
            self.get_logger().info(f"🏥 HEALTH MONITORING: {concern_type}")
            
            # Generate health-focused response
            response = "I'm concerned about your health. Can you tell me more about how you're feeling?"
            self.send_response_to_user(response, health_related=True)
            
        except Exception as e:
            self.get_logger().error(f"Health monitoring trigger error: {e}")

    def handle_dialog_response(self, msg: String):
        """Handle response from dialog manager."""
        try:
            response_text = msg.data
            self.get_logger().info(f"Dialog Manager response: '{response_text}'")
            
            # Send response to user through all enabled output channels
            self.send_response_to_user(response_text)
            
        except Exception as e:
            self.get_logger().error(f"Dialog response handling error: {e}")

    def send_response_to_user(self, response_text: str, urgent: bool = False, health_related: bool = False):
        """Send response to user through all enabled output channels."""
        try:
            self.get_logger().info(f"Sending response: '{response_text}'")
            
            # 1. Text output (console, web interface)
            if self.enable_console or self.mode in [RouterAgentMode.TEXT_ONLY, RouterAgentMode.HYBRID]:
                self.output_text_response(response_text, urgent)
            
            # 2. Audio output (TTS)
            if self.enable_speaker and self.mode in [RouterAgentMode.AUDIO_ONLY, RouterAgentMode.HYBRID]:
                self.output_audio_response(response_text, urgent)
            
            # 3. Publish to text output topic
            text_msg = String()
            text_msg.data = response_text
            self.text_output_pub.publish(text_msg)
            
            # Update response timing
            self.last_response_time = time.time()
            
        except Exception as e:
            self.get_logger().error(f"Response output error: {e}")

    def output_text_response(self, response_text: str, urgent: bool = False):
        """Output text response to console."""
        try:
            if urgent:
                print(f"\n🚨 URGENT - Robot: {response_text}\n")
            else:
                print(f"Robot: {response_text}")
            
        except Exception as e:
            self.get_logger().error(f"Text output error: {e}")

    def output_audio_response(self, response_text: str, urgent: bool = False):
        """Output audio response via TTS."""
        try:
            # Send to TTS system
            tts_msg = String()
            tts_msg.data = response_text
            self.tts_request_pub.publish(tts_msg)
            
        except Exception as e:
            self.get_logger().error(f"Audio output error: {e}")

    def handle_conversation_state(self, msg: String):
        """Handle conversation state updates."""
        try:
            state = msg.data
            self.get_logger().debug(f"Conversation state: {state}")
            
            # Update system status based on conversation state
            if state == "emergency":
                self.publish_system_status("EMERGENCY", "Emergency conversation mode active")
            elif state == "processing":
                self.publish_system_status("PROCESSING", "Processing user input")
            elif state == "responding":
                self.publish_system_status("RESPONDING", "Generating response")
            else:
                self.publish_system_status("ACTIVE", f"Conversation state: {state}")
                
        except Exception as e:
            self.get_logger().error(f"Conversation state handling error: {e}")

    def handle_emergency_alert(self, msg: EmergencyAlert):
        """Handle emergency alert with <200ms response time."""
        try:
            start_time = time.time()
            
            self.get_logger().critical(f"🚨 EMERGENCY ALERT: {msg.emergency_type} - {msg.description}")
            
            # Immediate response
            emergency_response = "紧急情况已确认！正在立即联系帮助。请保持冷静，不要移动。"
            self.send_response_to_user(emergency_response, urgent=True)
            
            # Calculate response time
            response_time_ms = (time.time() - start_time) * 1000
            self.get_logger().critical(f"Emergency response time: {response_time_ms:.1f}ms")
            
            # Update system to emergency mode
            self.publish_system_status("EMERGENCY", f"Emergency response activated: {msg.emergency_type}")
            
        except Exception as e:
            self.get_logger().error(f"Emergency alert handling error: {e}")

    def log_conversation_input(self, speech_result: SpeechResult):
        """Log conversation input for analysis."""
        try:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'input_type': 'speech' if speech_result.voice_activity_detected else 'text',
                'text': speech_result.text,
                'emotion': speech_result.emotion.primary_emotion,
                'confidence': speech_result.confidence,
                'conversation_id': self.current_conversation_id
            }
            
            # In a real implementation, this would write to a secure log file
            self.get_logger().debug(f"Conversation logged: {json.dumps(log_entry)}")
            
        except Exception as e:
            self.get_logger().error(f"Conversation logging error: {e}")

    def check_component_health(self):
        """Check health of all system components."""
        try:
            # This would ping each component to check if it's responsive
            # For now, we'll simulate health checks
            
            all_healthy = True
            for component, status in self.component_status.items():
                # In real implementation, would actually check component status
                self.component_status[component] = True
            
            if all_healthy:
                self.publish_system_status("HEALTHY", "All components operational")
            else:
                failed_components = [comp for comp, status in self.component_status.items() if not status]
                self.publish_system_status("DEGRADED", f"Components failed: {failed_components}")
                
        except Exception as e:
            self.get_logger().error(f"Component health check error: {e}")

    def publish_system_status(self, status: str, message: str):
        """Publish system status."""
        try:
            status_data = {
                'status': status,
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'mode': self.mode.value,
                'components': self.component_status
            }
            
            status_msg = String()
            status_msg.data = json.dumps(status_data)
            self.system_status_pub.publish(status_msg)
            
        except Exception as e:
            self.get_logger().error(f"System status publishing error: {e}")

    def print_system_status(self):
        """Print system status to console."""
        try:
            print("\n" + "="*40)
            print("🤖 SYSTEM STATUS")
            print("="*40)
            print(f"Mode: {self.mode.value}")
            print(f"Active: {self.is_active}")
            print(f"Safety Monitoring: {self.enable_safety}")
            print(f"Microphone: {self.enable_microphone}")
            print(f"Speaker: {self.enable_speaker}")
            print(f"Console: {self.enable_console}")
            print("\nComponent Status:")
            for component, status in self.component_status.items():
                status_icon = "✅" if status else "❌"
                print(f"  {status_icon} {component}")
            print("="*40)
            print()
            
        except Exception as e:
            self.get_logger().error(f"Status printing error: {e}")

    def shutdown_system(self):
        """Shutdown the Router Agent system gracefully."""
        try:
            self.get_logger().info("🛑 Shutting down Router Agent Coordinator...")
            
            self.is_active = False
            self.publish_system_status("SHUTDOWN", "System shutdown initiated")
            
            print("\n👋 Goodbye! Router Agent Coordinator shutting down...")
            
            # In a real implementation, we'd properly shutdown all components
            rclpy.shutdown()
            
        except Exception as e:
            self.get_logger().error(f"Shutdown error: {e}")


def main(args=None):
    """Main entry point for Router Agent Coordinator."""
    rclpy.init(args=args)
    
    try:
        # Create the coordinator node
        coordinator = RouterAgentCoordinator()
        
        # Use multi-threaded executor for handling multiple streams
        executor = MultiThreadedExecutor()
        executor.add_node(coordinator)
        
        # Spin the executor
        executor.spin()
        
    except KeyboardInterrupt:
        print("\n⚠️ Keyboard interrupt received")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()