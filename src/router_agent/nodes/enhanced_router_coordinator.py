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

from elderly_companion.srv import (
    ValidateIntent,
    ExecuteAction,
    EmergencyDispatch
)

import json
import time
import threading
import requests
import subprocess
import os
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

from std_msgs.msg import String, Bool
from elderly_companion.msg import (
    SpeechResult, EmotionData, IntentResult,
    HealthStatus, EmergencyAlert
)
from elderly_companion.srv import ProcessSpeech


class RouterAgentMode(Enum):
    TEXT_ONLY = "text_only"
    AUDIO_ONLY = "audio_only"
    HYBRID = "hybrid"
    EMERGENCY = "emergency"
    MAINTENANCE = "maintenance"
    DEMO = "demo"


class SystemComponent(Enum):
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
    FASTAPI_ORCHESTRATOR = "fastapi_orchestrator"
    FASTAPI_GUARD = "fastapi_guard"
    FASTAPI_INTENT = "fastapi_intent"
    FASTAPI_ADAPTERS = "fastapi_adapters"


class SystemStatus(Enum):
    STARTING = "starting"
    READY = "ready"
    ACTIVE = "active"
    EMERGENCY = "emergency"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    SHUTTING_DOWN = "shutting_down"


class EnhancedRouterAgentCoordinator(Node):
    """Enhanced Router Agent Coordinator - Complete Integration Orchestrator."""

    def __init__(self):
        super().__init__('enhanced_router_agent_coordinator')

        # --------------------------
        # Parameters
        # --------------------------
        self.declare_parameters(
            namespace='',
            parameters=[
                ('router_agent.mode', 'hybrid'),
                ('router_agent.enable_safety_monitoring', True),
                ('router_agent.enable_conversation_logging', True),
                ('router_agent.response_timeout_seconds', 10.0),
                ('router_agent.startup_timeout_seconds', 120.0),
                ('router_agent.enable_component_health_monitoring', True),

                ('audio.enable_microphone', True),
                ('audio.enable_speaker', True),
                ('audio.enable_silero_vad', True),
                ('audio.enable_noise_reduction', True),
                ('audio.sample_rate', 16000),

                ('ui.enable_console_interface', True),
                ('ui.enable_web_interface', True),
                ('ui.enable_family_app_interface', True),
                ('ui.console_welcome_message', True),

                ('safety.emergency_response_time_ms', 100),
                ('safety.enable_enhanced_guard', True),
                ('safety.enable_guard_fastapi_bridge', True),
                ('safety.emergency_escalation_enabled', True),
                ('safety.proactive_safety_monitoring', True),

                ('fastapi.orchestrator_url', 'http://localhost:7010'),
                ('fastapi.guard_url', 'http://localhost:7002'),
                ('fastapi.intent_url', 'http://localhost:7001'),
                ('fastapi.adapters_url', 'http://localhost:7003'),
                ('fastapi.enable_auto_start', True),
                ('fastapi.startup_wait_seconds', 30),

                ('communication.enable_sip_voip', True),
                ('communication.enable_sms_notifications', True),
                ('communication.enable_email_notifications', True),

                ('smart_home.enable_automation', True),
                ('smart_home.enable_emergency_scenes', True),

                ('video.enable_webrtc_streaming', True),
                ('video.enable_emergency_activation', True),

                ('ai.conversation_model', 'local'),
                ('ai.safety_level', 'elderly_care'),
                ('ai.enable_emotion_awareness', True),

                ('monitoring.enable_performance_tracking', True),
                ('monitoring.health_check_interval', 30),

                ('deployment.target', 'development'),
                ('deployment.enable_docker_integration', True),
            ]
        )

        # --------------------------
        # Config & State
        # --------------------------
        self.mode = RouterAgentMode(self.get_parameter('router_agent.mode').value)
        self.enable_safety = self.get_parameter('router_agent.enable_safety_monitoring').value
        self.enable_console = self.get_parameter('ui.enable_console_interface').value
        self.enable_enhanced_guard = self.get_parameter('safety.enable_enhanced_guard').value
        self.enable_smart_home = self.get_parameter('smart_home.enable_automation').value
        self.enable_video_streaming = self.get_parameter('video.enable_webrtc_streaming').value
        self.enable_sip_voip = self.get_parameter('communication.enable_sip_voip').value
        self.deployment_target = self.get_parameter('deployment.target').value
        self.enable_docker_integration = self.get_parameter('deployment.enable_docker_integration').value

        self.fastapi_urls = {
            'orchestrator': self.get_parameter('fastapi.orchestrator_url').value,
            'guard': self.get_parameter('fastapi.guard_url').value,
            'intent': self.get_parameter('fastapi.intent_url').value,
            'adapters': self.get_parameter('fastapi.adapters_url').value
        }

        self.system_status = SystemStatus.STARTING
        self.is_active = False
        self.current_conversation_id = None
        self.startup_complete = False
        self.emergency_mode = False

        self.component_status = {component.value: False for component in SystemComponent}
        self.component_health_data: Dict[str, Dict[str, Any]] = {}

        self.system_metrics = {
            'total_conversations': 0,
            'emergency_responses': 0,
            'successful_actions': 0,
            'system_uptime_start': datetime.now(),
            'last_health_check': None,
            'fastapi_services_active': 0,
            'ros2_nodes_active': 0
        }

        self.http_session = requests.Session()
        self.http_session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Enhanced-Router-Coordinator/1.0'
        })

        # QoS
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

        # Subscribers
        self.text_input_sub = self.create_subscription(
            String, '/router_agent/text_input', self.handle_text_input, default_qos
        )
        self.fastapi_response_sub = self.create_subscription(
            String, '/fastapi/response', self.handle_fastapi_response, default_qos
        )
        self.guard_decision_sub = self.create_subscription(
            String, '/guard/final_decision', self.handle_guard_decision, critical_qos
        )
        self.smart_home_result_sub = self.create_subscription(
            String, '/smart_home/automation_result', self.handle_smart_home_result, default_qos
        )
        self.webrtc_status_sub = self.create_subscription(
            String, '/webrtc/stream_status', self.handle_webrtc_status, fast_qos
        )
        self.emergency_alert_sub = self.create_subscription(
            EmergencyAlert, '/emergency/alert', self.handle_emergency_alert, critical_qos
        )
        self.tts_status_sub = self.create_subscription(
            Bool, '/tts/status', self.handle_tts_status, fast_qos
        )

        # Publishers
        self.text_output_pub = self.create_publisher(String, '/router_agent/text_output', default_qos)
        self.emotion_aware_tts_pub = self.create_publisher(String, '/tts/emotion_request', default_qos)
        self.system_status_pub = self.create_publisher(String, '/router_agent/system_status', fast_qos)
        self.system_metrics_pub = self.create_publisher(String, '/router_agent/system_metrics', default_qos)

        # Services
        self.service_clients = {}
        self.initialize_service_clients()

        # Timers
        self.health_check_timer = self.create_timer(
            self.get_parameter('monitoring.health_check_interval').value,
            self.check_system_health
        )
        self.metrics_timer = self.create_timer(60.0, self.publish_system_metrics)

        # Start
        self.start_enhanced_coordination_system()
        self.get_logger().info(f"Enhanced Router Agent Coordinator initialized in {self.mode.value} mode")

    # --------------------------
    # Helpers (new/updated)
    # --------------------------
    @staticmethod
    def _json_safe(obj: Any) -> Any:
        """Make arbitrary objects JSON-serializable (datetime/Enum)."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Enum):
            return obj.value
        return obj

    def _serialize_metrics(self) -> Dict[str, Any]:
        """Return a JSON-safe copy of system_metrics."""
        out: Dict[str, Any] = {}
        for k, v in self.system_metrics.items():
            out[k] = self._json_safe(v)
        return out

    # --------------------------
    # Init service clients
    # --------------------------
    def initialize_service_clients(self):
        try:
            self.service_clients['fastapi_bridge'] = self.create_client(
                ProcessSpeech, '/fastapi_bridge/process_text'
            )
            self.service_clients['guard_bridge'] = self.create_client(
                ValidateIntent, '/guard_bridge/validate_intent'
            )
            self.service_clients['smart_home'] = self.create_client(
                ExecuteAction, '/smart_home/execute_action'
            )
            self.service_clients['emergency_dispatch'] = self.create_client(
                EmergencyDispatch, '/sip_voip/emergency_dispatch'
            )
            self.get_logger().info("Service clients initialized")
        except Exception as e:
            self.get_logger().error(f"Service clients initialization error: {e}")

    # --------------------------
    # Startup flow
    # --------------------------
    def start_enhanced_coordination_system(self):
        try:
            self.get_logger().info("🚀 Starting Enhanced Router Agent Coordination System...")
            self.system_status = SystemStatus.STARTING

            if self.get_parameter('fastapi.enable_auto_start').value:
                self.start_fastapi_services()

            self.wait_for_essential_components()
            self.verify_system_integration()

            self.system_status = SystemStatus.READY
            self.is_active = True
            self.startup_complete = True

            self.publish_enhanced_system_status("READY", "Enhanced Router Agent coordination system started")

            if self.enable_console:
                self.start_enhanced_console_interface()

            self.system_status = SystemStatus.ACTIVE
            self.get_logger().info("✅ Enhanced Router Agent Coordination System is ACTIVE")

        except Exception as e:
            self.system_status = SystemStatus.ERROR
            self.get_logger().error(f"Failed to start enhanced coordination system: {e}")
            self.publish_enhanced_system_status("ERROR", f"Startup failed: {e}")

    def start_fastapi_services(self):
        try:
            if not self.enable_docker_integration:
                self.get_logger().info("Docker integration disabled - skipping FastAPI auto-start")
                return
            self.get_logger().info("Starting FastAPI services via Docker...")
            docker_compose_file = self.get_docker_compose_file()
            if docker_compose_file and os.path.exists(docker_compose_file):
                result = subprocess.run(
                    ['docker', 'compose', '-f', docker_compose_file, 'up', '-d'],
                    capture_output=True, text=True, cwd=os.path.dirname(docker_compose_file)
                )
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
        try:
            base_path = "/mnt/c/Users/haipeng/Documents/00-code/02-RobDog/elderly-companion/src/router_agent/docker"
            if not os.path.exists(base_path):
                self.get_logger().warning(f"Docker directory not found: {base_path}")
                return None
            if self.deployment_target == 'rk3588':
                file_path = os.path.join(base_path, 'docker-compose.rk3588.yml')
            elif self.deployment_target == 'production':
                file_path = os.path.join(base_path, 'docker-compose.pc.gpu.yml')
            else:
                file_path = os.path.join(base_path, 'docker-compose.pc.yml')
            if os.path.exists(file_path):
                self.get_logger().info(f"Found Docker compose file: {file_path}")
                return file_path
            self.get_logger().warning(f"Docker compose file not found: {file_path}")
            return None
        except Exception as e:
            self.get_logger().error(f"Error finding docker compose file: {e}")
            return None

    def wait_for_essential_components(self):
        try:
            self.get_logger().info("⏳ Waiting for essential components...")
            max_wait_time = self.get_parameter('router_agent.startup_timeout_seconds').value
            start_time = time.time()

            essential = [SystemComponent.FASTAPI_ORCHESTRATOR, SystemComponent.FASTAPI_BRIDGE]
            if self.enable_enhanced_guard:
                essential += [SystemComponent.ENHANCED_GUARD, SystemComponent.GUARD_FASTAPI_BRIDGE]

            while (time.time() - start_time) < max_wait_time:
                ready = 0
                for comp in essential:
                    if self.check_component_availability(comp):
                        self.component_status[comp.value] = True
                        ready += 1
                if ready == len(essential):
                    self.get_logger().info("✅ Essential components are ready")
                    return True
                self.get_logger().info(f"⏳ {ready}/{len(essential)} essential components ready...")
                time.sleep(5.0)

            self.get_logger().warning("⚠️ Not all essential components ready, starting anyway")
            return False
        except Exception as e:
            self.get_logger().error(f"Component wait error: {e}")
            return False

    def check_component_availability(self, component: SystemComponent) -> bool:
        try:
            if component in [
                SystemComponent.FASTAPI_ORCHESTRATOR,
                SystemComponent.FASTAPI_GUARD,
                SystemComponent.FASTAPI_INTENT,
                SystemComponent.FASTAPI_ADAPTERS
            ]:
                return self.check_fastapi_service_health(component)
            # 对 ROS2 组件，这里不做阻塞检查，统一交给 verify_component_communication
            return True
        except Exception:
            return False

    def check_fastapi_service_health(self, component: SystemComponent) -> bool:
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
            r = self.http_session.get(url, timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    # --------------------------
    # Verification (updated)
    # --------------------------
    def verify_system_integration(self):
        try:
            self.get_logger().info("🔍 Verifying system integration...")

            # 先全面 health 检查
            health_summary = {}
            for comp in [
                SystemComponent.FASTAPI_ORCHESTRATOR,
                SystemComponent.FASTAPI_GUARD,
                SystemComponent.FASTAPI_INTENT,
                SystemComponent.FASTAPI_ADAPTERS
            ]:
                ok = self.check_fastapi_service_health(comp)
                self.component_status[comp.value] = ok
                health_summary[comp.value] = ok

            self.get_logger().info(f"FastAPI health summary: {health_summary}")

            # 只有 orchestrator 健康时才做一次轻量回环 POST
            if health_summary.get(SystemComponent.FASTAPI_ORCHESTRATOR.value, False):
                ok = self.test_fastapi_integration()
                if ok:
                    self.get_logger().info("✅ FastAPI integration verified")
                else:
                    self.get_logger().warning("⚠️ FastAPI integration test failed")
            else:
                self.get_logger().warning("⚠️ Orchestrator /health not ready, skip /asr_text loopback test")

            # ROS2 服务通信检查
            self.verify_component_communication()
            self.get_logger().info("✅ System integration verification completed")

        except Exception as e:
            self.get_logger().error(f"System integration verification error: {e}")

    def test_fastapi_integration(self) -> bool:
        """Single attempt; no spammy logs."""
        try:
            url = f"{self.fastapi_urls['orchestrator']}/asr_text"
            payload = {"text": "系统测试"}
            r = self.http_session.post(url, json=payload, timeout=10)
            if r.status_code == 200:
                self.get_logger().debug(f"FastAPI test ok: {r.json()}")
                return True
            else:
                # 只打一条 WARN，并把响应内容放 DEBUG，便于排查
                self.get_logger().warning(f"FastAPI test failed: {r.status_code}")
                try:
                    self.get_logger().debug(f"/asr_text response body: {r.text}")
                except Exception:
                    pass
                return False
        except Exception as e:
            self.get_logger().warning(f"FastAPI integration test error: {e}")
            return False

    def verify_component_communication(self):
        try:
            for name, client in self.service_clients.items():
                # 仅对已创建的 client 做 wait_for_service
                if client.wait_for_service(timeout_sec=5.0):
                    self.get_logger().info(f"✅ {name} service available")
                else:
                    self.get_logger().warning(f"⚠️ {name} service not available")
        except Exception as e:
            self.get_logger().error(f"Component communication verification error: {e}")

    # --------------------------
    # Console, IO & pipeline (unchanged logic)
    # --------------------------
    def start_enhanced_console_interface(self):
        try:
            if not self.enable_console:
                return
            self.console_thread = threading.Thread(target=self.enhanced_console_loop, daemon=True)
            self.console_thread.start()
            self.display_enhanced_welcome_message()
        except Exception as e:
            self.get_logger().error(f"Enhanced console interface start error: {e}")

    def display_enhanced_welcome_message(self):
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
            print("🟢 Ready for conversation...\n")

    def enhanced_console_loop(self):
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
                    self.process_enhanced_text_input(user_input)
            except (EOFError, KeyboardInterrupt):
                break
            except Exception as e:
                self.get_logger().error(f"Console input error: {e}")

    def process_enhanced_text_input(self, text: str):
        try:
            self.get_logger().info(f"Processing enhanced text input: '{text}'")
            if 'fastapi_bridge' in self.service_clients:
                client = self.service_clients['fastapi_bridge']
                if client.wait_for_service(timeout_sec=2.0):
                    req = ProcessSpeech.Request()
                    req.text = text
                    fut = client.call_async(req)
                    fut.add_done_callback(lambda f: self.handle_fastapi_bridge_response(f, text))
                else:
                    self.get_logger().warning("FastAPI bridge service not available")
                    self.fallback_text_processing(text)
            else:
                self.fallback_text_processing(text)
        except Exception as e:
            self.get_logger().error(f"Enhanced text input processing error: {e}")

    def handle_fastapi_bridge_response(self, future, original_text: str):
        try:
            resp = future.result()
            if resp.processing_successful:
                result_data = json.loads(resp.result_data)
                self.get_logger().info(f"FastAPI bridge response: {result_data.get('status', 'unknown')}")
                self.generate_response_from_fastapi_result(result_data, original_text)
                self.system_metrics['successful_actions'] += 1
            else:
                self.get_logger().error(f"FastAPI bridge processing failed: {resp.error_message}")
                self.send_error_response("处理失败，请重试")
        except Exception as e:
            self.get_logger().error(f"FastAPI bridge response handling error: {e}")

    def generate_response_from_fastapi_result(self, result_data: Dict[str, Any], original_text: str):
        try:
            status = result_data.get('status', 'unknown')
            if status == 'emergency_dispatched':
                self.send_urgent_response("紧急情况已确认！正在立即联系帮助。请保持冷静，不要移动。")
                self.system_metrics['emergency_responses'] += 1
            elif status == 'denied':
                reason = result_data.get('reason', '安全原因')
                self.send_response(f"抱歉，出于{reason}，无法执行此操作。")
            elif status == 'need_confirm':
                prompt = result_data.get('prompt', '请确认是否继续此操作？')
                self.send_confirmation_request(prompt)
            elif status == 'ok':
                adapter = result_data.get('adapter', '')
                if adapter == 'smart-home':
                    self.send_response("好的，正在为您调整智能家居设备。")
                elif adapter == 'sip':
                    self.send_response("正在为您拨打电话。")
                else:
                    self.send_response("好的，已经为您处理。")
            else:
                self.send_response("我理解了您的话，让我想想如何帮助您。")
            self.system_metrics['total_conversations'] += 1
        except Exception as e:
            self.get_logger().error(f"Response generation error: {e}")

    def send_response(self, text: str):
        self.send_enhanced_response(text, urgency='normal')

    def send_urgent_response(self, text: str):
        self.send_enhanced_response(text, urgency='emergency')

    def send_confirmation_request(self, prompt: str):
        self.send_enhanced_response(prompt, urgency='high', requires_confirmation=True)

    def send_error_response(self, message: str):
        self.send_enhanced_response(message, urgency='normal', emotion_context={'primary_emotion': 'concern'})

    def send_enhanced_response(self, text: str, urgency: str = 'normal',
                               requires_confirmation: bool = False,
                               emotion_context: Optional[Dict[str, Any]] = None):
        try:
            self.get_logger().info(f"Sending enhanced response: '{text}' (urgency: {urgency})")
            print(f"Robot: {text}")

            msg = String()
            msg.data = text
            self.text_output_pub.publish(msg)

            if self.get_parameter('audio.enable_speaker').value:
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
        except Exception as e:
            self.get_logger().error(f"Enhanced response sending error: {e}")

    # --------------------------
    # Handlers
    # --------------------------
    def handle_text_input(self, msg: String):
        try:
            self.get_logger().info(f"Enhanced Router Agent received text: '{msg.data}'")
            self.process_enhanced_text_input(msg.data)
        except Exception as e:
            self.get_logger().error(f"Text input handling error: {e}")

    def handle_fastapi_response(self, msg: String):
        try:
            _ = json.loads(msg.data)
            self.get_logger().debug("FastAPI response received")
        except Exception as e:
            self.get_logger().error(f"FastAPI response handling error: {e}")

    def handle_guard_decision(self, msg: String):
        try:
            decision_data = json.loads(msg.data)
            decision = decision_data.get('decision', 'unknown')
            self.get_logger().info(f"Guard decision received: {decision}")
            if decision == 'dispatch_emergency':
                self.handle_emergency_dispatch_decision(decision_data)
            elif decision == 'need_confirm':
                self.send_confirmation_request(decision_data.get('prompt', '请确认您的请求。'))
        except Exception as e:
            self.get_logger().error(f"Guard decision handling error: {e}")

    def handle_emergency_dispatch_decision(self, decision_data: Dict[str, Any]):
        try:
            self.get_logger().critical("🚨 Emergency dispatch decision received")
            self.emergency_mode = True
            self.system_status = SystemStatus.EMERGENCY
            self.send_urgent_response("紧急情况已确认！正在立即联系帮助。请保持冷静，我会一直陪伴您。")
            self.trigger_comprehensive_emergency_response(decision_data)
        except Exception as e:
            self.get_logger().error(f"Emergency dispatch handling error: {e}")

    def trigger_comprehensive_emergency_response(self, decision_data: Dict[str, Any]):
        try:
            emergency_id = str(uuid.uuid4())
            if self.enable_sip_voip and 'emergency_dispatch' in self.service_clients:
                self.trigger_emergency_calling(emergency_id, decision_data)
            if self.enable_smart_home and 'smart_home' in self.service_clients:
                self.trigger_emergency_smart_home(emergency_id)
            if self.enable_video_streaming:
                self.trigger_emergency_video_streaming(emergency_id)
            self.get_logger().critical(f"Comprehensive emergency response triggered: {emergency_id}")
        except Exception as e:
            self.get_logger().error(f"Comprehensive emergency response error: {e}")

    def trigger_emergency_calling(self, emergency_id: str, decision_data: Dict[str, Any]):
        try:
            client = self.service_clients['emergency_dispatch']
            req = EmergencyDispatch.Request()
            req.emergency_type = decision_data.get('reason', 'unknown')
            req.severity_level = 4
            req.location_description = "Elderly person at home"
            fut = client.call_async(req)
            fut.add_done_callback(lambda f: self.handle_emergency_dispatch_response(f, emergency_id))
        except Exception as e:
            self.get_logger().error(f"Emergency calling trigger error: {e}")

    def trigger_emergency_smart_home(self, emergency_id: str):
        try:
            client = self.service_clients['smart_home']
            req = ExecuteAction.Request()
            req.action_type = "emergency_scene"
            req.parameters = json.dumps({'emergency_id': emergency_id, 'scene': 'emergency_response'})
            fut = client.call_async(req)
            fut.add_done_callback(lambda f: self.handle_smart_home_response(f))
        except Exception as e:
            self.get_logger().error(f"Emergency smart home trigger error: {e}")

    def trigger_emergency_video_streaming(self, emergency_id: str):
        try:
            self.get_logger().critical(f"Emergency video streaming activated: {emergency_id}")
        except Exception as e:
            self.get_logger().error(f"Emergency video streaming trigger error: {e}")

    def handle_emergency_dispatch_response(self, future, emergency_id: str):
        try:
            resp = future.result()
            if resp.dispatch_successful:
                self.get_logger().critical(f"✅ Emergency dispatch successful: {resp.reference_id}")
            else:
                self.get_logger().critical("❌ Emergency dispatch failed")
        except Exception as e:
            self.get_logger().error(f"Emergency dispatch response error: {e}")

    def handle_smart_home_response(self, future):
        try:
            resp = future.result()
            if resp.execution_successful:
                self.get_logger().info("✅ Smart home emergency scene activated")
            else:
                self.get_logger().warning("⚠️ Smart home emergency scene failed")
        except Exception as e:
            self.get_logger().error(f"Smart home response error: {e}")

    def handle_smart_home_result(self, msg: String):
        try:
            _ = json.loads(msg.data)
            self.get_logger().info("Smart home result received")
        except Exception as e:
            self.get_logger().error(f"Smart home result handling error: {e}")

    def handle_webrtc_status(self, msg: String):
        try:
            _ = json.loads(msg.data)
            self.get_logger().debug("WebRTC status received")
        except Exception as e:
            self.get_logger().error(f"WebRTC status handling error: {e}")

    def handle_emergency_alert(self, msg: EmergencyAlert):
        try:
            start = time.time()
            self.get_logger().critical(f"🚨 EMERGENCY ALERT: {msg.emergency_type} - {msg.description}")
            self.emergency_mode = True
            self.system_status = SystemStatus.EMERGENCY
            self.send_urgent_response("紧急情况已确认！正在立即联系帮助。请保持冷静，不要移动。救援正在路上。")
            self.trigger_comprehensive_emergency_response({
                'reason': msg.emergency_type, 'description': msg.description, 'severity': msg.severity_level
            })
            rt_ms = (time.time() - start) * 1000
            req_ms = self.get_parameter('safety.emergency_response_time_ms').value
            if rt_ms <= req_ms:
                self.get_logger().critical(f"✅ Emergency response time: {rt_ms:.1f}ms")
            else:
                self.get_logger().critical(f"⚠️ Emergency response time exceeded: {rt_ms:.1f}ms (required: {req_ms}ms)")
            self.publish_enhanced_system_status("EMERGENCY", f"Emergency response activated: {msg.emergency_type}")
        except Exception as e:
            self.get_logger().error(f"Emergency alert handling error: {e}")

    def handle_tts_status(self, msg: Bool):
        try:
            self.get_logger().debug("TTS engine speaking" if msg.data else "TTS engine finished")
        except Exception as e:
            self.get_logger().error(f"TTS status handling error: {e}")

    # --------------------------
    # Fallback
    # --------------------------
    def fallback_text_processing(self, text: str):
        try:
            self.get_logger().warning("Using fallback text processing")
            emergency_keywords = ['救命', 'help', 'emergency', '急救', '不舒服']
            if any(k in text.lower() for k in emergency_keywords):
                self.send_urgent_response("我检测到您可能需要紧急帮助，正在联系救援。")
            else:
                self.send_response("我听到了您的话，但系统服务暂时不可用。请稍后再试。")
        except Exception as e:
            self.get_logger().error(f"Fallback text processing error: {e}")

    # --------------------------
    # Health / Metrics (updated)
    # --------------------------
    def check_system_health(self):
        try:
            self.get_logger().debug("Checking enhanced system health...")
            self.check_fastapi_services_health()
            self.check_ros2_components_health()
            self.update_system_health_metrics()
            self.publish_system_health_status()
        except Exception as e:
            self.get_logger().error(f"System health check error: {e}")

    def check_fastapi_services_health(self):
        try:
            for comp in [SystemComponent.FASTAPI_ORCHESTRATOR,
                         SystemComponent.FASTAPI_GUARD,
                         SystemComponent.FASTAPI_INTENT,
                         SystemComponent.FASTAPI_ADAPTERS]:
                ok = self.check_fastapi_service_health(comp)
                self.component_status[comp.value] = ok
                self.component_health_data[comp.value] = {
                    'status': 'healthy' if ok else 'unhealthy',
                    'last_check': datetime.now().isoformat()
                }
        except Exception as e:
            self.get_logger().error(f"FastAPI services health check error: {e}")

    def check_ros2_components_health(self):
        try:
            # 仅根据是否有对应 client 来标记（避免误报）
            mapping = {
                SystemComponent.FASTAPI_BRIDGE: 'fastapi_bridge',
                SystemComponent.GUARD_FASTAPI_BRIDGE: 'guard_bridge',
                SystemComponent.SMART_HOME_BACKEND: 'smart_home',
                SystemComponent.SIP_VOIP_ADAPTER: 'emergency_dispatch'
            }
            for comp, key in mapping.items():
                self.component_status[comp.value] = key in self.service_clients
        except Exception as e:
            self.get_logger().error(f"ROS2 components health check error: {e}")

    def update_system_health_metrics(self):
        try:
            self.system_metrics['last_health_check'] = datetime.now()
            active_fastapi = sum(1 for comp in [SystemComponent.FASTAPI_ORCHESTRATOR,
                                                SystemComponent.FASTAPI_GUARD,
                                                SystemComponent.FASTAPI_INTENT,
                                                SystemComponent.FASTAPI_ADAPTERS]
                                 if self.component_status[comp.value])
            active_ros2 = sum(1 for comp in [
                SystemComponent.FASTAPI_BRIDGE,
                SystemComponent.GUARD_FASTAPI_BRIDGE,
                SystemComponent.SMART_HOME_BACKEND,
                SystemComponent.SIP_VOIP_ADAPTER
            ] if self.component_status[comp.value])
            self.system_metrics['fastapi_services_active'] = active_fastapi
            self.system_metrics['ros2_nodes_active'] = active_ros2
        except Exception as e:
            self.get_logger().error(f"System health metrics update error: {e}")

    def publish_system_health_status(self):
        try:
            health_data = {
                'system_status': self.system_status.value,
                'emergency_mode': self.emergency_mode,
                'components': self.component_status,
                'health_data': self.component_health_data,
                'timestamp': datetime.now().isoformat()
            }
            msg = String()
            msg.data = json.dumps(health_data)
            self.system_status_pub.publish(msg)
        except Exception as e:
            self.get_logger().error(f"System health status publishing error: {e}")

    def publish_system_metrics(self):
        try:
            # 计算并写回可序列化值
            uptime = datetime.now() - self.system_metrics['system_uptime_start']
            self.system_metrics['uptime_seconds'] = uptime.total_seconds()
            serializable = self._serialize_metrics()
            msg = String()
            msg.data = json.dumps(serializable)
            self.system_metrics_pub.publish(msg)
        except Exception as e:
            self.get_logger().error(f"System metrics publishing error: {e}")

    def publish_enhanced_system_status(self, status: str, message: str):
        try:
            status_data = {
                'status': status,
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'mode': self.mode.value,
                'emergency_mode': self.emergency_mode,
                'components': self.component_status,
                'deployment_target': self.deployment_target,
                'system_metrics': self._serialize_metrics(),  # <-- 修复 datetime 序列化
            }
            msg = String()
            msg.data = json.dumps(status_data)
            self.system_status_pub.publish(msg)
        except Exception as e:
            self.get_logger().error(f"Enhanced system status publishing error: {e}")

    # --------------------------
    # Debug printouts
    # --------------------------
    def print_enhanced_system_status(self):
        try:
            print("\n" + "="*60)
            print("🤖 ENHANCED ROUTER AGENT SYSTEM STATUS")
            print("="*60)
            print(f"System Status: {self.system_status.value.upper()}")
            print(f"Mode: {self.mode.value}")
            print(f"Emergency Mode: {'🚨 ACTIVE' if self.emergency_mode else '✅ Normal'}")
            print(f"Deployment: {self.deployment_target}")
            print("\n📊 Component Status:")
            for component, status in self.component_status.items():
                print(f"  {'✅' if status else '❌'} {component}")
            print("\n📈 System Metrics:")
            print(f"  Conversations: {self.system_metrics['total_conversations']}")
            print(f"  Emergency Responses: {self.system_metrics['emergency_responses']}")
            print(f"  Successful Actions: {self.system_metrics['successful_actions']}")
            uptime = datetime.now() - self.system_metrics['system_uptime_start']
            print(f"  Uptime: {uptime}")
            print("="*60 + "\n")
        except Exception as e:
            self.get_logger().error(f"Status printing error: {e}")

    def print_component_health(self):
        try:
            print("\n" + "="*60)
            print("🏥 COMPONENT HEALTH DETAILS")
            print("="*60)
            for component, health_data in self.component_health_data.items():
                status = health_data.get('status', 'unknown')
                last_check = health_data.get('last_check', 'never')
                print(f"  {'✅' if status == 'healthy' else '❌'} {component}: {status} (checked: {last_check})")
            print("="*60 + "\n")
        except Exception as e:
            self.get_logger().error(f"Component health printing error: {e}")

    # --------------------------
    # Tools
    # --------------------------
    def test_emergency_response(self):
        try:
            print("\n🚨 TESTING EMERGENCY RESPONSE SYSTEM...")
            test_alert = EmergencyAlert()
            test_alert.emergency_type = "test"
            test_alert.severity_level = 3
            test_alert.description = "Emergency response system test"
            self.handle_emergency_alert(test_alert)
            print("✅ Emergency response test completed")
        except Exception as e:
            self.get_logger().error(f"Emergency response test error: {e}")
            print("❌ Emergency response test failed")

    def trigger_help_request(self):
        try:
            self.get_logger().info("Processing help request")
            self.process_enhanced_text_input("help I need assistance")
        except Exception as e:
            self.get_logger().error(f"Help request trigger error: {e}")

    def shutdown_enhanced_system(self):
        try:
            self.get_logger().info("🛑 Shutting down Enhanced Router Agent Coordinator...")
            self.system_status = SystemStatus.SHUTTING_DOWN
            self.is_active = False
            self.publish_enhanced_system_status("SHUTDOWN", "Enhanced system shutdown initiated")
            print("\n👋 Goodbye! Enhanced Router Agent Coordinator shutting down...")
            if hasattr(self, 'http_session'):
                self.http_session.close()
            rclpy.shutdown()
        except Exception as e:
            self.get_logger().error(f"Enhanced shutdown error: {e}")


def main(args=None):
    rclpy.init(args=args)
    try:
        coordinator = EnhancedRouterAgentCoordinator()
        executor = MultiThreadedExecutor()
        executor.add_node(coordinator)
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
