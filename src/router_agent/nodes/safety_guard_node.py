#!/usr/bin/env python3
"""
Safety Guard Node for Elderly Companion Robdog.

Critical safety system that validates all intents and enforces safety constraints.
Ensures elderly safety through intent validation, emergency detection, and safety monitoring.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

import threading
import time
import json
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta

# ROS2 message imports
from std_msgs.msg import Header
from geometry_msgs.msg import Pose, Point
from elderly_companion.msg import (
    SpeechResult, EmotionData, IntentResult, HealthStatus, 
    EmergencyAlert, SafetyConstraints
)
from elderly_companion.srv import ValidateIntent, EmergencyDispatch


class SafetyLevel(Enum):
    """Safety levels for different situations."""
    CRITICAL = 4  # Immediate emergency response required
    HIGH = 3     # High caution, restricted actions
    MEDIUM = 2   # Normal caution, some restrictions
    LOW = 1      # Minimal restrictions
    SAFE = 0     # No restrictions


class EmergencyType(Enum):
    """Types of emergency situations."""
    MEDICAL = "medical"
    FALL = "fall"
    SOS = "sos"
    SECURITY = "security"
    SYSTEM_FAILURE = "system_failure"


@dataclass
class SafetyEvent:
    """Safety event data structure."""
    timestamp: datetime
    event_type: str
    severity: int
    description: str
    resolved: bool = False


class SafetyGuardNode(Node):
    """
    Safety Guard Node - The critical safety system for elderly companion robot.
    
    This node is responsible for:
    - Validating all intents before execution
    - Detecting emergency situations
    - Enforcing safety constraints
    - Monitoring system health and elderly wellbeing
    - Coordinating emergency response
    """

    def __init__(self):
        super().__init__('safety_guard_node')
        
        # Initialize parameters
        self.declare_parameters(
            namespace='',
            parameters=[
                ('safety.emergency_response_timeout_ms', 200),
                ('safety.max_motion_speed', 0.6),  # m/s
                ('safety.min_obstacle_distance', 1.0),  # meters
                ('safety.comfort_zone_radius', 2.0),  # meters
                ('safety.battery_emergency_level', 0.15),  # 15%
                ('safety.enable_fall_detection', True),
                ('safety.enable_voice_stress_detection', True),
                ('safety.enable_motion_constraints', True),
                ('elderly.health_monitoring.enabled', True),
                ('elderly.emergency_contacts', []),
                ('system.max_continuous_operation_hours', 16),
            ]
        )
        
        # Get parameters
        self.emergency_timeout_ms = self.get_parameter('safety.emergency_response_timeout_ms').value
        self.max_motion_speed = self.get_parameter('safety.max_motion_speed').value
        self.min_obstacle_distance = self.get_parameter('safety.min_obstacle_distance').value
        self.comfort_zone_radius = self.get_parameter('safety.comfort_zone_radius').value
        self.battery_emergency_level = self.get_parameter('safety.battery_emergency_level').value
        self.health_monitoring_enabled = self.get_parameter('elderly.health_monitoring.enabled').value
        
        # Safety state management
        self.current_safety_level = SafetyLevel.SAFE
        self.current_constraints = SafetyConstraints()
        self.safety_events: List[SafetyEvent] = []
        self.emergency_active = False
        self.last_health_check = datetime.now()
        
        # Elderly person tracking
        self.elderly_last_seen = None
        self.elderly_last_position = None
        self.elderly_responsive = True
        
        # System status tracking
        self.system_health = HealthStatus()
        self.last_system_update = datetime.now()
        
        # Emergency keywords for immediate response
        self.emergency_keywords = {
            'critical': ['救命', '急救', '不能呼吸', '胸痛', 'help', 'emergency', 'cant breathe', 'chest pain'],
            'medical': ['疼痛', '头晕', '摔倒', '不舒服', 'pain', 'dizzy', 'fell', 'hurt'],
            'sos': ['SOS', '求救', '报警', 'call police', 'call ambulance']
        }
        
        # Intent validation rules
        self.validation_rules = self.initialize_validation_rules()
        
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
        
        # Subscribers
        self.speech_result_sub = self.create_subscription(
            SpeechResult,
            '/speech/with_emotion',
            self.analyze_speech_safety_callback,
            default_qos
        )
        
        self.health_status_sub = self.create_subscription(
            HealthStatus,
            '/system/health',
            self.system_health_callback,
            default_qos
        )
        
        # Publishers
        self.emergency_alert_pub = self.create_publisher(
            EmergencyAlert,
            '/emergency/alert',
            critical_qos
        )
        
        self.safety_constraints_pub = self.create_publisher(
            SafetyConstraints,
            '/safety/constraints',
            default_qos
        )
        
        self.validated_intent_pub = self.create_publisher(
            IntentResult,
            '/intent/validated',
            default_qos
        )
        
        # Services
        self.validate_intent_service = self.create_service(
            ValidateIntent,
            '/safety_guard/validate_intent',
            self.validate_intent_callback
        )
        
        self.emergency_dispatch_service = self.create_service(
            EmergencyDispatch,
            '/safety_guard/emergency_dispatch',
            self.emergency_dispatch_callback
        )
        
        # Initialize safety constraints
        self.initialize_default_constraints()
        
        # Start safety monitoring thread
        self.monitoring_thread = threading.Thread(target=self.safety_monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        
        self.get_logger().info("Safety Guard Node initialized - Elderly safety protection active")

    def initialize_validation_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize intent validation rules."""
        return {
            'smart_home': {
                'risk_level': 'low',
                'requires_confirmation': False,
                'max_retries': 3,
                'timeout_seconds': 10
            },
            'emergency': {
                'risk_level': 'critical',
                'requires_confirmation': False,
                'max_retries': 0,
                'timeout_seconds': 1,
                'bypass_constraints': True
            },
            'follow': {
                'risk_level': 'medium',
                'requires_confirmation': True,
                'max_retries': 2,
                'timeout_seconds': 30,
                'motion_constraints': True
            },
            'chat': {
                'risk_level': 'safe',
                'requires_confirmation': False,
                'max_retries': 5,
                'timeout_seconds': 60
            },
            'memory': {
                'risk_level': 'low',
                'requires_confirmation': False,
                'max_retries': 3,
                'timeout_seconds': 15
            },
            'health_check': {
                'risk_level': 'low',
                'requires_confirmation': False,
                'max_retries': 2,
                'timeout_seconds': 20
            }
        }

    def initialize_default_constraints(self):
        """Initialize default safety constraints."""
        self.current_constraints.header = Header()
        self.current_constraints.header.stamp = self.get_clock().now().to_msg()
        self.current_constraints.header.frame_id = "safety_guard"
        
        # Motion constraints
        self.current_constraints.max_linear_velocity = self.max_motion_speed
        self.current_constraints.max_angular_velocity = 1.0
        self.current_constraints.max_acceleration = 0.5
        self.current_constraints.min_obstacle_distance = self.min_obstacle_distance
        self.current_constraints.comfort_zone_radius = self.comfort_zone_radius
        
        # Environmental constraints
        self.current_constraints.forbidden_areas = []
        self.current_constraints.max_slope_degrees = 15.0
        self.current_constraints.stairs_detected = False
        
        # Elderly-specific constraints
        self.current_constraints.elderly_present = True
        self.current_constraints.elderly_mobility_level = 0.8
        self.current_constraints.elderly_requires_assistance = False
        
        # Time-based constraints
        self.current_constraints.night_mode_active = False
        self.current_constraints.quiet_hours_active = False
        
        # Emergency capabilities
        self.current_constraints.emergency_override_enabled = True
        self.current_constraints.emergency_permissions = ['motion', 'communication', 'sensors']
        self.current_constraints.emergency_response_time_limit = self.emergency_timeout_ms / 1000.0
        
        # Interaction constraints
        self.current_constraints.max_interaction_distance = 3.0
        self.current_constraints.min_personal_space = 0.5
        self.current_constraints.physical_contact_allowed = False
        self.current_constraints.audio_recording_permitted = True
        
        # System constraints
        self.current_constraints.battery_reserve_level = self.battery_emergency_level
        self.current_constraints.maintenance_mode_active = False
        self.current_constraints.disabled_features = []
        self.current_constraints.max_continuous_operation_hours = 16
        
        # Publish initial constraints
        self.safety_constraints_pub.publish(self.current_constraints)

    def analyze_speech_safety_callback(self, msg: SpeechResult):
        """Analyze speech for safety concerns and emergency detection."""
        try:
            text = msg.text.lower()
            emotion = msg.emotion
            
            # Emergency keyword detection
            emergency_detected = self.detect_emergency_in_speech(text, emotion)
            
            if emergency_detected:
                self.handle_speech_emergency(msg, emergency_detected)
            
            # Health indicators monitoring
            if self.health_monitoring_enabled:
                self.monitor_health_indicators(text, emotion)
            
            # Stress level monitoring
            if emotion.stress_level > 0.7:
                self.handle_high_stress(msg)
            
            # Update elderly status
            self.update_elderly_status(msg)
            
        except Exception as e:
            self.get_logger().error(f"Speech safety analysis error: {e}")

    def detect_emergency_in_speech(self, text: str, emotion: EmotionData) -> Optional[str]:
        """Detect emergency keywords and patterns in speech."""
        try:
            # Check critical emergency keywords
            for keyword in self.emergency_keywords['critical']:
                if keyword in text:
                    self.get_logger().critical(f"CRITICAL EMERGENCY KEYWORD DETECTED: {keyword}")
                    return EmergencyType.MEDICAL.value
            
            # Check medical emergency keywords
            for keyword in self.emergency_keywords['medical']:
                if keyword in text:
                    if emotion.stress_level > 0.6:  # High stress confirms medical emergency
                        self.get_logger().warning(f"Medical emergency keyword with high stress: {keyword}")
                        return EmergencyType.MEDICAL.value
            
            # Check SOS keywords
            for keyword in self.emergency_keywords['sos']:
                if keyword in text:
                    self.get_logger().warning(f"SOS keyword detected: {keyword}")
                    return EmergencyType.SOS.value
            
            # Pattern-based emergency detection
            if emotion.stress_level > 0.8 and emotion.primary_emotion in ['fear', 'pain']:
                emergency_phrases = ['不能', '动不了', '站不起来', 'cant move', 'cant stand']
                for phrase in emergency_phrases:
                    if phrase in text:
                        return EmergencyType.FALL.value
            
            return None
            
        except Exception as e:
            self.get_logger().error(f"Emergency detection error: {e}")
            return None

    def handle_speech_emergency(self, speech_msg: SpeechResult, emergency_type: str):
        """Handle detected speech emergency."""
        try:
            self.get_logger().critical(f"EMERGENCY DETECTED: {emergency_type}")
            
            # Create emergency alert
            alert = EmergencyAlert()
            alert.header = Header()
            alert.header.stamp = self.get_clock().now().to_msg()
            alert.header.frame_id = "safety_guard"
            
            alert.emergency_type = emergency_type
            alert.severity_level = 4  # Critical
            alert.description = f"Emergency detected from speech: '{speech_msg.text}'"
            
            # Location information (if available)
            if speech_msg.speaker_location:
                alert.person_location = Pose()
                alert.person_location.position = speech_msg.speaker_location
            
            # Audio context
            alert.last_speech = speech_msg
            alert.distress_detected_in_voice = speech_msg.emotion.stress_level > 0.7
            
            # Set response flags
            alert.emergency_call_initiated = False
            alert.family_notified = False
            alert.requires_human_intervention = True
            alert.estimated_response_time_minutes = 5
            
            # Publish emergency alert
            self.emergency_alert_pub.publish(alert)
            
            # Set emergency state
            self.emergency_active = True
            self.current_safety_level = SafetyLevel.CRITICAL
            
            # Update safety constraints for emergency
            self.update_emergency_constraints()
            
            self.get_logger().critical("Emergency alert published - All systems alerted")
            
        except Exception as e:
            self.get_logger().error(f"Emergency handling error: {e}")

    def update_emergency_constraints(self):
        """Update safety constraints for emergency situations."""
        try:
            # Enable emergency override
            self.current_constraints.emergency_override_enabled = True
            self.current_constraints.emergency_permissions = [
                'motion', 'communication', 'sensors', 'override_quiet_hours'
            ]
            
            # Reduce response time limits
            self.current_constraints.emergency_response_time_limit = 0.2  # 200ms
            
            # Allow faster motion for emergency response
            self.current_constraints.max_linear_velocity = 1.0  # Increased for emergency
            
            # Reduce personal space requirements for assistance
            self.current_constraints.min_personal_space = 0.2
            self.current_constraints.physical_contact_allowed = True  # For assistance
            
            # Override quiet hours
            self.current_constraints.quiet_hours_active = False
            
            # Update timestamp
            self.current_constraints.header.stamp = self.get_clock().now().to_msg()
            
            # Publish updated constraints
            self.safety_constraints_pub.publish(self.current_constraints)
            
        except Exception as e:
            self.get_logger().error(f"Emergency constraints update error: {e}")

    def monitor_health_indicators(self, text: str, emotion: EmotionData):
        """Monitor health indicators from speech patterns."""
        try:
            health_concerns = []
            
            # Check for pain indicators
            pain_keywords = ['疼', '痛', '不舒服', 'pain', 'hurt', 'ache']
            for keyword in pain_keywords:
                if keyword in text:
                    health_concerns.append(f"pain_reported: {keyword}")
            
            # Check for confusion indicators
            confusion_keywords = ['忘记', '糊涂', '不记得', 'forget', 'confused', 'dont remember']
            for keyword in confusion_keywords:
                if keyword in text:
                    health_concerns.append(f"confusion_reported: {keyword}")
            
            # Check for mobility issues
            mobility_keywords = ['站不起来', '走不动', 'cant stand', 'cant walk', 'dizzy']
            for keyword in mobility_keywords:
                if keyword in text:
                    health_concerns.append(f"mobility_concern: {keyword}")
            
            # Log health concerns
            if health_concerns:
                self.get_logger().warning(f"Health indicators detected: {health_concerns}")
                
                # Create health monitoring event
                event = SafetyEvent(
                    timestamp=datetime.now(),
                    event_type="health_concern",
                    severity=2,
                    description=f"Health indicators: {', '.join(health_concerns)}"
                )
                self.safety_events.append(event)
            
        except Exception as e:
            self.get_logger().error(f"Health monitoring error: {e}")

    def handle_high_stress(self, speech_msg: SpeechResult):
        """Handle high stress situations."""
        try:
            stress_level = speech_msg.emotion.stress_level
            self.get_logger().warning(f"High stress detected: {stress_level:.2f}")
            
            # Adjust safety level based on stress
            if stress_level > 0.9:
                self.current_safety_level = SafetyLevel.HIGH
            elif stress_level > 0.7:
                self.current_safety_level = SafetyLevel.MEDIUM
            
            # Create stress monitoring event
            event = SafetyEvent(
                timestamp=datetime.now(),
                event_type="high_stress",
                severity=2 if stress_level > 0.8 else 1,
                description=f"High stress level detected: {stress_level:.2f}"
            )
            self.safety_events.append(event)
            
        except Exception as e:
            self.get_logger().error(f"High stress handling error: {e}")

    def update_elderly_status(self, speech_msg: SpeechResult):
        """Update elderly person status based on speech."""
        try:
            self.elderly_last_seen = datetime.now()
            self.elderly_responsive = True
            
            if speech_msg.speaker_location:
                self.elderly_last_position = speech_msg.speaker_location
            
        except Exception as e:
            self.get_logger().error(f"Elderly status update error: {e}")

    def system_health_callback(self, msg: HealthStatus):
        """Monitor system health status."""
        try:
            self.system_health = msg
            self.last_system_update = datetime.now()
            
            # Check for critical system issues
            if msg.battery_level < self.battery_emergency_level:
                self.handle_low_battery_emergency(msg.battery_level)
            
            if not msg.emergency_system_ready:
                self.handle_emergency_system_failure()
            
            # Update safety constraints based on system health
            self.update_constraints_from_health(msg)
            
        except Exception as e:
            self.get_logger().error(f"System health callback error: {e}")

    def handle_low_battery_emergency(self, battery_level: float):
        """Handle low battery emergency."""
        try:
            self.get_logger().critical(f"CRITICAL: Low battery emergency - {battery_level:.1%}")
            
            # Create emergency alert
            alert = EmergencyAlert()
            alert.header = Header()
            alert.header.stamp = self.get_clock().now().to_msg()
            alert.header.frame_id = "safety_guard"
            
            alert.emergency_type = EmergencyType.SYSTEM_FAILURE.value
            alert.severity_level = 3
            alert.description = f"Critical low battery: {battery_level:.1%}"
            alert.requires_human_intervention = True
            
            self.emergency_alert_pub.publish(alert)
            
            # Restrict motion to conserve battery
            self.current_constraints.max_linear_velocity = 0.2
            self.current_constraints.disabled_features = ['motion_following', 'non_emergency_actions']
            
        except Exception as e:
            self.get_logger().error(f"Low battery emergency handling error: {e}")

    def validate_intent_callback(self, request, response):
        """Handle service callback for intent validation."""
        try:
            intent = request.intent
            self.get_logger().info(f"Validating intent: {intent.intent_type}")
            
            # Get validation rules for this intent type
            rules = self.validation_rules.get(intent.intent_type, {})
            
            # Check if emergency override is active
            if self.emergency_active and intent.intent_type == 'emergency':
                response.approved = True
                response.priority_level = 4
                response.confidence_adjustment = 0.0
                response.requires_human_confirmation = False
                response.estimated_risk_level = 0  # Emergency actions are necessary
                return response
            
            # Validate based on current safety level
            approval_result = self.evaluate_intent_safety(intent, rules)
            
            # Populate response
            response.approved = approval_result['approved']
            response.rejection_reason = approval_result.get('rejection_reason', '')
            response.safety_constraints_violated = approval_result.get('constraints_violated', [])
            response.priority_level = approval_result.get('priority_level', 1)
            response.confidence_adjustment = approval_result.get('confidence_adjustment', 0.0)
            response.requires_human_confirmation = approval_result.get('requires_confirmation', False)
            response.alternative_suggestions = approval_result.get('alternatives', [])
            response.estimated_risk_level = approval_result.get('risk_level', 0)
            response.updated_constraints = self.current_constraints
            
            # Log validation result
            self.get_logger().info(f"Intent validation result: {response.approved} - {response.rejection_reason}")
            
            return response
            
        except Exception as e:
            self.get_logger().error(f"Intent validation error: {e}")
            response.approved = False
            response.rejection_reason = f"Validation error: {str(e)}"
            return response

    def evaluate_intent_safety(self, intent: IntentResult, rules: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate intent safety based on current conditions."""
        try:
            result = {
                'approved': False,
                'rejection_reason': '',
                'constraints_violated': [],
                'priority_level': 1,
                'confidence_adjustment': 0.0,
                'requires_confirmation': rules.get('requires_confirmation', False),
                'alternatives': [],
                'risk_level': 0
            }
            
            # Check safety level compatibility
            risk_level = rules.get('risk_level', 'low')
            
            if self.current_safety_level == SafetyLevel.CRITICAL:
                if risk_level != 'critical':
                    result['rejection_reason'] = "Critical safety mode active - only emergency actions allowed"
                    result['constraints_violated'] = ['critical_safety_mode']
                    return result
            
            elif self.current_safety_level == SafetyLevel.HIGH:
                if risk_level in ['medium', 'high']:
                    result['rejection_reason'] = "High safety mode active - action too risky"
                    result['constraints_violated'] = ['high_safety_mode']
                    return result
            
            # Check specific intent types
            if intent.intent_type == 'follow':
                if not self.validate_motion_intent(intent, result):
                    return result
            
            elif intent.intent_type == 'smart_home':
                if not self.validate_smart_home_intent(intent, result):
                    return result
            
            # If we get here, intent is approved
            result['approved'] = True
            result['priority_level'] = self.get_intent_priority(intent.intent_type)
            
            return result
            
        except Exception as e:
            return {
                'approved': False,
                'rejection_reason': f"Safety evaluation error: {str(e)}",
                'constraints_violated': ['evaluation_error']
            }

    def validate_motion_intent(self, intent: IntentResult, result: Dict[str, Any]) -> bool:
        """Validate motion-related intents."""
        try:
            # Check if motion is currently restricted
            if 'motion' in self.current_constraints.disabled_features:
                result['rejection_reason'] = "Motion currently disabled for safety"
                result['constraints_violated'] = ['motion_disabled']
                return False
            
            # Check battery level for motion
            if self.system_health.battery_level < 0.3:
                result['rejection_reason'] = "Battery too low for motion activities"
                result['constraints_violated'] = ['low_battery']
                result['alternatives'] = ['stationary_interaction', 'call_for_help']
                return False
            
            # Check if elderly person is present and safe
            if not self.elderly_responsive:
                result['rejection_reason'] = "Elderly person not responsive - motion restricted"
                result['constraints_violated'] = ['elderly_unresponsive']
                return False
            
            return True
            
        except Exception as e:
            result['rejection_reason'] = f"Motion validation error: {str(e)}"
            return False

    def validate_smart_home_intent(self, intent: IntentResult, result: Dict[str, Any]) -> bool:
        """Validate smart home control intents."""
        try:
            # Smart home actions are generally low risk
            # Check for system connectivity
            if not self.system_health.network_connected:
                result['rejection_reason'] = "Network disconnected - cannot control smart home"
                result['constraints_violated'] = ['network_disconnected']
                return False
            
            return True
            
        except Exception as e:
            result['rejection_reason'] = f"Smart home validation error: {str(e)}"
            return False

    def get_intent_priority(self, intent_type: str) -> int:
        """Get priority level for intent type."""
        priority_map = {
            'emergency': 4,
            'health_check': 3,
            'follow': 2,
            'smart_home': 1,
            'chat': 1,
            'memory': 1
        }
        return priority_map.get(intent_type, 1)

    def emergency_dispatch_callback(self, request, response):
        """Handle service callback for emergency dispatch."""
        try:
            self.get_logger().critical(f"Emergency dispatch requested: {request.emergency_type}")
            
            # Process emergency dispatch
            response.dispatch_successful = True
            response.reference_id = f"EMERGENCY_{int(time.time())}"
            response.estimated_response_time = "5-10 minutes"
            
            # Actions taken
            response.actions_taken = [
                "emergency_alert_triggered",
                "safety_constraints_updated",
                "system_status_logged"
            ]
            
            # Set emergency state
            self.emergency_active = True
            self.current_safety_level = SafetyLevel.CRITICAL
            
            return response
            
        except Exception as e:
            self.get_logger().error(f"Emergency dispatch error: {e}")
            response.dispatch_successful = False
            return response

    def safety_monitoring_loop(self):
        """Run continuous safety monitoring loop."""
        self.get_logger().info("Safety monitoring loop started")
        
        while rclpy.ok():
            try:
                # Check elderly person status
                self.check_elderly_wellness()
                
                # Check system health
                self.check_system_wellness()
                
                # Update safety constraints if needed
                self.update_dynamic_constraints()
                
                # Clean up old safety events
                self.cleanup_old_events()
                
                time.sleep(1.0)  # 1 second monitoring interval
                
            except Exception as e:
                self.get_logger().error(f"Safety monitoring loop error: {e}")
                time.sleep(5.0)  # Longer delay on error

    def check_elderly_wellness(self):
        """Check elderly person wellness indicators."""
        try:
            now = datetime.now()
            
            # Check if we haven't heard from elderly person recently
            if self.elderly_last_seen:
                time_since_contact = now - self.elderly_last_seen
                
                if time_since_contact > timedelta(hours=4):
                    self.get_logger().warning("No contact with elderly person for 4+ hours")
                    # Could trigger wellness check
                elif time_since_contact > timedelta(hours=8):
                    self.get_logger().error("No contact with elderly person for 8+ hours - wellness concern")
                    # Could trigger emergency check
            
        except Exception as e:
            self.get_logger().error(f"Elderly wellness check error: {e}")

    def check_system_wellness(self):
        """Check system wellness indicators."""
        try:
            now = datetime.now()
            
            # Check if system health updates are current
            if self.last_system_update:
                time_since_update = now - self.last_system_update
                
                if time_since_update > timedelta(minutes=5):
                    self.get_logger().warning("System health updates delayed")
                    self.current_safety_level = SafetyLevel.MEDIUM
            
        except Exception as e:
            self.get_logger().error(f"System wellness check error: {e}")

    def update_dynamic_constraints(self):
        """Update safety constraints based on current conditions."""
        try:
            # Update timestamp
            self.current_constraints.header.stamp = self.get_clock().now().to_msg()
            
            # Publish updated constraints
            self.safety_constraints_pub.publish(self.current_constraints)
            
        except Exception as e:
            self.get_logger().error(f"Dynamic constraints update error: {e}")

    def cleanup_old_events(self):
        """Clean up old safety events."""
        try:
            cutoff_time = datetime.now() - timedelta(hours=24)
            self.safety_events = [
                event for event in self.safety_events 
                if event.timestamp > cutoff_time or not event.resolved
            ]
        except Exception as e:
            self.get_logger().error(f"Event cleanup error: {e}")

    def update_constraints_from_health(self, health_msg: HealthStatus):
        """Update constraints based on system health."""
        try:
            # Update based on battery level
            if health_msg.battery_level < 0.3:
                self.current_constraints.max_linear_velocity = 0.3  # Conserve battery
            
            # Update based on system capabilities
            if not health_msg.motion_system_ok:
                if 'motion' not in self.current_constraints.disabled_features:
                    self.current_constraints.disabled_features.append('motion')
            
            if not health_msg.audio_system_ok:
                if 'audio_interaction' not in self.current_constraints.disabled_features:
                    self.current_constraints.disabled_features.append('audio_interaction')
            
        except Exception as e:
            self.get_logger().error(f"Constraints update from health error: {e}")


def main(args=None):
    """Run the main entry point."""
    rclpy.init(args=args)
    
    try:
        node = SafetyGuardNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()