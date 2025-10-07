#!/usr/bin/env python3
"""
FastAPI Bridge Node for Elderly Companion Robdog.

This node bridges ROS2 messaging with the proven FastAPI microservices 
from router_agent/router_agent/ maintaining the working closed-loop functionality.

Architecture:
ROS2 SpeechResult -> FastAPI Orchestrator -> ROS2 Response
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

import requests
import json
import time
import threading
import queue
from typing import Dict, Any, Optional
from datetime import datetime

# ROS2 message imports
from std_msgs.msg import Header, String
from elderly_companion.msg import SpeechResult, IntentResult
from elderly_companion.srv import ProcessSpeech

class FastAPIBridgeNode(Node):
    """
    Bridge Node connecting ROS2 with FastAPI microservices.
    
    This node maintains the proven closed-loop functionality from 
    router_agent/router_agent/ while providing proper ROS2 integration.
    """

    def __init__(self):
        super().__init__('fastapi_bridge_node')
        
        # Initialize parameters
        self.declare_parameters(
            namespace='',
            parameters=[
                ('fastapi.orchestrator_url', 'http://localhost:7010'),
                ('fastapi.guard_url', 'http://localhost:7002'),
                ('fastapi.intent_url', 'http://localhost:7001'),
                ('fastapi.adapters_url', 'http://localhost:7003'),
                ('fastapi.timeout_seconds', 10.0),
                ('fastapi.retry_attempts', 3),
                ('bridge.enable_async_processing', True),
                ('bridge.queue_size', 100),
            ]
        )
        
        # Get parameters
        self.orchestrator_url = self.get_parameter('fastapi.orchestrator_url').value
        self.guard_url = self.get_parameter('fastapi.guard_url').value
        self.intent_url = self.get_parameter('fastapi.intent_url').value
        self.adapters_url = self.get_parameter('fastapi.adapters_url').value
        self.request_timeout = self.get_parameter('fastapi.timeout_seconds').value
        self.retry_attempts = self.get_parameter('fastapi.retry_attempts').value
        self.enable_async = self.get_parameter('bridge.enable_async_processing').value
        self.queue_size = self.get_parameter('bridge.queue_size').value
        
        # HTTP session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'ROS2-FastAPI-Bridge/1.0'
        })
        
        # Processing queue for async handling
        self.processing_queue = queue.Queue(maxsize=self.queue_size)
        self.response_cache = {}  # Simple cache for recent responses
        
        # QoS profiles
        reliable_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=50
        )
        
        # Subscribers
        self.speech_result_sub = self.create_subscription(
            SpeechResult,
            '/speech/with_emotion',
            self.handle_speech_result_callback,
            reliable_qos
        )
        
        # Publishers
        self.fastapi_response_pub = self.create_publisher(
            String,
            '/fastapi/response',
            reliable_qos
        )
        
        self.processed_intent_pub = self.create_publisher(
            IntentResult,
            '/fastapi/processed_intent',
            reliable_qos
        )
        
        self.bridge_status_pub = self.create_publisher(
            String,
            '/fastapi/bridge_status',
            reliable_qos
        )
        
        # Services
        self.process_text_service = self.create_service(
            ProcessSpeech,
            '/fastapi_bridge/process_text',
            self.process_text_service_callback
        )
        
        # Start async processing thread if enabled
        if self.enable_async:
            self.processing_thread = threading.Thread(
                target=self.async_processing_loop,
                daemon=True
            )
            self.processing_thread.start()
        
        # Test FastAPI services availability
        self.test_fastapi_services()
        
        self.get_logger().info(f"FastAPI Bridge Node initialized - Orchestrator: {self.orchestrator_url}")

    def test_fastapi_services(self):
        """Test availability of FastAPI services."""
        services = {
            'orchestrator': f"{self.orchestrator_url}/health",
            'guard': f"{self.guard_url}/health", 
            'intent': f"{self.intent_url}/health",
            'adapters': f"{self.adapters_url}/health"
        }
        
        available_services = []
        unavailable_services = []
        
        for service_name, health_url in services.items():
            try:
                response = self.session.get(health_url, timeout=5)
                if response.status_code == 200:
                    available_services.append(service_name)
                    self.get_logger().info(f"✅ {service_name} service available")
                else:
                    unavailable_services.append(service_name)
                    self.get_logger().warning(f"⚠️ {service_name} service responded with {response.status_code}")
            except Exception as e:
                unavailable_services.append(service_name)
                self.get_logger().warning(f"❌ {service_name} service unavailable: {e}")
        
        # Publish bridge status
        status_data = {
            'timestamp': datetime.now().isoformat(),
            'available_services': available_services,
            'unavailable_services': unavailable_services,
            'bridge_ready': len(available_services) >= 2  # Need at least orchestrator + one other
        }
        
        status_msg = String()
        status_msg.data = json.dumps(status_data)
        self.bridge_status_pub.publish(status_msg)

    def handle_speech_result_callback(self, msg: SpeechResult):
        """Handle speech result and bridge to FastAPI orchestrator."""
        try:
            self.get_logger().info(f"Bridge processing speech: '{msg.text}'")
            
            if self.enable_async:
                # Add to async processing queue
                try:
                    self.processing_queue.put_nowait({
                        'type': 'speech_result',
                        'data': msg,
                        'timestamp': time.time()
                    })
                except queue.Full:
                    self.get_logger().error("Processing queue full, dropping speech result")
            else:
                # Process synchronously
                self.process_speech_result(msg)
                
        except Exception as e:
            self.get_logger().error(f"Speech result handling error: {e}")

    def process_speech_result(self, speech_msg: SpeechResult):
        """Process speech result through FastAPI orchestrator."""
        try:
            start_time = time.time()
            
            # Prepare request for FastAPI orchestrator
            request_data = {
                "text": speech_msg.text
            }
            
            # Call FastAPI orchestrator
            response_data = self.call_fastapi_orchestrator(request_data)
            
            if response_data:
                # Process successful response
                self.handle_orchestrator_response(response_data, speech_msg)
                
                processing_time = (time.time() - start_time) * 1000
                self.get_logger().info(f"FastAPI processing completed in {processing_time:.1f}ms")
            else:
                self.get_logger().error("FastAPI orchestrator returned no response")
                
        except Exception as e:
            self.get_logger().error(f"Speech result processing error: {e}")

    def call_fastapi_orchestrator(self, request_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Call FastAPI orchestrator with retry logic."""
        orchestrator_endpoint = f"{self.orchestrator_url}/asr_text"
        
        for attempt in range(self.retry_attempts):
            try:
                self.get_logger().debug(f"Calling FastAPI orchestrator (attempt {attempt + 1}): {request_data}")
                
                response = self.session.post(
                    orchestrator_endpoint,
                    json=request_data,
                    timeout=self.request_timeout
                )
                
                if response.status_code == 200:
                    response_data = response.json()
                    self.get_logger().debug(f"FastAPI response: {response_data}")
                    return response_data
                else:
                    self.get_logger().warning(f"FastAPI returned status {response.status_code}: {response.text}")
                    
            except requests.exceptions.Timeout:
                self.get_logger().warning(f"FastAPI request timeout (attempt {attempt + 1})")
            except requests.exceptions.ConnectionError:
                self.get_logger().warning(f"FastAPI connection error (attempt {attempt + 1})")
            except Exception as e:
                self.get_logger().error(f"FastAPI request error (attempt {attempt + 1}): {e}")
            
            if attempt < self.retry_attempts - 1:
                time.sleep(0.5 * (attempt + 1))  # Exponential backoff
        
        return None

    def handle_orchestrator_response(self, response_data: Dict[str, Any], original_speech: SpeechResult):
        """Handle response from FastAPI orchestrator."""
        try:
            # Publish raw FastAPI response
            response_msg = String()
            response_msg.data = json.dumps(response_data)
            self.fastapi_response_pub.publish(response_msg)
            
            # Extract and publish processed intent if available
            if 'intent' in response_data:
                intent_result = self.create_intent_result_from_response(
                    response_data, original_speech
                )
                self.processed_intent_pub.publish(intent_result)
            
            # Log response status
            status = response_data.get('status', 'unknown')
            if status == 'emergency_dispatched':
                self.get_logger().critical(f"🚨 Emergency dispatched: {response_data}")
            elif status == 'denied':
                self.get_logger().warning(f"⚠️ Intent denied: {response_data.get('reason', 'unknown')}")
            elif status == 'need_confirm':
                self.get_logger().info(f"❓ Confirmation needed: {response_data.get('prompt', '')}")
            else:
                self.get_logger().info(f"✅ Processing completed: {status}")
                
        except Exception as e:
            self.get_logger().error(f"Orchestrator response handling error: {e}")

    def create_intent_result_from_response(self, response_data: Dict[str, Any], 
                                         original_speech: SpeechResult) -> IntentResult:
        """Create IntentResult from FastAPI response."""
        intent_result = IntentResult()
        intent_result.header = Header()
        intent_result.header.stamp = self.get_clock().now().to_msg()
        intent_result.header.frame_id = "fastapi_bridge"
        
        # Extract intent information
        intent_data = response_data.get('intent', {})
        intent_result.intent_type = intent_data.get('intent', 'unknown')
        intent_result.confidence = intent_data.get('confidence', 0.0)
        
        # Map FastAPI response to ROS2 intent fields
        if 'adapter' in response_data:
            intent_result.adapter_used = response_data['adapter']
        
        intent_result.processing_successful = response_data.get('status') == 'ok'
        intent_result.requires_confirmation = response_data.get('status') == 'need_confirm'
        
        # Add bridge context
        intent_result.conversation_id = f"fastapi_bridge_{int(time.time())}"
        intent_result.original_speech = original_speech
        intent_result.fastapi_response = json.dumps(response_data)
        
        return intent_result

    def async_processing_loop(self):
        """Async processing loop for handling speech results."""
        while rclpy.ok():
            try:
                # Get item from queue with timeout
                item = self.processing_queue.get(timeout=1.0)
                
                if item['type'] == 'speech_result':
                    speech_msg = item['data']
                    self.process_speech_result(speech_msg)
                
                self.processing_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                self.get_logger().error(f"Async processing error: {e}")

    def process_text_service_callback(self, request, response):
        """Handle service callback for direct text processing."""
        try:
            self.get_logger().info(f"Direct text processing service called: '{request.text}'")
            
            # Prepare request data
            request_data = {"text": request.text}
            
            # Call FastAPI orchestrator
            response_data = self.call_fastapi_orchestrator(request_data)
            
            if response_data:
                response.processing_successful = True
                response.result_data = json.dumps(response_data)
                response.processing_time_ms = 100.0  # Placeholder
                
                # Check if emergency was dispatched
                if response_data.get('status') == 'emergency_dispatched':
                    response.emergency_triggered = True
                
                self.get_logger().info(f"Direct text processing completed: {response_data.get('status', 'unknown')}")
            else:
                response.processing_successful = False
                response.error_message = "FastAPI orchestrator call failed"
            
            return response
            
        except Exception as e:
            self.get_logger().error(f"Text processing service error: {e}")
            response.processing_successful = False
            response.error_message = str(e)
            return response

    def call_guard_service(self, text: str, intent: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Direct call to FastAPI guard service."""
        try:
            guard_endpoint = f"{self.guard_url}/guard/check"
            
            request_data = {
                "type": "intent" if intent else "asr",
                "text": text,
                "intent": intent
            }
            
            response = self.session.post(
                guard_endpoint,
                json=request_data,
                timeout=self.request_timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                self.get_logger().warning(f"Guard service returned {response.status_code}")
                return None
                
        except Exception as e:
            self.get_logger().error(f"Guard service call error: {e}")
            return None

    def call_intent_service(self, text: str) -> Optional[Dict[str, Any]]:
        """Direct call to FastAPI intent service."""
        try:
            intent_endpoint = f"{self.intent_url}/parse_intent"
            
            request_data = {"text": text}
            
            response = self.session.post(
                intent_endpoint,
                json=request_data,
                timeout=self.request_timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                self.get_logger().warning(f"Intent service returned {response.status_code}")
                return None
                
        except Exception as e:
            self.get_logger().error(f"Intent service call error: {e}")
            return None

    def __del__(self):
        """Clean up when node is destroyed."""
        try:
            if hasattr(self, 'session'):
                self.session.close()
        except:
            pass


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)
    
    try:
        node = FastAPIBridgeNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"FastAPI Bridge Node error: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()