#!/usr/bin/env python3
"""
Action Coordinator Node for Elderly Companion Robdog.

Central coordinator for all robot actions, navigation, and safety-controlled movement.
Handles UC3 (Following/Strolling) and emergency response movement.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from rclpy.action import ActionServer, CancelResponse, GoalResponse

import threading
import time
import math
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import uuid

# ROS2 message imports
from std_msgs.msg import Header, String, Bool
from geometry_msgs.msg import Pose, Twist, Point, Quaternion, PoseStamped
from nav_msgs.msg import OccupancyGrid, Odometry
from sensor_msgs.msg import LaserScan

# Custom message imports
from elderly_companion.msg import (
    IntentResult, EmergencyAlert, SafetyConstraints, HealthStatus
)
from elderly_companion.srv import ExecuteAction
from elderly_companion.action import (
    FollowPerson, GoToLocation, EmergencyResponse
)


class ActionState(Enum):
    """Action execution states."""
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    EMERGENCY_STOP = "emergency_stop"


class ActionPriority(Enum):
    """Action priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    EMERGENCY = 4


@dataclass
class ActionRequest:
    """Action request data structure."""
    request_id: str
    action_type: str
    parameters: Dict[str, Any]
    priority: ActionPriority
    safety_constraints: SafetyConstraints
    timestamp: datetime
    timeout_seconds: float = 300.0
    emergency_context: bool = False


