#!/usr/bin/env python3
"""
Unitree Go2 Bridge Node for Elderly Companion Robdog
Bridges ROS2 Action Agent with Unitree Go2 SDK
Implements elderly-specific safety constraints and motion patterns
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

import threading
import time
import math
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

# Unitree SDK imports
try:
    import unitree_sdk2py
    from unitree_sdk2py.core.channel import ChannelFactoryInitialize
    from unitree_sdk2py.go2.sport.sport_client import SportClient
    from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowState_
    from unitree_sdk2py.idl.default import unitree_go_msg_dds__SportModeState_
    UNITREE_SDK_AVAILABLE = True
except ImportError:
    UNITREE_SDK_AVAILABLE = False
    print("Warning: Unitree SDK not available, using mock implementation")

# ROS2 message imports
from std_msgs.msg import Header, String, Bool, Float32MultiArray
from geometry_msgs.msg import Pose, Twist, Point, Quaternion, Vector3
from sensor_msgs.msg import JointState, Imu, PointCloud2
from nav_msgs.msg import Odometry
from tf2_msgs.msg import TFMessage

# Custom message imports
from elderly_companion.msg import (
    SafetyConstraints, EmergencyAlert, HealthStatus
)


class RobotState(Enum):
    """Robot operational states"""
    STANDING = "standing"
    WALKING = "walking"
    SITTING = "sitting"
    LYING = "lying"
    EMERGENCY_STOP = "emergency_stop"
    ERROR = "error"


class GaitType(Enum):
    """Gait types optimized for elderly companionship"""
    ELDERLY_WALK = "elderly_walk"      # Very gentle, slow gait
    NORMAL_WALK = "normal_walk"        # Standard walking gait
    CAREFUL_STEP = "careful_step"      # Extra careful stepping
    EMERGENCY_APPROACH = "emergency_approach"  # Quick but controlled approach


@dataclass
class ElderlyMotionConstraints:
    """Motion constraints optimized for elderly safety"""
    max_linear_velocity: float = 0.6      # m/s - elderly-safe speed
    max_angular_velocity: float = 0.8     # rad/s - gentle turning
    max_acceleration: float = 0.3         # m/s² - gentle acceleration
    max_body_height: float = 0.35         # m - stable body height
    min_body_height: float = 0.15         # m - minimum height
    comfort_zone_radius: float = 2.0      # m - radius around elderly
    emergency_stop_distance: float = 0.8  # m - emergency stop distance
    gentle_approach_distance: float = 1.5 # m - start gentle approach
    max_slope_angle: float = 15.0         # degrees - maximum slope
    stability_margin: float = 0.1         # m - stability margin


class UnitreeGo2BridgeNode(Node):
    """
    Unitree Go2 Bridge Node - Interface between ROS2 and Unitree Go2 hardware.
    
    Responsibilities:
    - Convert ROS2 commands to Unitree SDK commands
    - Implement elderly-specific safety constraints
    - Monitor robot health and status
    - Handle emergency stops and safety protocols
    - Provide gentle motion patterns for elderly comfort
    - Stream sensor data back to ROS2 ecosystem
    """

    def __init__(self):
        super().__init__('unitree_go2_bridge_node')
        
        # Initialize parameters
        self.declare_parameters(
            namespace='',
            parameters=[
                ('unitree.network_interface', 'eth0'),
                ('unitree.robot_ip', '192.168.123.15'),
                ('unitree.control_level', 'high'),  # high, low
                ('safety.elderly_mode', True),
                ('safety.max_linear_velocity', 0.6),
                ('safety.max_angular_velocity', 0.8),
                ('safety.emergency_stop_enabled', True),
                ('motion.default_body_height', 0.25),
                ('motion.default_gait', 'elderly_walk'),
                ('motion.step_frequency', 1.5),  # Hz - slower for elderly
                ('monitoring.publish_frequency', 50.0),  # Hz
                ('monitoring.health_check_interval', 1.0),  # seconds
            ]
        )
        
        # Get parameters
        self.network_interface = self.get_parameter('unitree.network_interface').value
        self.robot_ip = self.get_parameter('unitree.robot_ip').value
        self.elderly_mode = self.get_parameter('safety.elderly_mode').value
        self.emergency_stop_enabled = self.get_parameter('safety.emergency_stop_enabled').value
        self.default_body_height = self.get_parameter('motion.default_body_height').value
        self.default_gait = self.get_parameter('motion.default_gait').value
        self.publish_frequency = self.get_parameter('monitoring.publish_frequency').value
        
        # Motion constraints for elderly care
        self.motion_constraints = ElderlyMotionConstraints()
        self.motion_constraints.max_linear_velocity = self.get_parameter('safety.max_linear_velocity').value
        self.motion_constraints.max_angular_velocity = self.get_parameter('safety.max_angular_velocity').value
        
        # Robot state management
        self.current_state = RobotState.STANDING
        self.current_gait = GaitType.ELDERLY_WALK
        self.emergency_stop_active = False
        self.robot_ready = False
        
        # Safety constraints from safety guard
        self.current_safety_constraints = SafetyConstraints()
        
        # Command tracking
        self.last_cmd_vel = Twist()
        self.last_command_time = datetime.now()
        self.command_timeout = 0.5  # seconds
        
        # Unitree SDK components
        self.sport_client = None
        self.low_state = None
        self.sport_state = None
        
        # QoS profiles
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )
        
        default_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        # Subscribers
        self.cmd_vel_sub = self.create_subscription(
            Twist,
            '/cmd_vel',
            self.cmd_vel_callback,
            default_qos
        )
        
        self.safety_constraints_sub = self.create_subscription(
            SafetyConstraints,
            '/safety/constraints',
            self.safety_constraints_callback,
            default_qos
        )
        
        self.emergency_alert_sub = self.create_subscription(
            EmergencyAlert,
            '/emergency/alert',
            self.emergency_alert_callback,
            default_qos
        )
        
        # Publishers
        self.odom_pub = self.create_publisher(
            Odometry,
            '/odom',
            sensor_qos
        )
        
        self.joint_states_pub = self.create_publisher(
            JointState,
            '/joint_states',
            sensor_qos
        )
        
        self.imu_pub = self.create_publisher(
            Imu,
            '/imu',
            sensor_qos
        )
        
        self.robot_status_pub = self.create_publisher(
            String,
            '/robot/status',
            default_qos
        )
        
        self.health_status_pub = self.create_publisher(
            HealthStatus,
            '/system/health',
            default_qos
        )
        
        # Initialize Unitree SDK
        self.initialize_unitree_sdk()
        
        # Start monitoring loops
        self.start_monitoring_loops()
        
        self.get_logger().info("Unitree Go2 Bridge Node initialized - Elderly companion robot ready")

    def initialize_unitree_sdk(self):
        """Initialize Unitree SDK connection"""
        try:
            if not UNITREE_SDK_AVAILABLE:
                self.get_logger().warning("Unitree SDK not available - using mock implementation")
                self.robot_ready = True  # Mock initialization
                return
            
            # Initialize channel factory
            ChannelFactoryInitialize(0, self.network_interface)
            
            # Create sport client for high-level control
            self.sport_client = SportClient()
            self.sport_client.SetTimeout(3.0)
            self.sport_client.Init()
            
            # Wait for connection
            for i in range(10):  # 10 second timeout
                if self.sport_client.CheckConnection():
                    break
                time.sleep(1.0)
                self.get_logger().info(f"Waiting for Unitree Go2 connection... {i+1}/10")
            
            if self.sport_client.CheckConnection():
                self.robot_ready = True
                self.get_logger().info("Connected to Unitree Go2 successfully")
                
                # Set robot to standing position for elderly safety
                self.set_initial_robot_state()
            else:
                self.get_logger().error("Failed to connect to Unitree Go2")
                self.robot_ready = False
                
        except Exception as e:
            self.get_logger().error(f"Unitree SDK initialization error: {e}")
            self.robot_ready = False

    def set_initial_robot_state(self):
        """Set robot to initial safe state for elderly interaction"""
        try:
            if not self.robot_ready or not self.sport_client:
                return
            
            self.get_logger().info("Setting robot to elderly-safe initial state")
            
            # Stand up with comfortable height
            self.sport_client.StandUp()
            time.sleep(2.0)
            
            # Set body height for elderly comfort (lower is less intimidating)
            self.sport_client.BodyHeight(self.default_body_height)
            time.sleep(1.0)
            
            # Enable balance mode for stability
            self.sport_client.BalanceStand()
            
            self.current_state = RobotState.STANDING
            self.get_logger().info("Robot ready for elderly companion mode")
            
        except Exception as e:
            self.get_logger().error(f"Initial robot state setting error: {e}")

    def cmd_vel_callback(self, msg: Twist):
        """Handle velocity commands with elderly safety constraints"""
        try:
            if not self.robot_ready or self.emergency_stop_active:
                return
            
            # Apply elderly-specific safety constraints
            safe_cmd = self.apply_elderly_safety_constraints(msg)
            
            # Update last command tracking
            self.last_cmd_vel = safe_cmd
            self.last_command_time = datetime.now()
            
            # Send to robot
            self.send_velocity_command(safe_cmd)
            
        except Exception as e:
            self.get_logger().error(f"Velocity command callback error: {e}")

    def apply_elderly_safety_constraints(self, cmd_vel: Twist) -> Twist:
        """Apply elderly-specific safety constraints to velocity commands"""
        try:
            safe_cmd = Twist()
            
            # Apply motion constraints
            safe_cmd.linear.x = max(-self.motion_constraints.max_linear_velocity,
                                  min(self.motion_constraints.max_linear_velocity,
                                      cmd_vel.linear.x))
            
            safe_cmd.linear.y = max(-self.motion_constraints.max_linear_velocity * 0.5,
                                  min(self.motion_constraints.max_linear_velocity * 0.5,
                                      cmd_vel.linear.y))
            
            safe_cmd.angular.z = max(-self.motion_constraints.max_angular_velocity,
                                   min(self.motion_constraints.max_angular_velocity,
                                       cmd_vel.angular.z))
            
            # Apply additional constraints from safety guard
            if hasattr(self.current_safety_constraints, 'max_linear_velocity'):
                max_vel = min(self.motion_constraints.max_linear_velocity,
                            self.current_safety_constraints.max_linear_velocity)
                safe_cmd.linear.x = max(-max_vel, min(max_vel, safe_cmd.linear.x))
            
            # Reduce speed in elderly mode for extra safety
            if self.elderly_mode:
                safety_factor = 0.7  # 70% of max speed in elderly mode
                safe_cmd.linear.x *= safety_factor
                safe_cmd.linear.y *= safety_factor
                safe_cmd.angular.z *= safety_factor
            
            return safe_cmd
            
        except Exception as e:
            self.get_logger().error(f"Safety constraints application error: {e}")
            return Twist()  # Return zero velocity on error

    def send_velocity_command(self, cmd_vel: Twist):
        """Send velocity command to Unitree Go2"""
        try:
            if not self.sport_client:
                return
            
            # Convert ROS2 Twist to Unitree velocity command
            vx = float(cmd_vel.linear.x)
            vy = float(cmd_vel.linear.y)
            vyaw = float(cmd_vel.angular.z)
            
            # Ensure robot is in walking mode if moving
            if abs(vx) > 0.01 or abs(vy) > 0.01 or abs(vyaw) > 0.01:
                if self.current_state != RobotState.WALKING:
                    self.current_state = RobotState.WALKING
            else:
                if self.current_state == RobotState.WALKING:
                    self.current_state = RobotState.STANDING
            
            # Send move command with elderly-appropriate gait
            self.sport_client.Move(vx, vy, vyaw)
            
        except Exception as e:
            self.get_logger().error(f"Velocity command sending error: {e}")

    def safety_constraints_callback(self, msg: SafetyConstraints):
        """Update safety constraints from safety guard"""
        try:
            self.current_safety_constraints = msg
            
            # Update motion constraints based on safety guard input
            if msg.emergency_override_enabled and msg.emergency_permissions:
                # In emergency mode, allow slightly faster movement
                self.motion_constraints.max_linear_velocity = min(0.8, msg.max_linear_velocity)
            else:
                # Normal mode - apply safety guard constraints
                self.motion_constraints.max_linear_velocity = min(0.6, msg.max_linear_velocity)
            
            self.motion_constraints.max_angular_velocity = min(0.8, msg.max_angular_velocity)
            
            self.get_logger().debug("Safety constraints updated from safety guard")
            
        except Exception as e:
            self.get_logger().error(f"Safety constraints update error: {e}")

    def emergency_alert_callback(self, msg: EmergencyAlert):
        """Handle emergency alerts - implement emergency stop or response"""
        try:
            self.get_logger().critical(f"EMERGENCY ALERT: {msg.emergency_type}")
            
            if msg.emergency_type in ["fall", "medical"]:
                # For fall or medical emergencies, approach carefully
                self.set_emergency_approach_mode()
            else:
                # For other emergencies, emergency stop
                self.emergency_stop()
            
        except Exception as e:
            self.get_logger().error(f"Emergency alert handling error: {e}")

    def set_emergency_approach_mode(self):
        """Set robot to emergency approach mode for assisting elderly"""
        try:
            self.get_logger().critical("Setting emergency approach mode")
            
            # Lower body for less intimidating approach
            if self.sport_client:
                self.sport_client.BodyHeight(0.15)  # Lower height
            
            # Set gentle movement constraints
            self.motion_constraints.max_linear_velocity = 0.3  # Slower approach
            self.motion_constraints.max_acceleration = 0.2     # Gentler acceleration
            
            self.current_gait = GaitType.EMERGENCY_APPROACH
            
        except Exception as e:
            self.get_logger().error(f"Emergency approach mode error: {e}")

    def emergency_stop(self):
        """Emergency stop robot immediately"""
        try:
            self.get_logger().critical("EMERGENCY STOP ACTIVATED")
            
            self.emergency_stop_active = True
            self.current_state = RobotState.EMERGENCY_STOP
            
            # Stop all movement
            if self.sport_client:
                self.sport_client.StopMove()
                # Ensure robot is in stable standing position
                self.sport_client.BalanceStand()
            
            # Publish emergency stop status
            status_msg = String()
            status_msg.data = "EMERGENCY_STOP_ACTIVE"
            self.robot_status_pub.publish(status_msg)
            
        except Exception as e:
            self.get_logger().error(f"Emergency stop error: {e}")

    def start_monitoring_loops(self):
        """Start robot monitoring and publishing loops"""
        try:
            # Create timers for monitoring
            self.state_pub_timer = self.create_timer(
                1.0 / self.publish_frequency,  # Convert Hz to seconds
                self.publish_robot_state
            )
            
            self.health_check_timer = self.create_timer(
                self.get_parameter('monitoring.health_check_interval').value,
                self.health_check_loop
            )
            
            self.command_timeout_timer = self.create_timer(
                0.1,  # 10Hz
                self.check_command_timeout
            )
            
        except Exception as e:
            self.get_logger().error(f"Monitoring loops start error: {e}")

    def publish_robot_state(self):
        """Publish robot state information to ROS2"""
        try:
            if not self.robot_ready:
                return
            
            current_time = self.get_clock().now()
            
            # Publish odometry
            self.publish_odometry(current_time)
            
            # Publish joint states
            self.publish_joint_states(current_time)
            
            # Publish IMU data
            self.publish_imu_data(current_time)
            
            # Publish robot status
            status_msg = String()
            status_msg.data = f"{self.current_state.value}:{self.current_gait.value}"
            self.robot_status_pub.publish(status_msg)
            
        except Exception as e:
            self.get_logger().error(f"Robot state publishing error: {e}")

    def publish_odometry(self, timestamp):
        """Publish robot odometry"""
        try:
            odom_msg = Odometry()
            odom_msg.header.stamp = timestamp.to_msg()
            odom_msg.header.frame_id = "odom"
            odom_msg.child_frame_id = "base_link"
            
            if UNITREE_SDK_AVAILABLE and self.sport_client:
                # Get actual robot state from Unitree SDK
                # This would be populated with real odometry data
                pass
            
            # For now, publish basic odometry
            odom_msg.pose.pose.position.x = 0.0
            odom_msg.pose.pose.position.y = 0.0
            odom_msg.pose.pose.position.z = self.default_body_height
            
            odom_msg.pose.pose.orientation.w = 1.0
            
            # Velocity from last command
            odom_msg.twist.twist = self.last_cmd_vel
            
            self.odom_pub.publish(odom_msg)
            
        except Exception as e:
            self.get_logger().error(f"Odometry publishing error: {e}")

    def publish_joint_states(self, timestamp):
        """Publish robot joint states"""
        try:
            joint_msg = JointState()
            joint_msg.header.stamp = timestamp.to_msg()
            joint_msg.header.frame_id = "base_link"
            
            # Unitree Go2 joint names
            joint_names = [
                'FR_hip_joint', 'FR_thigh_joint', 'FR_calf_joint',
                'FL_hip_joint', 'FL_thigh_joint', 'FL_calf_joint',
                'RR_hip_joint', 'RR_thigh_joint', 'RR_calf_joint',
                'RL_hip_joint', 'RL_thigh_joint', 'RL_calf_joint'
            ]
            
            joint_msg.name = joint_names
            joint_msg.position = [0.0] * len(joint_names)  # Would be populated with real data
            joint_msg.velocity = [0.0] * len(joint_names)
            joint_msg.effort = [0.0] * len(joint_names)
            
            self.joint_states_pub.publish(joint_msg)
            
        except Exception as e:
            self.get_logger().error(f"Joint states publishing error: {e}")

    def publish_imu_data(self, timestamp):
        """Publish robot IMU data"""
        try:
            imu_msg = Imu()
            imu_msg.header.stamp = timestamp.to_msg()
            imu_msg.header.frame_id = "imu_link"
            
            # Would be populated with real IMU data from Unitree SDK
            imu_msg.orientation.w = 1.0
            
            self.imu_pub.publish(imu_msg)
            
        except Exception as e:
            self.get_logger().error(f"IMU data publishing error: {e}")

    def health_check_loop(self):
        """Monitor robot health and publish status"""
        try:
            health_msg = HealthStatus()
            health_msg.header.stamp = self.get_clock().now().to_msg()
            health_msg.header.frame_id = "robot_health"
            
            # System health checks
            health_msg.motion_system_ok = self.robot_ready and not self.emergency_stop_active
            health_msg.audio_system_ok = True  # Would check actual audio system
            health_msg.network_connected = self.robot_ready
            health_msg.camera_system_ok = True  # Would check camera system
            health_msg.ai_processing_ok = True
            
            # Battery level (would get from actual robot)
            health_msg.battery_level = 0.8  # Mock 80% battery
            
            # Emergency system status
            health_msg.emergency_system_ready = not self.emergency_stop_active
            health_msg.emergency_response_time_ms = 200.0  # Target 200ms response
            
            # Robot-specific health
            health_msg.fall_detection_active = True
            health_msg.voice_monitoring_active = True
            health_msg.family_connection_active = True
            
            self.health_status_pub.publish(health_msg)
            
        except Exception as e:
            self.get_logger().error(f"Health check error: {e}")

    def check_command_timeout(self):
        """Check for command timeout and stop robot if no recent commands"""
        try:
            current_time = datetime.now()
            time_since_last_cmd = (current_time - self.last_command_time).total_seconds()
            
            if (time_since_last_cmd > self.command_timeout and 
                self.current_state == RobotState.WALKING):
                
                # No recent commands, stop robot for safety
                self.send_velocity_command(Twist())
                self.current_state = RobotState.STANDING
                
        except Exception as e:
            self.get_logger().error(f"Command timeout check error: {e}")

    def __del__(self):
        """Cleanup when node is destroyed"""
        try:
            if hasattr(self, 'sport_client') and self.sport_client:
                # Ensure robot stops safely
                self.sport_client.StopMove()
                self.sport_client.Damp()
        except:
            pass


def main(args=None):
    """Main entry point"""
    rclpy.init(args=args)
    
    try:
        node = UnitreeGo2BridgeNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()