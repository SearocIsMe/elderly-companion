#!/usr/bin/env python3
"""
Guard-FastAPI Bridge Node for Elderly Companion Robdog.

Integrates the enhanced ROS2 Guard Engine with the proven FastAPI Guard Service,
maintaining the working closed-loop functionality while adding advanced safety features.

Integration Flow:
ROS2 Enhanced Guard → FastAPI Guard Service → Combined Decision → Response
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

import requests
import json
import time
import threading
import queue
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

# ROS2 message imports
from std_msgs.msg import Header, String
from elderly_companion.msg import (
    SpeechResult, IntentResult, EmergencyAlert
)
from elderly_companion.srv import ValidateIntent


class GuardDecisionType(Enum):
    """Types of guard decisions."""
    PASS_TEXT = "pass_text"
    WAKE = "wake"
    DISPATCH_EMERGENCY = "dispatch_emergency"
    DENY = "deny"
    NEED_CONFIRM = "need_confirm"
    ALLOW = "allow"


class GuardDecisionPriority(Enum):
    """Priority levels for guard decisions."""
    EMERGENCY = 1
    SAFETY_CRITICAL = 2
    SECURITY = 3
    NORMAL = 4
    LOW = 5


class GuardFastAPIBridgeNode(Node):
    """
    Bridge Node integrating Enhanced Guard Engine with FastAPI Guard Service.
    
    This node provides seamless integration between:
    - ROS2 Enhanced Guard Engine (advanced safety analysis)
    - FastAPI Guard Service (proven closed-loop functionality)
    
    Combined features:
    - Maintains FastAPI guard service proven decision logic
    - Enhances with ROS2 advanced safety features (wakeword, SOS, geofence, implicit commands)
    - Provides unified guard decision API
    - Emergency response coordination
    - Performance monitoring and logging
    """

    def __init__(self):
        super().__init__('guard_fastapi_bridge_node')
        
        # Initialize parameters
        self.declare_parameters(
            namespace='',
            parameters=[
                # FastAPI Guard Service
                ('fastapi.guard_url', 'http://localhost:7002'),
                ('fastapi.timeout_seconds', 5.0),
                ('fastapi.retry_attempts', 3),
                ('fastapi.enable_fallback', True),
                
                # Enhanced Guard Integration
                ('enhanced_guard.enable_wakeword_enhancement', True),
                ('enhanced_guard.enable_sos_enhancement', True),
                ('enhanced_guard.enable_implicit_commands', True),
                ('enhanced_guard.enable_geofence_integration', True),
                
                # Decision Logic
                ('decision.enhanced_guard_weight', 0.6),
                ('decision.fastapi_guard_weight', 0.4),
                ('decision.emergency_override_threshold', 0.8),
                ('decision.enable_learning', True),
                
                # Performance and Monitoring
                ('monitoring.log_all_decisions', True),
                ('monitoring.performance_tracking', True),
                ('monitoring.alert_slow_decisions', True),
                ('performance.max_decision_time_ms', 200),
                
                # Safety Configuration
                ('safety.emergency_response_time_ms', 100),
                ('safety.enable_proactive_alerts', True),
                ('safety.escalation_threshold', 3),
            ]
        )
        
        # Get parameters
        self.fastapi_guard_url = self.get_parameter('fastapi.guard_url').value
        self.fastapi_timeout = self.get_parameter('fastapi.timeout_seconds').value
        self.retry_attempts = self.get_parameter('fastapi.retry_attempts').value
        self.enable_wakeword_enhancement = self.get_parameter('enhanced_guard.enable_wakeword_enhancement').value
        self.enable_sos_enhancement = self.get_parameter('enhanced_guard.enable_sos_enhancement').value
        self.enable_implicit_commands = self.get_parameter('enhanced_guard.enable_implicit_commands').value
        self.enhanced_weight = self.get_parameter('decision.enhanced_guard_weight').value
        self.fastapi_weight = self.get_parameter('decision.fastapi_guard_weight').value
        self.emergency_threshold = self.get_parameter('decision.emergency_override_threshold').value
        self.max_decision_time = self.get_parameter('performance.max_decision_time_ms').value
        self.emergency_response_time = self.get_parameter('safety.emergency_response_time_ms').value
        
        # Integration state
        self.enhanced_guard_available = False
        self.fastapi_guard_available = False
        self.last_enhanced_analysis: Optional[Dict[str, Any]] = None
        
        # Performance tracking
        self.decision_times = []
        self.decision_stats = {
            'total_decisions': 0,
            'emergency_decisions': 0,
            'enhanced_guard_decisions': 0,
            'fastapi_only_decisions': 0,
            'combined_decisions': 0
        }
        
        # HTTP session for FastAPI communication
        self.fastapi_session = requests.Session()
        self.fastapi_session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Guard-FastAPI-Bridge/1.0'
        })
        
        # QoS profiles
        critical_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=100
        )
        
        fast_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )
        
        # Subscribers - Enhanced Guard outputs
        self.guard_analysis_sub = self.create_subscription(
            String,
            '/guard/analysis',
            self.handle_enhanced_guard_analysis,
            critical_qos
        )
        
        self.sos_alert_sub = self.create_subscription(
            EmergencyAlert,
            '/guard/sos_alert',
            self.handle_sos_alert,
            critical_qos
        )
        
        self.enhanced_intent_sub = self.create_subscription(
            IntentResult,
            '/guard/enhanced_intent',
            self.handle_enhanced_intent,
            critical_qos
        )
        
        # Subscribers - Input for guard processing
        self.speech_result_sub = self.create_subscription(
            SpeechResult,
            '/speech/recognized',
            self.handle_speech_for_guard,
            critical_qos
        )
        
        # Publishers - Guard outputs
        self.guard_decision_pub = self.create_publisher(
            String,
            '/guard/final_decision',
            critical_qos
        )
        
        self.guard_metrics_pub = self.create_publisher(
            String,
            '/guard/performance_metrics',
            fast_qos
        )
        
        # Services
        self.validate_intent_service = self.create_service(
            ValidateIntent,
            '/guard_bridge/validate_intent',
            self.validate_intent_callback
        )
        
        # Test FastAPI guard availability
        self.test_fastapi_guard_availability()
        
        # Start monitoring threads
        self.start_monitoring_threads()
        
        self.get_logger().info("Guard-FastAPI Bridge Node initialized - Integrated guard system ready")

    def test_fastapi_guard_availability(self):
        """Test FastAPI guard service availability."""
        try:
            health_url = f"{self.fastapi_guard_url}/health"
            response = self.fastapi_session.get(health_url, timeout=5)
            
            if response.status_code == 200:
                self.fastapi_guard_available = True
                self.get_logger().info("✅ FastAPI Guard service available")
            else:
                self.fastapi_guard_available = False
                self.get_logger().warning("⚠️ FastAPI Guard service not responding properly")
                
        except Exception as e:
            self.fastapi_guard_available = False
            self.get_logger().warning(f"❌ FastAPI Guard service unavailable: {e}")

    def handle_enhanced_guard_analysis(self, msg: String):
        """Handle comprehensive analysis from Enhanced Guard Engine."""
        try:
            analysis = json.loads(msg.data)
            self.last_enhanced_analysis = analysis
            self.enhanced_guard_available = True
            
            self.get_logger().debug(f"Enhanced Guard analysis received: {analysis.get('safety_assessment', {}).get('level', 'unknown')}")
            
            # Check for immediate emergency conditions
            safety_assessment = analysis.get('safety_assessment', {})
            if safety_assessment.get('level') == 'emergency':
                self.handle_immediate_emergency(analysis)
                
        except Exception as e:
            self.get_logger().error(f"Enhanced guard analysis handling error: {e}")

    def handle_sos_alert(self, msg: EmergencyAlert):
        """Handle SOS alerts from Enhanced Guard."""
        try:
            self.get_logger().critical(f"SOS ALERT from Enhanced Guard: {msg.emergency_type}")
            
            # Create emergency decision immediately
            emergency_decision = {
                'decision': GuardDecisionType.DISPATCH_EMERGENCY.value,
                'route': ['sip', 'family', 'doctor'],
                'reason': f'enhanced_guard_sos_{msg.emergency_type}',
                'urgency_level': msg.severity_level,
                'enhanced_guard_triggered': True,
                'timestamp': datetime.now().isoformat(),
                'emergency_id': getattr(msg, 'incident_id', str(time.time()))
            }
            
            # Publish immediate emergency decision
            self.publish_guard_decision(emergency_decision)
            
            # Update stats
            self.decision_stats['emergency_decisions'] += 1
            
        except Exception as e:
            self.get_logger().error(f"SOS alert handling error: {e}")

    def handle_enhanced_intent(self, msg: IntentResult):
        """Handle enhanced intents from Guard."""
        try:
            self.get_logger().info(f"Enhanced intent from Guard: {msg.intent_type}")
            
            # Process the enhanced intent through combined guard logic
            self.process_enhanced_intent_with_fastapi(msg)
            
        except Exception as e:
            self.get_logger().error(f"Enhanced intent handling error: {e}")

    def handle_speech_for_guard(self, msg: SpeechResult):
        """Handle speech input for comprehensive guard processing."""
        try:
            start_time = time.time()
            
            self.get_logger().info(f"Processing speech for guard: '{msg.text}'")
            
            # Process through both Enhanced Guard and FastAPI Guard
            combined_decision = self.process_speech_with_combined_guard(msg)
            
            if combined_decision:
                # Publish final decision
                self.publish_guard_decision(combined_decision)
                
                # Track performance
                decision_time = (time.time() - start_time) * 1000  # ms
                self.decision_times.append(decision_time)
                
                if decision_time > self.max_decision_time:
                    self.get_logger().warning(f"Guard decision time exceeded: {decision_time:.1f}ms")
                
                # Update statistics
                self.decision_stats['total_decisions'] += 1
                
        except Exception as e:
            self.get_logger().error(f"Speech guard processing error: {e}")

    def process_speech_with_combined_guard(self, speech_msg: SpeechResult) -> Optional[Dict[str, Any]]:
        """Process speech through both Enhanced Guard and FastAPI Guard."""
        try:
            enhanced_analysis = self.last_enhanced_analysis
            fastapi_decision = None
            
            # Get FastAPI guard decision
            if self.fastapi_guard_available:
                fastapi_decision = self.call_fastapi_guard_asr(speech_msg.text)
                
            # Combine decisions
            combined_decision = self.combine_guard_decisions(
                speech_msg, enhanced_analysis, fastapi_decision
            )
            
            return combined_decision
            
        except Exception as e:
            self.get_logger().error(f"Combined guard processing error: {e}")
            return None

    def process_enhanced_intent_with_fastapi(self, intent_msg: IntentResult):
        """Process enhanced intent through FastAPI guard."""
        try:
            # Convert ROS2 IntentResult to dict format expected by FastAPI
            intent_dict = {
                'intent': intent_msg.intent_type,
                'confidence': intent_msg.confidence,
                'guard_enhanced': True,
                'conversation_id': intent_msg.conversation_id
            }
            
            # Add any additional parameters from the intent
            if hasattr(intent_msg, 'parameters'):
                intent_dict.update(json.loads(intent_msg.parameters))
            
            # Get FastAPI guard decision for intent
            fastapi_decision = self.call_fastapi_guard_intent(intent_dict)
            
            # Combine with enhanced guard analysis
            if self.last_enhanced_analysis:
                combined_decision = self.combine_intent_decisions(
                    intent_msg, self.last_enhanced_analysis, fastapi_decision
                )
                
                if combined_decision:
                    self.publish_guard_decision(combined_decision)
                    
        except Exception as e:
            self.get_logger().error(f"Enhanced intent FastAPI processing error: {e}")

    def call_fastapi_guard_asr(self, text: str) -> Optional[Dict[str, Any]]:
        """Call FastAPI guard service for ASR text."""
        try:
            guard_endpoint = f"{self.fastapi_guard_url}/guard/check"
            
            request_data = {
                "type": "asr",
                "text": text
            }
            
            for attempt in range(self.retry_attempts):
                try:
                    response = self.fastapi_session.post(
                        guard_endpoint,
                        json=request_data,
                        timeout=self.fastapi_timeout
                    )
                    
                    if response.status_code == 200:
                        decision = response.json()
                        self.get_logger().debug(f"FastAPI guard ASR decision: {decision}")
                        return decision
                    else:
                        self.get_logger().warning(f"FastAPI guard returned {response.status_code}")
                        
                except requests.exceptions.Timeout:
                    self.get_logger().warning(f"FastAPI guard timeout (attempt {attempt + 1})")
                except Exception as e:
                    self.get_logger().error(f"FastAPI guard error (attempt {attempt + 1}): {e}")
                
                if attempt < self.retry_attempts - 1:
                    time.sleep(0.2 * (attempt + 1))
            
            return None
            
        except Exception as e:
            self.get_logger().error(f"FastAPI guard ASR call error: {e}")
            return None

    def call_fastapi_guard_intent(self, intent_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Call FastAPI guard service for intent validation."""
        try:
            guard_endpoint = f"{self.fastapi_guard_url}/guard/check"
            
            request_data = {
                "type": "intent",
                "intent": intent_dict
            }
            
            response = self.fastapi_session.post(
                guard_endpoint,
                json=request_data,
                timeout=self.fastapi_timeout
            )
            
            if response.status_code == 200:
                decision = response.json()
                self.get_logger().debug(f"FastAPI guard intent decision: {decision}")
                return decision
            else:
                self.get_logger().warning(f"FastAPI guard intent returned {response.status_code}")
                return None
                
        except Exception as e:
            self.get_logger().error(f"FastAPI guard intent call error: {e}")
            return None

    def combine_guard_decisions(self, speech_msg: SpeechResult, 
                              enhanced_analysis: Optional[Dict[str, Any]],
                              fastapi_decision: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Combine decisions from Enhanced Guard and FastAPI Guard."""
        try:
            # Start with FastAPI decision as base (proven functionality)
            if fastapi_decision:
                combined_decision = fastapi_decision.copy()
                combined_decision['fastapi_decision'] = fastapi_decision
                self.decision_stats['fastapi_only_decisions'] += 1
            else:
                # Fallback decision if FastAPI not available
                combined_decision = {
                    'decision': 'pass_text',
                    'reason': 'fastapi_unavailable_fallback'
                }
            
            # Enhance with Enhanced Guard analysis
            if enhanced_analysis:
                enhanced_decision = self.interpret_enhanced_guard_analysis(enhanced_analysis)
                combined_decision = self.merge_decisions(combined_decision, enhanced_decision, enhanced_analysis)
                combined_decision['enhanced_analysis'] = enhanced_analysis
                self.decision_stats['enhanced_guard_decisions'] += 1
                
                if fastapi_decision:
                    self.decision_stats['combined_decisions'] += 1
            
            # Add metadata
            combined_decision.update({
                'timestamp': datetime.now().isoformat(),
                'speech_text': speech_msg.text,
                'speech_confidence': speech_msg.confidence,
                'processing_mode': 'combined' if enhanced_analysis and fastapi_decision else 'single',
                'bridge_version': '1.0'
            })
            
            return combined_decision
            
        except Exception as e:
            self.get_logger().error(f"Guard decision combination error: {e}")
            return {
                'decision': 'pass_text',
                'reason': 'decision_combination_error',
                'error': str(e)
            }

    def interpret_enhanced_guard_analysis(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Interpret Enhanced Guard analysis into decision format."""
        try:
            safety_assessment = analysis.get('safety_assessment', {})
            sos_detection = analysis.get('sos_detection', {})
            wakeword = analysis.get('wakeword', {})
            implicit_command = analysis.get('implicit_command', {})
            
            # Priority 1: Emergency SOS
            if sos_detection.get('detected') and sos_detection.get('urgency_level', 0) >= 3:
                return {
                    'decision': GuardDecisionType.DISPATCH_EMERGENCY.value,
                    'route': ['sip', 'family', 'doctor'],
                    'reason': f"enhanced_guard_sos_{sos_detection.get('category', 'unknown')}",
                    'priority': GuardDecisionPriority.EMERGENCY.value,
                    'confidence': sos_detection.get('confidence', 0.9)
                }
            
            # Priority 2: Safety critical conditions
            if safety_assessment.get('level') == 'emergency':
                return {
                    'decision': GuardDecisionType.DISPATCH_EMERGENCY.value,
                    'route': ['sip', 'family'],
                    'reason': 'enhanced_guard_safety_emergency',
                    'priority': GuardDecisionPriority.EMERGENCY.value,
                    'confidence': 0.85
                }
            
            # Priority 3: Wakeword detection
            if (self.enable_wakeword_enhancement and 
                wakeword.get('detected') and 
                wakeword.get('type') == 'emergency'):
                return {
                    'decision': GuardDecisionType.WAKE.value,
                    'reason': f"enhanced_guard_wakeword_{wakeword.get('type')}",
                    'priority': GuardDecisionPriority.SAFETY_CRITICAL.value,
                    'confidence': wakeword.get('confidence', 0.8)
                }
            
            # Priority 4: High risk situations
            elif safety_assessment.get('level') == 'high_risk':
                return {
                    'decision': GuardDecisionType.NEED_CONFIRM.value,
                    'reason': 'enhanced_guard_high_risk',
                    'prompt': '检测到可能的安全风险，请确认您是否需要帮助？',
                    'priority': GuardDecisionPriority.SAFETY_CRITICAL.value,
                    'confidence': 0.7
                }
            
            # Priority 5: Implicit commands
            elif (self.enable_implicit_commands and 
                  implicit_command.get('detected') and 
                  implicit_command.get('confidence', 0) > 0.7):
                return {
                    'decision': GuardDecisionType.ALLOW.value,
                    'reason': f"enhanced_guard_implicit_{implicit_command.get('command_type')}",
                    'implicit_command': implicit_command,
                    'requires_confirmation': implicit_command.get('requires_confirmation', False),
                    'priority': GuardDecisionPriority.NORMAL.value,
                    'confidence': implicit_command.get('confidence', 0.7)
                }
            
            # Default: Let other systems handle
            else:
                return {
                    'decision': GuardDecisionType.PASS_TEXT.value,
                    'reason': 'enhanced_guard_no_trigger',
                    'priority': GuardDecisionPriority.LOW.value,
                    'confidence': 0.5
                }
                
        except Exception as e:
            self.get_logger().error(f"Enhanced guard analysis interpretation error: {e}")
            return {
                'decision': GuardDecisionType.PASS_TEXT.value,
                'reason': 'enhanced_guard_analysis_error'
            }

    def merge_decisions(self, fastapi_decision: Dict[str, Any], 
                       enhanced_decision: Dict[str, Any],
                       enhanced_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Merge decisions from FastAPI Guard and Enhanced Guard."""
        try:
            # Emergency decisions from Enhanced Guard take priority
            enhanced_decision_type = enhanced_decision.get('decision')
            fastapi_decision_type = fastapi_decision.get('decision')
            
            if enhanced_decision_type == GuardDecisionType.DISPATCH_EMERGENCY.value:
                # Enhanced Guard emergency overrides everything
                return enhanced_decision
            
            # FastAPI emergency decisions are preserved
            elif fastapi_decision_type == GuardDecisionType.DISPATCH_EMERGENCY.value:
                # Keep FastAPI emergency decision but add enhanced context
                merged = fastapi_decision.copy()
                merged['enhanced_context'] = enhanced_analysis
                return merged
            
            # For non-emergency decisions, combine intelligently
            else:
                # Use weighted combination based on confidence and priority
                enhanced_confidence = enhanced_decision.get('confidence', 0.5)
                fastapi_confidence = 1.0  # FastAPI decisions are binary, assume high confidence
                
                # Calculate combined confidence
                combined_confidence = (
                    enhanced_confidence * self.enhanced_weight + 
                    fastapi_confidence * self.fastapi_weight
                )
                
                # Determine final decision
                if enhanced_confidence > 0.8 and enhanced_decision_type in [
                    GuardDecisionType.DENY.value, 
                    GuardDecisionType.NEED_CONFIRM.value
                ]:
                    # High confidence Enhanced Guard safety decisions take priority
                    final_decision = enhanced_decision.copy()
                    final_decision['fastapi_input'] = fastapi_decision
                    
                elif fastapi_decision_type in [
                    GuardDecisionType.DENY.value,
                    GuardDecisionType.NEED_CONFIRM.value
                ]:
                    # FastAPI safety decisions are preserved
                    final_decision = fastapi_decision.copy()
                    final_decision['enhanced_context'] = enhanced_analysis
                    
                else:
                    # Default to FastAPI decision with enhanced context
                    final_decision = fastapi_decision.copy()
                    final_decision['enhanced_context'] = enhanced_analysis
                    final_decision['enhanced_decision'] = enhanced_decision
                    
                final_decision['combined_confidence'] = combined_confidence
                return final_decision
                
        except Exception as e:
            self.get_logger().error(f"Decision merging error: {e}")
            # Fallback to FastAPI decision
            return fastapi_decision if fastapi_decision else {
                'decision': 'pass_text',
                'reason': 'decision_merge_error'
            }

    def combine_intent_decisions(self, intent_msg: IntentResult,
                               enhanced_analysis: Dict[str, Any],
                               fastapi_decision: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Combine intent decisions from Enhanced Guard and FastAPI."""
        try:
            # If FastAPI guard provides decision, use it as base
            if fastapi_decision:
                combined = fastapi_decision.copy()
                combined['enhanced_context'] = enhanced_analysis
                combined['original_intent'] = intent_msg.intent_type
                
                # Check if Enhanced Guard suggests denial
                safety_level = enhanced_analysis.get('safety_assessment', {}).get('level')
                if safety_level in ['emergency', 'high_risk']:
                    combined['decision'] = 'deny'
                    combined['reason'] = f'enhanced_guard_safety_override_{safety_level}'
                
                return combined
            else:
                # Create decision based on Enhanced Guard analysis only
                safety_assessment = enhanced_analysis.get('safety_assessment', {})
                
                if safety_assessment.get('level') == 'emergency':
                    return {
                        'decision': 'dispatch_emergency',
                        'route': ['sip', 'family'],
                        'reason': 'enhanced_guard_intent_emergency'
                    }
                elif safety_assessment.get('risk_score', 0) > 0.7:
                    return {
                        'decision': 'need_confirm',
                        'reason': 'enhanced_guard_high_risk_intent',
                        'prompt': '此操作可能存在风险，请确认是否继续？'
                    }
                else:
                    return {
                        'decision': 'allow',
                        'reason': 'enhanced_guard_intent_safe'
                    }
                    
        except Exception as e:
            self.get_logger().error(f"Intent decision combination error: {e}")
            return None

    def handle_immediate_emergency(self, analysis: Dict[str, Any]):
        """Handle immediate emergency situations with <100ms response."""
        try:
            start_time = time.time()
            
            # Create immediate emergency response
            emergency_decision = {
                'decision': GuardDecisionType.DISPATCH_EMERGENCY.value,
                'route': ['sip', 'family', 'doctor', 'emergency'],
                'reason': 'enhanced_guard_immediate_emergency',
                'urgency_level': 4,
                'immediate_response': True,
                'enhanced_analysis': analysis,
                'timestamp': datetime.now().isoformat()
            }
            
            # Publish immediately
            self.publish_guard_decision(emergency_decision)
            
            # Check response time
            response_time = (time.time() - start_time) * 1000  # ms
            if response_time <= self.emergency_response_time:
                self.get_logger().critical(f"✅ Emergency response time: {response_time:.1f}ms")
            else:
                self.get_logger().critical(f"⚠️ Emergency response time exceeded: {response_time:.1f}ms")
                
        except Exception as e:
            self.get_logger().error(f"Immediate emergency handling error: {e}")

    def publish_guard_decision(self, decision: Dict[str, Any]):
        """Publish final guard decision."""
        try:
            # Add processing metadata
            decision['published_at'] = datetime.now().isoformat()
            decision['bridge_node'] = 'guard_fastapi_bridge'
            
            # Publish decision
            decision_msg = String()
            decision_msg.data = json.dumps(decision)
            self.guard_decision_pub.publish(decision_msg)
            
            # Log decision
            decision_type = decision.get('decision', 'unknown')
            reason = decision.get('reason', 'unknown')
            self.get_logger().info(f"Guard decision published: {decision_type} - {reason}")
            
        except Exception as e:
            self.get_logger().error(f"Guard decision publishing error: {e}")

    def validate_intent_callback(self, request, response):
        """Handle service callback for intent validation."""
        try:
            intent_type = request.intent_result.intent_type
            confidence = request.intent_result.confidence
            
            self.get_logger().info(f"Intent validation service called: {intent_type}")
            
            # Create intent dict for FastAPI
            intent_dict = {
                'intent': intent_type,
                'confidence': confidence
            }
            
            # Get FastAPI guard decision
            fastapi_decision = self.call_fastapi_guard_intent(intent_dict)
            
            # Combine with enhanced analysis if available
            if self.last_enhanced_analysis and fastapi_decision:
                combined_decision = self.combine_intent_decisions(
                    request.intent_result, self.last_enhanced_analysis, fastapi_decision
                )
            else:
                combined_decision = fastapi_decision
            
            # Prepare response
            if combined_decision:
                decision_type = combined_decision.get('decision', 'allow')
                
                response.validation_successful = True
                response.intent_approved = decision_type == 'allow'
                response.requires_confirmation = decision_type == 'need_confirm'
                response.rejection_reason = combined_decision.get('reason', '')
                
                if 'prompt' in combined_decision:
                    response.confirmation_prompt = combined_decision['prompt']
                
                response.safety_constraints_updated = True
                response.guard_analysis = json.dumps(combined_decision)
            else:
                response.validation_successful = False
                response.error_message = "Guard validation failed"
            
            return response
            
        except Exception as e:
            self.get_logger().error(f"Intent validation callback error: {e}")
            response.validation_successful = False
            response.error_message = str(e)
            return response

    def start_monitoring_threads(self):
        """Start monitoring and metrics threads."""
        try:
            # Performance monitoring thread
            perf_thread = threading.Thread(
                target=self.performance_monitoring_loop,
                daemon=True
            )
            perf_thread.start()
            
            # Health check thread
            health_thread = threading.Thread(
                target=self.health_check_loop,
                daemon=True
            )
            health_thread.start()
            
            self.get_logger().info("Guard bridge monitoring threads started")
            
        except Exception as e:
            self.get_logger().error(f"Monitoring threads start error: {e}")

    def performance_monitoring_loop(self):
        """Monitor guard bridge performance."""
        while rclpy.ok():
            try:
                # Calculate performance metrics
                if self.decision_times:
                    avg_decision_time = sum(self.decision_times) / len(self.decision_times)
                    max_decision_time = max(self.decision_times)
                    
                    # Clear old times
                    self.decision_times = self.decision_times[-100:]  # Keep last 100
                    
                    # Publish metrics
                    metrics = {
                        'avg_decision_time_ms': avg_decision_time,
                        'max_decision_time_ms': max_decision_time,
                        'stats': self.decision_stats,
                        'enhanced_guard_available': self.enhanced_guard_available,
                        'fastapi_guard_available': self.fastapi_guard_available,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    metrics_msg = String()
                    metrics_msg.data = json.dumps(metrics)
                    self.guard_metrics_pub.publish(metrics_msg)
                    
                    # Alert on performance issues
                    if (self.get_parameter('monitoring.alert_slow_decisions').value and 
                        avg_decision_time > self.max_decision_time):
                        self.get_logger().warning(f"Guard decision performance alert: {avg_decision_time:.1f}ms avg")
                
                time.sleep(30)  # Monitor every 30 seconds
                
            except Exception as e:
                self.get_logger().error(f"Performance monitoring error: {e}")
                time.sleep(60)

    def health_check_loop(self):
        """Monitor health of guard services."""
        while rclpy.ok():
            try:
                # Check FastAPI guard availability
                self.test_fastapi_guard_availability()
                
                # Check enhanced guard by monitoring recent analysis
                if self.last_enhanced_analysis:
                    last_analysis_time = datetime.fromisoformat(
                        self.last_enhanced_analysis.get('timestamp', datetime.now().isoformat())
                    )
                    if (datetime.now() - last_analysis_time).total_seconds() < 60:
                        self.enhanced_guard_available = True
                    else:
                        self.enhanced_guard_available = False
                        self.get_logger().warning("Enhanced Guard appears inactive")
                
                time.sleep(30)  # Health check every 30 seconds
                
            except Exception as e:
                self.get_logger().error(f"Health check error: {e}")
                time.sleep(60)


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)
    
    try:
        node = GuardFastAPIBridgeNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Guard-FastAPI Bridge error: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()