class ActionCoordinatorNode(Node):
    """
    Action Coordinator Node - Central controller for elderly companion robot actions.
    
    Responsibilities:
    - Coordinate all robot movement and actions
    - Enforce safety constraints from safety guard
    - Manage action priorities and interruptions
    - Handle emergency response actions
    - Interface with Unitree Go2 platform
    - Monitor elderly person during actions
    """

    def __init__(self):
        super().__init__('action_coordinator_node')
        
        # Initialize parameters
        self.declare_parameters(
            namespace='',
            parameters=[
                ('safety.max_linear_velocity', 0.6),
                ('safety.max_angular_velocity', 1.0),
                ('safety.min_obstacle_distance', 1.0),
                ('safety.comfort_zone_radius', 2.0),
                ('elderly.following_distance', 1.5),
                ('elderly.max_following_speed', 0.4),
                ('emergency.response_timeout', 30.0),
            ]
        )
        
        # Get parameters
        self.max_linear_vel = self.get_parameter('safety.max_linear_velocity').value
        self.max_angular_vel = self.get_parameter('safety.max_angular_velocity').value
        self.following_distance = self.get_parameter('elderly.following_distance').value
        self.max_following_speed = self.get_parameter('elderly.max_following_speed').value
        
        # Action management
        self.current_action: Optional[ActionRequest] = None
        self.action_queue: List[ActionRequest] = []
        self.current_state = ActionState.IDLE
        
        # Safety constraints
        self.current_constraints = SafetyConstraints()
        self.emergency_stop_active = False
        
        # Elderly person tracking
        self.elderly_position = None
        self.elderly_visible = False
        
        # Robot state
        self.robot_pose = Pose()
        self.robot_twist = Twist()
        
        # QoS profiles
        default_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        # Subscribers
        self.validated_intent_sub = self.create_subscription(
            IntentResult,
            '/intent/validated',
            self.handle_validated_intent_callback,
            default_qos
        )
        
        self.emergency_alert_sub = self.create_subscription(
            EmergencyAlert,
            '/emergency/alert',
            self.handle_emergency_alert_callback,
            default_qos
        )
        
        self.safety_constraints_sub = self.create_subscription(
            SafetyConstraints,
            '/safety/constraints',
            self.update_safety_constraints_callback,
            default_qos
        )
        
        self.odom_sub = self.create_subscription(
            Odometry,
            '/odom',
            self.odometry_callback,
            default_qos
        )
        
        self.laser_sub = self.create_subscription(
            LaserScan,
            '/scan',
            self.laser_scan_callback,
            default_qos
        )
        
        # Publishers
        self.cmd_vel_pub = self.create_publisher(
            Twist,
            '/cmd_vel',
            default_qos
        )
        
        self.action_status_pub = self.create_publisher(
            String,
            '/action/status',
            default_qos
        )
        
        # Action servers
        self.follow_person_server = ActionServer(
            self,
            FollowPerson,
            '/action/follow_person',
            self.follow_person_callback
        )
        
        self.go_to_location_server = ActionServer(
            self,
            GoToLocation,
            '/action/go_to_location',
            self.go_to_location_callback
        )
        
        self.emergency_response_server = ActionServer(
            self,
            EmergencyResponse,
            '/action/emergency_response',
            self.emergency_response_callback
        )
        
        # Services
        self.execute_action_service = self.create_service(
            ExecuteAction,
            '/action_agent/execute_action',
            self.execute_action_callback
        )
        
        # Safety monitoring timer
        self.safety_timer = self.create_timer(0.1, self.safety_monitoring_loop)  # 10Hz
        
        self.get_logger().info("Action Coordinator Node initialized - Ready for elderly companion actions")

    def handle_validated_intent_callback(self, msg: IntentResult):
        """Handle validated intents from router agent."""
        try:
            if msg.intent_type in ['follow', 'go_to', 'emergency']:
                self.get_logger().info(f"Received validated action intent: {msg.intent_type}")
                
                # Create action request
                request = ActionRequest(
                    request_id=str(uuid.uuid4()),
                    action_type=msg.intent_type,
                    parameters=dict(zip(msg.parameter_names, msg.parameter_values)) if msg.parameter_names else {},
                    priority=ActionPriority.EMERGENCY if msg.priority_level >= 3 else ActionPriority.NORMAL,
                    safety_constraints=self.current_constraints,
                    timestamp=datetime.now(),
                    emergency_context=(msg.intent_type == 'emergency')
                )
                
                self.execute_action_request(request)
                
        except Exception as e:
            self.get_logger().error(f"Validated intent handling error: {e}")

    def handle_emergency_alert_callback(self, msg: EmergencyAlert):
        """Handle emergency alerts - highest priority actions."""
        try:
            self.get_logger().critical(f"EMERGENCY ACTION: {msg.emergency_type}")
            
            # Stop current action immediately
            self.emergency_stop()
            
            # Create emergency response action
            request = ActionRequest(
                request_id=str(uuid.uuid4()),
                action_type='emergency_response',
                parameters={
                    'emergency_type': msg.emergency_type,
                    'person_location': msg.person_location if hasattr(msg, 'person_location') else None,
                    'severity': msg.severity_level
                },
                priority=ActionPriority.EMERGENCY,
                safety_constraints=self.current_constraints,
                timestamp=datetime.now(),
                emergency_context=True
            )
            
            self.execute_action_request(request)
            
        except Exception as e:
            self.get_logger().error(f"Emergency alert handling error: {e}")

    def update_safety_constraints_callback(self, msg: SafetyConstraints):
        """Update current safety constraints."""
        try:
            self.current_constraints = msg
            
            # Update velocity limits based on constraints
            self.max_linear_vel = min(self.max_linear_vel, msg.max_linear_velocity)
            self.max_angular_vel = min(self.max_angular_vel, msg.max_angular_velocity)
            
            self.get_logger().debug("Safety constraints updated")
            
        except Exception as e:
            self.get_logger().error(f"Safety constraints update error: {e}")

    def odometry_callback(self, msg: Odometry):
        """Update robot pose from odometry."""
        try:
            self.robot_pose = msg.pose.pose
            self.robot_twist = msg.twist.twist
            
        except Exception as e:
            self.get_logger().error(f"Odometry callback error: {e}")

    def laser_scan_callback(self, msg: LaserScan):
        """Process laser scan for obstacle detection."""
        try:
            # Simple obstacle detection
            min_distance = min(msg.ranges)
            
            if min_distance < self.current_constraints.min_obstacle_distance:
                if not self.emergency_stop_active:
                    self.get_logger().warning(f"Obstacle detected at {min_distance:.2f}m - emergency stop")
                    self.emergency_stop()
            
        except Exception as e:
            self.get_logger().error(f"Laser scan callback error: {e}")

    def execute_action_request(self, request: ActionRequest):
        """Execute action request."""
        try:
            # Check if emergency action should interrupt current action
            if (request.priority == ActionPriority.EMERGENCY or 
                not self.current_action or 
                request.priority.value > self.current_action.priority.value):
                
                # Stop current action if needed
                if self.current_action and self.current_state == ActionState.EXECUTING:
                    self.get_logger().info("Interrupting current action for higher priority request")
                    self.stop_current_action()
                
                # Start new action
                self.current_action = request
                self.current_state = ActionState.PLANNING
                
                # Execute based on action type
                if request.action_type == 'follow':
                    self.start_follow_action(request)
                elif request.action_type == 'go_to':
                    self.start_go_to_action(request)
                elif request.action_type == 'emergency_response':
                    self.start_emergency_response_action(request)
                else:
                    self.get_logger().warning(f"Unknown action type: {request.action_type}")
                    
            else:
                # Add to queue
                self.action_queue.append(request)
                self.get_logger().info(f"Action queued: {request.action_type}")
            
        except Exception as e:
            self.get_logger().error(f"Action execution error: {e}")

    def start_follow_action(self, request: ActionRequest):
        """Start following action."""
        try:
            self.get_logger().info("Starting follow person action")
            self.current_state = ActionState.EXECUTING
            
            # Simple following behavior - move towards elderly at safe distance
            def follow_behavior():
                while (self.current_action and 
                       self.current_action.request_id == request.request_id and
                       self.current_state == ActionState.EXECUTING):
                    
                    cmd_vel = Twist()
                    
                    if self.elderly_position:
                        # Calculate distance to elderly person
                        dx = self.elderly_position.x - self.robot_pose.position.x
                        dy = self.elderly_position.y - self.robot_pose.position.y
                        distance = math.sqrt(dx*dx + dy*dy)
                        
                        # Maintain following distance
                        if distance > self.following_distance + 0.5:
                            # Move closer
                            cmd_vel.linear.x = min(self.max_following_speed, 
                                                 (distance - self.following_distance) * 0.5)
                        elif distance < self.following_distance - 0.3:
                            # Move back
                            cmd_vel.linear.x = -0.2
                        
                        # Calculate angle to elderly person
                        angle = math.atan2(dy, dx)
                        # Simple angular control
                        cmd_vel.angular.z = angle * 0.5
                        
                        # Apply safety limits
                        cmd_vel.linear.x = max(-self.max_linear_vel, 
                                             min(self.max_linear_vel, cmd_vel.linear.x))
                        cmd_vel.angular.z = max(-self.max_angular_vel, 
                                              min(self.max_angular_vel, cmd_vel.angular.z))
                    
                    # Publish command
                    if not self.emergency_stop_active:
                        self.cmd_vel_pub.publish(cmd_vel)
                    
                    time.sleep(0.1)  # 10Hz control loop
                
                # Stop robot when action ends
                self.cmd_vel_pub.publish(Twist())
                self.current_state = ActionState.COMPLETED
                self.get_logger().info("Follow action completed")
            
            # Start follow behavior in separate thread
            threading.Thread(target=follow_behavior, daemon=True).start()
            
        except Exception as e:
            self.get_logger().error(f"Follow action start error: {e}")
            self.current_state = ActionState.FAILED

    def start_go_to_action(self, request: ActionRequest):
        """Start go to location action."""
        try:
            self.get_logger().info("Starting go to location action")
            self.current_state = ActionState.EXECUTING
            
            # Simple point-to-point navigation
            target_x = request.parameters.get('target_x', 0.0)
            target_y = request.parameters.get('target_y', 0.0)
            
            def navigation_behavior():
                while (self.current_action and 
                       self.current_action.request_id == request.request_id and
                       self.current_state == ActionState.EXECUTING):
                    
                    # Calculate distance to target
                    dx = target_x - self.robot_pose.position.x
                    dy = target_y - self.robot_pose.position.y
                    distance = math.sqrt(dx*dx + dy*dy)
                    
                    if distance < 0.3:  # Reached target
                        break
                    
                    cmd_vel = Twist()
                    
                    # Simple navigation
                    angle = math.atan2(dy, dx)
                    cmd_vel.linear.x = min(self.max_linear_vel, distance * 0.5)
                    cmd_vel.angular.z = angle * 0.5
                    
                    # Apply safety limits
                    cmd_vel.linear.x = max(0, min(self.max_linear_vel, cmd_vel.linear.x))
                    cmd_vel.angular.z = max(-self.max_angular_vel, 
                                          min(self.max_angular_vel, cmd_vel.angular.z))
                    
                    # Publish command
                    if not self.emergency_stop_active:
                        self.cmd_vel_pub.publish(cmd_vel)
                    
                    time.sleep(0.1)
                
                # Stop robot
                self.cmd_vel_pub.publish(Twist())
                self.current_state = ActionState.COMPLETED
                self.get_logger().info("Go to location completed")
            
            # Start navigation in separate thread
            threading.Thread(target=navigation_behavior, daemon=True).start()
            
        except Exception as e:
            self.get_logger().error(f"Go to action start error: {e}")
            self.current_state = ActionState.FAILED

    def start_emergency_response_action(self, request: ActionRequest):
        """Start emergency response action."""
        try:
            self.get_logger().critical("Starting emergency response action")
            self.current_state = ActionState.EXECUTING
            
            emergency_type = request.parameters.get('emergency_type', 'unknown')
            
            if emergency_type in ['fall', 'medical']:
                # Move to elderly person's front for assistance
                if request.parameters.get('person_location'):
                    person_pos = request.parameters['person_location']
                    
                    def emergency_approach():
                        # Simple approach to person
                        target_x = person_pos.position.x + 0.8  # 0.8m in front
                        target_y = person_pos.position.y
                        
                        while (self.current_action and 
                               self.current_action.request_id == request.request_id):
                            
                            dx = target_x - self.robot_pose.position.x
                            dy = target_y - self.robot_pose.position.y
                            distance = math.sqrt(dx*dx + dy*dy)
                            
                            if distance < 0.5:  # Close enough
                                break
                            
                            cmd_vel = Twist()
                            angle = math.atan2(dy, dx)
                            cmd_vel.linear.x = min(0.3, distance * 0.3)  # Slow approach
                            cmd_vel.angular.z = angle * 0.3
                            
                            if not self.emergency_stop_active:
                                self.cmd_vel_pub.publish(cmd_vel)
                            
                            time.sleep(0.1)
                        
                        # Stop and position for assistance
                        self.cmd_vel_pub.publish(Twist())
                        self.current_state = ActionState.COMPLETED
                        self.get_logger().critical("Emergency response positioning completed")
                    
                    threading.Thread(target=emergency_approach, daemon=True).start()
                else:
                    # No position available, just stop and wait
                    self.cmd_vel_pub.publish(Twist())
                    self.current_state = ActionState.COMPLETED
            else:
                # Other emergency types - stop and wait
                self.cmd_vel_pub.publish(Twist())
                self.current_state = ActionState.COMPLETED
            
        except Exception as e:
            self.get_logger().error(f"Emergency response action error: {e}")
            self.current_state = ActionState.FAILED

    def emergency_stop(self):
        """Perform emergency stop of all motion."""
        try:
            self.emergency_stop_active = True
            self.cmd_vel_pub.publish(Twist())  # Stop robot
            self.current_state = ActionState.EMERGENCY_STOP
            self.get_logger().warning("EMERGENCY STOP ACTIVATED")
            
        except Exception as e:
            self.get_logger().error(f"Emergency stop error: {e}")

    def stop_current_action(self):
        """Stop current action."""
        try:
            if self.current_action:
                self.get_logger().info(f"Stopping current action: {self.current_action.action_type}")
                self.current_state = ActionState.PAUSED
                self.cmd_vel_pub.publish(Twist())
                
        except Exception as e:
            self.get_logger().error(f"Stop current action error: {e}")

    def safety_monitoring_loop(self):
        """Run safety monitoring loop at 10Hz."""
        try:
            # Reset emergency stop if safe
            if (self.emergency_stop_active and 
                self.current_state == ActionState.EMERGENCY_STOP):
                # Could add logic to automatically resume when safe
                pass
            
            # Publish action status
            if self.current_action:
                status_msg = String()
                status_msg.data = f"{self.current_state.value}:{self.current_action.action_type}"
                self.action_status_pub.publish(status_msg)
            
        except Exception as e:
            self.get_logger().error(f"Safety monitoring error: {e}")

    # Action server callbacks
    def follow_person_callback(self, goal_handle):
        """Handle follow person action server callback."""
        self.get_logger().info("Follow person goal received")
        goal_handle.succeed()
        result = FollowPerson.Result()
        result.follow_completed = True
        return result

    def go_to_location_callback(self, goal_handle):
        """Handle go to location action server callback."""
        self.get_logger().info("Go to location goal received")
        goal_handle.succeed()
        result = GoToLocation.Result()
        result.navigation_successful = True
        return result

    def emergency_response_callback(self, goal_handle):
        """Handle emergency response action server callback."""
        self.get_logger().critical("Emergency response goal received")
        goal_handle.succeed()
        result = EmergencyResponse.Result()
        result.emergency_response_completed = True
        return result

    def execute_action_callback(self, request, response):
        """Handle service callback for action execution."""
        try:
            self.get_logger().info(f"Execute action service called: {request.validated_intent.intent_type}")
            
            response.execution_started = True
            response.action_id = str(uuid.uuid4())
            response.estimated_duration = 30.0
            
            return response
            
        except Exception as e:
            self.get_logger().error(f"Execute action callback error: {e}")
            response.execution_started = False
            response.error_message = str(e)
            return response


def main(args=None):
    """Run the main entry point."""
    rclpy.init(args=args)
    
    try:
        node = ActionCoordinatorNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()