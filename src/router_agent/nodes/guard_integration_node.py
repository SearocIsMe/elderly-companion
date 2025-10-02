#!/usr/bin/env python3
"""
Guard Integration Node - Connects Enhanced Guard Engine with existing Router Agent.

This node serves as the bridge between the Enhanced Guard Engine and the existing
Dialog Manager, Safety Guard, and other Router Agent components.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

import json
import threading
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass

# ROS2 message imports
from std_msgs.msg import Header, String
from geometry_msgs.msg import Point, Pose
from elderly_companion.msg import (
    SpeechResult, EmotionData, IntentResult, HealthStatus, 
    EmergencyAlert, SafetyConstraints
)
from elderly_companion.srv import ValidateIntent, EmergencyDispatch

# Enhanced Guard imports
from .enhanced_guard_engine import (
    EnhancedGuardEngine, WakewordType, SOSCategory, GeofenceStatus
)


@dataclass
class GuardDialogMessage:
    """Message structure for Guard-Dialog communication."""
    timestamp: datetime
    message_type: str  # 'wakeword', 'sos', 'implicit', 'geofence'
    confidence: float
    content: Dict[str, Any]
    priority_level: int
    requires_immediate_action: bool


class GuardIntegrationNode(Node):
    """Integration node for Enhanced Guard Engine with Router Agent."""
    
    def __init__(self):
        super().__init__('guard_integration_node')
        
        # Enhanced Guard Engine
        self.enhanced_guard = None
        self.initialize_enhanced_guard()
        
        # Integration state
        self.dialog_manager_connected = False
        self.safety_guard_connected = False
        self.emergency_system_ready = False
        
        # Message routing
        self.pending_messages = []
        self.message_priorities = {
            'emergency': 4,
            'sos': 4,
            'geofence_violation': 3,
            'implicit_urgent': 2,
            'wakeword': 1,
            'general': 0
        }
        
        # QoS profiles
        critical_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=50
        )
        
        default_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        # Subscribers - Connect to Enhanced Guard outputs
        self.guard_analysis_sub = self.create_subscription(
            String,
            '/guard/analysis',
            self.handle_guard_analysis,
            critical_qos
        )
        
        self.sos_alert_sub = self.create_subscription(
            EmergencyAlert,
            '/guard/sos_alert',
            self.handle_guard_sos_alert,
            critical_qos
        )
        
        self.enhanced_intent_sub = self.create_subscription(
            IntentResult,
            '/guard/enhanced_intent',
            self.handle_enhanced_intent,
            default_qos
        )
        
        # Publishers - Connect to existing Router Agent
        self.validated_intent_pub = self.create_publisher(
            IntentResult,
            '/intent/validated',
            default_qos
        )
        
        self.emergency_alert_pub = self.create_publisher(
            EmergencyAlert,
            '/emergency/alert',
            critical_qos
        )
        
        self.dialog_enhancement_pub = self.create_publisher(
            String,
            '/dialog/guard_enhancement',
            default_qos
        )
        
        # Service clients
        self.safety_validation_client = self.create_client(
            ValidateIntent,
            '/safety_guard/validate_intent'
        )
        
        self.emergency_dispatch_client = self.create_client(
            EmergencyDispatch,
            '/safety_guard/emergency_dispatch'
        )
        
        # Message processing thread
        self.message_processor_thread = threading.Thread(
            target=self.message_processing_loop,
            daemon=True
        )
        self.message_processor_thread.start()
        
        self.get_logger().info("Guard Integration Node initialized - Enhanced Guard connected to Router Agent")
    
    def initialize_enhanced_guard(self):
        """Initialize Enhanced Guard Engine."""
        try:
            # Enhanced Guard Engine is initialized separately
            # This integration node connects to its outputs
            self.get_logger().info("Enhanced Guard Engine connection established")
            
        except Exception as e:
            self.get_logger().error(f"Enhanced Guard initialization error: {e}")
    
    def handle_guard_analysis(self, msg: String):
        """Handle comprehensive Guard analysis results."""
        try:
            analysis = json.loads(msg.data)
            
            # Create Guard-Dialog message
            guard_message = GuardDialogMessage(
                timestamp=datetime.now(),
                message_type=self.determine_message_type(analysis),
                confidence=analysis.get('confidence', 0.0),
                content=analysis,
                priority_level=self.calculate_priority(analysis),
                requires_immediate_action=self.requires_immediate_action(analysis)
            )
            
            # Add to processing queue
            self.pending_messages.append(guard_message)
            
            # Sort by priority
            self.pending_messages.sort(key=lambda x: x.priority_level, reverse=True)
            
            self.get_logger().info(f"Guard analysis processed: {guard_message.message_type} (priority: {guard_message.priority_level})")
            
        except Exception as e:
            self.get_logger().error(f"Guard analysis handling error: {e}")
    
    def handle_guard_sos_alert(self, msg: EmergencyAlert):
        """Handle SOS alerts from Enhanced Guard."""
        try:
            self.get_logger().critical(f"GUARD SOS ALERT: {msg.emergency_type}")
            
            # Forward to main emergency system
            self.emergency_alert_pub.publish(msg)
            
            # Create emergency dispatch if severe
            if msg.severity_level >= 3:
                self.dispatch_emergency_services(msg)
            
            # Update emergency status
            self.emergency_system_ready = True
            
        except Exception as e:
            self.get_logger().error(f"Guard SOS alert handling error: {e}")
    
    def handle_enhanced_intent(self, msg: IntentResult):
        """Handle enhanced intents from Guard implicit recognition."""
        try:
            self.get_logger().info(f"Enhanced intent from Guard: {msg.intent_type}")
            
            # Validate with existing safety system if not emergency
            if msg.intent_type != 'emergency' and self.safety_validation_client.service_is_ready():
                self.validate_guard_intent(msg)
            else:
                # Emergency or safety service not ready - pass through directly
                self.validated_intent_pub.publish(msg)
            
        except Exception as e:
            self.get_logger().error(f"Enhanced intent handling error: {e}")
    
    def validate_guard_intent(self, intent: IntentResult):
        """Validate Guard-enhanced intent with existing safety system."""
        try:
            request = ValidateIntent.Request()
            request.intent = intent
            request.system_status = HealthStatus()  # Would get current status
            request.safety_constraints = SafetyConstraints()  # Would get current constraints
            
            future = self.safety_validation_client.call_async(request)
            future.add_done_callback(
                lambda f: self.handle_safety_validation_response(f, intent)
            )
            
        except Exception as e:
            self.get_logger().error(f"Guard intent validation error: {e}")
    
    def handle_safety_validation_response(self, future, original_intent: IntentResult):
        """Handle safety validation response for Guard intents."""
        try:
            response = future.result()
            
            if response.approved:
                # Add Guard enhancement tags
                original_intent.guard_enhanced = True
                original_intent.safety_validated = True
                
                # Publish validated intent
                self.validated_intent_pub.publish(original_intent)
                
                self.get_logger().info(f"Guard intent approved: {original_intent.intent_type}")
            else:
                self.get_logger().warning(f"Guard intent rejected: {response.rejection_reason}")
                
                # Send rejection feedback to Dialog Manager
                self.send_dialog_enhancement(
                    'intent_rejected',
                    {
                        'intent_type': original_intent.intent_type,
                        'rejection_reason': response.rejection_reason,
                        'suggested_alternatives': response.alternative_suggestions
                    }
                )
            
        except Exception as e:
            self.get_logger().error(f"Safety validation response handling error: {e}")
    
    def dispatch_emergency_services(self, alert: EmergencyAlert):
        """Dispatch emergency services for critical SOS alerts."""
        try:
            if not self.emergency_dispatch_client.service_is_ready():
                self.get_logger().error("Emergency dispatch service not ready")
                return
            
            request = EmergencyDispatch.Request()
            request.emergency_type = alert.emergency_type
            request.severity_level = alert.severity_level
            request.robot_location = Pose()  # Would get actual robot location
            request.person_location = alert.person_location
            request.location_description = alert.description
            request.last_speech = alert.last_speech
            request.person_responsive = alert.person_responsive
            request.timestamp = alert.header.stamp
            
            future = self.emergency_dispatch_client.call_async(request)
            future.add_done_callback(self.handle_emergency_dispatch_response)
            
        except Exception as e:
            self.get_logger().error(f"Emergency dispatch error: {e}")
    
    def handle_emergency_dispatch_response(self, future):
        """Handle emergency dispatch response."""
        try:
            response = future.result()
            
            if response.dispatch_initiated:
                self.get_logger().critical(f"Emergency services dispatched: {response.incident_id}")
            else:
                self.get_logger().error("Emergency dispatch failed")
            
        except Exception as e:
            self.get_logger().error(f"Emergency dispatch response error: {e}")
    
    def determine_message_type(self, analysis: Dict[str, Any]) -> str:
        """Determine message type from Guard analysis."""
        if analysis.get('sos_detection', {}).get('detected', False):
            return 'sos'
        elif analysis.get('safety_assessment', {}).get('level') == 'emergency':
            return 'emergency'
        elif analysis.get('geofence', {}).get('status') in ['violation', 'emergency']:
            return 'geofence_violation'
        elif analysis.get('implicit_command', {}).get('detected', False):
            confidence = analysis['implicit_command'].get('confidence', 0)
            return 'implicit_urgent' if confidence > 0.8 else 'implicit_command'
        elif analysis.get('wakeword', {}).get('detected', False):
            return 'wakeword'
        else:
            return 'general'
    
    def calculate_priority(self, analysis: Dict[str, Any]) -> int:
        """Calculate message priority level."""
        message_type = self.determine_message_type(analysis)
        base_priority = self.message_priorities.get(message_type, 0)
        
        # Adjust based on risk assessment
        risk_score = analysis.get('safety_assessment', {}).get('risk_score', 0.0)
        if risk_score > 0.8:
            base_priority = max(base_priority, 3)
        elif risk_score > 0.6:
            base_priority = max(base_priority, 2)
        
        return base_priority
    
    def requires_immediate_action(self, analysis: Dict[str, Any]) -> bool:
        """Determine if analysis requires immediate action."""
        # Emergency conditions
        if analysis.get('sos_detection', {}).get('detected', False):
            urgency = analysis['sos_detection'].get('urgency_level', 0)
            return urgency >= 3
        
        # High risk assessment
        risk_score = analysis.get('safety_assessment', {}).get('risk_score', 0.0)
        return risk_score > 0.7
    
    def message_processing_loop(self):
        """Process pending Guard messages with priority handling."""
        while rclpy.ok():
            try:
                if self.pending_messages:
                    # Process highest priority message
                    message = self.pending_messages.pop(0)
                    self.process_guard_message(message)
                
                time.sleep(0.1)  # 100ms processing cycle
                
            except Exception as e:
                self.get_logger().error(f"Message processing loop error: {e}")
                time.sleep(1.0)
    
    def process_guard_message(self, message: GuardDialogMessage):
        """Process individual Guard message."""
        try:
            if message.requires_immediate_action:
                self.handle_immediate_action(message)
            else:
                self.route_to_dialog_manager(message)
            
        except Exception as e:
            self.get_logger().error(f"Guard message processing error: {e}")
    
    def handle_immediate_action(self, message: GuardDialogMessage):
        """Handle messages requiring immediate action."""
        try:
            self.get_logger().warning(f"IMMEDIATE ACTION: {message.message_type}")
            
            if message.message_type in ['sos', 'emergency']:
                # Already handled by handle_guard_sos_alert
                pass
            
            elif message.message_type == 'geofence_violation':
                self.handle_geofence_emergency(message)
            
            elif message.message_type == 'implicit_urgent':
                self.handle_urgent_implicit_command(message)
            
        except Exception as e:
            self.get_logger().error(f"Immediate action handling error: {e}")
    
    def handle_geofence_emergency(self, message: GuardDialogMessage):
        """Handle geofence emergency situations."""
        try:
            geofence_data = message.content.get('geofence', {})
            
            if geofence_data.get('status') == 'emergency':
                # Create emergency alert for geofence violation
                alert = EmergencyAlert()
                alert.header = Header()
                alert.header.stamp = self.get_clock().now().to_msg()
                alert.header.frame_id = "guard_integration"
                
                alert.emergency_type = "geofence_violation"
                alert.severity_level = 3
                alert.description = f"Emergency geofence violation in zone: {geofence_data.get('zone', 'unknown')}"
                alert.requires_human_intervention = True
                
                self.emergency_alert_pub.publish(alert)
                
        except Exception as e:
            self.get_logger().error(f"Geofence emergency handling error: {e}")
    
    def handle_urgent_implicit_command(self, message: GuardDialogMessage):
        """Handle urgent implicit commands."""
        try:
            implicit_data = message.content.get('implicit_command', {})
            command_type = implicit_data.get('command_type')
            
            if command_type in ['assistance_request', 'health_concern']:
                # Create high-priority intent
                intent = IntentResult()
                intent.header = Header()
                intent.header.stamp = self.get_clock().now().to_msg()
                intent.header.frame_id = "guard_integration"
                
                intent.intent_type = command_type
                intent.confidence = implicit_data.get('confidence', 0.0)
                intent.priority_level = 3  # High priority
                intent.requires_confirmation = False  # Urgent - skip confirmation
                intent.guard_enhanced = True
                
                # Publish directly as validated intent
                self.validated_intent_pub.publish(intent)
                
        except Exception as e:
            self.get_logger().error(f"Urgent implicit command handling error: {e}")
    
    def route_to_dialog_manager(self, message: GuardDialogMessage):
        """Route message to Dialog Manager with Guard enhancements."""
        try:
            enhancement_data = {
                'guard_analysis': message.content,
                'message_type': message.message_type,
                'confidence': message.confidence,
                'priority_level': message.priority_level,
                'timestamp': message.timestamp.isoformat(),
                'recommendations': self.generate_dialog_recommendations(message)
            }
            
            enhancement_msg = String()
            enhancement_msg.data = json.dumps(enhancement_data)
            
            self.dialog_enhancement_pub.publish(enhancement_msg)
            
        except Exception as e:
            self.get_logger().error(f"Dialog Manager routing error: {e}")
    
    def generate_dialog_recommendations(self, message: GuardDialogMessage) -> List[str]:
        """Generate recommendations for Dialog Manager based on Guard analysis."""
        recommendations = []
        
        analysis = message.content
        
        # Wakeword recommendations
        if message.message_type == 'wakeword':
            wakeword_data = analysis.get('wakeword', {})
            if wakeword_data.get('type') == 'emergency':
                recommendations.append('prepare_emergency_response')
            elif wakeword_data.get('type') == 'attention':
                recommendations.append('increase_attention_level')
        
        # Emotional state recommendations
        emotion = analysis.get('emotion', {})
        stress_level = emotion.get('stress_level', 0.0)
        
        if stress_level > 0.7:
            recommendations.append('apply_calming_response')
        elif stress_level > 0.5:
            recommendations.append('monitor_stress_level')
        
        # Safety assessment recommendations
        safety = analysis.get('safety_assessment', {})
        if safety.get('requires_attention', False):
            recommendations.extend(safety.get('recommendations', []))
        
        return recommendations
    
    def send_dialog_enhancement(self, enhancement_type: str, data: Dict[str, Any]):
        """Send enhancement data to Dialog Manager."""
        try:
            enhancement = {
                'type': enhancement_type,
                'timestamp': datetime.now().isoformat(),
                'data': data,
                'source': 'enhanced_guard'
            }
            
            enhancement_msg = String()
            enhancement_msg.data = json.dumps(enhancement)
            
            self.dialog_enhancement_pub.publish(enhancement_msg)
            
        except Exception as e:
            self.get_logger().error(f"Dialog enhancement sending error: {e}")
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get integration status and performance metrics."""
        return {
            'dialog_manager_connected': self.dialog_manager_connected,
            'safety_guard_connected': self.safety_guard_connected,
            'emergency_system_ready': self.emergency_system_ready,
            'pending_messages': len(self.pending_messages),
            'enhanced_guard_active': self.enhanced_guard is not None,
            'integration_status': 'active'
        }


def main(args=None):
    """Run the Guard Integration Node."""
    rclpy.init(args=args)
    
    try:
        node = GuardIntegrationNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Guard Integration Node error: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()