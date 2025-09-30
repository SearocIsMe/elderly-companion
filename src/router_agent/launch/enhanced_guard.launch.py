#!/usr/bin/env python3
"""
Enhanced Guard Launch Configuration.
Launches Enhanced Guard Engine with RKNPU optimization for RK3588.
"""

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    return LaunchDescription([
        # Launch arguments
        DeclareLaunchArgument(
            'log_level',
            default_value='info',
            description='Log level for Enhanced Guard'
        ),
        
        DeclareLaunchArgument(
            'enable_rknpu',
            default_value='true',
            description='Enable RKNPU acceleration'
        ),
        
        # Enhanced Guard Engine
        Node(
            package='router_agent',
            executable='enhanced_guard_engine.py',
            name='enhanced_guard_engine',
            output='screen',
            parameters=[{
                'log_level': LaunchConfiguration('log_level'),
                'enable_rknpu': LaunchConfiguration('enable_rknpu'),
                'elderly.speech_adaptation': True,
                'guard.wakeword_threshold': 0.75,
                'guard.sos_threshold': 0.6,
                'guard.geofence_monitoring': True,
                'guard.implicit_recognition': True,
                'performance.max_response_time_ms': 200,
                'privacy.local_processing_only': True
            }]
        ),
        
        # Guard Integration Node
        Node(
            package='router_agent',
            executable='guard_integration_node.py', 
            name='guard_integration',
            output='screen',
            parameters=[{
                'integration.dialog_manager_timeout': 5.0,
                'integration.safety_guard_timeout': 3.0,
                'integration.message_buffer_size': 100
            }]
        ),
        
        LogInfo(msg="Enhanced Guard system launched - Advanced safety monitoring active")
    ])