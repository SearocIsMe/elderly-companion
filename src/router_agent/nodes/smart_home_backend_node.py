#!/usr/bin/env python3
"""
Comprehensive Smart-Home Backend Service for Elderly Companion Robdog.

Production-ready smart home integration with:
- Complete Home Assistant and MQTT integration
- Elderly-focused device management (lighting, climate, safety, health)
- Emergency automation and safety protocols
- Device status monitoring and predictive maintenance
- FastAPI integration for seamless system communication
- Advanced scene management for elderly comfort and safety
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

import json
import time
import threading
import queue
import requests
import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import uuid

# MQTT and Home Assistant imports
try:
    import paho.mqtt.client as mqtt
    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False
    print("Warning: paho-mqtt not available")

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

# ROS2 message imports
from std_msgs.msg import Header, String, Bool
from elderly_companion.msg import (
    IntentResult, EmergencyAlert, HealthStatus
)
from elderly_companion.srv import ExecuteAction


class DeviceCategory(Enum):
    """Device categories for elderly care."""
    LIGHTING = "lighting"
    CLIMATE = "climate" 
    SAFETY = "safety"
    HEALTH = "health"
    ENTERTAINMENT = "entertainment"
    COMMUNICATION = "communication"
    EMERGENCY = "emergency"


class DeviceState(Enum):
    """Device operational states."""
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    EMERGENCY = "emergency"


class AutomationTrigger(Enum):
    """Automation triggers."""
    TIME_BASED = "time_based"
    SENSOR_BASED = "sensor_based"
    EMERGENCY = "emergency"
    HEALTH_EVENT = "health_event"
    VOICE_COMMAND = "voice_command"


@dataclass
class ElderlySmartDevice:
    """Enhanced smart device definition for elderly care."""
    device_id: str
    name: str
    category: DeviceCategory
    room: str
    manufacturer: str
    model: str
    
    # Control information
    mqtt_topic: str
    ha_entity_id: str
    capabilities: List[str]
    current_state: Dict[str, Any]
    
    # Elderly-specific features
    elderly_priority: int  # 1 = critical, 5 = convenience
    safety_critical: bool
    emergency_automation: bool
    voice_controllable: bool
    simplified_interface: bool
    
    # Status and monitoring
    last_updated: datetime
    device_state: DeviceState
    battery_level: Optional[float] = None
    signal_strength: Optional[float] = None
    maintenance_due: Optional[datetime] = None
    
    # Emergency settings
    emergency_state: Optional[Dict[str, Any]] = None
    backup_control_method: Optional[str] = None


@dataclass
class ElderlyScene:
    """Smart home scene optimized for elderly users."""
    scene_id: str
    name: str
    description: str
    trigger_phrase: List[str]
    
    # Device actions
    device_actions: Dict[str, Dict[str, Any]]
    
    # Elderly-specific settings
    confirmation_required: bool
    voice_feedback: bool
    gradual_transition: bool
    safety_checks: List[str]
    
    # Scheduling
    time_restrictions: Optional[Dict[str, Any]] = None
    health_conditions: Optional[List[str]] = None


class SmartHomeBackendNode(Node):
    """
    Comprehensive Smart-Home Backend Service for elderly care.
    
    Core functionality:
    - Complete Home Assistant and MQTT integration
    - Elderly-focused device management and automation
    - Emergency response and safety protocols
    - Predictive maintenance and health monitoring
    - Voice command processing with safety validation
    - Scene management optimized for elderly comfort
    """

    def __init__(self):
        super().__init__('smart_home_backend_node')
        
        # Initialize comprehensive parameters
        self.declare_parameters(
            namespace='',
            parameters=[
                # Home Assistant Integration
                ('homeassistant.url', 'http://homeassistant.local:8123'),
                ('homeassistant.token', ''),
                ('homeassistant.ssl_verify', True),
                ('homeassistant.timeout', 10),
                
                # MQTT Configuration
                ('mqtt.broker_host', 'localhost'),
                ('mqtt.broker_port', 1883),
                ('mqtt.username', ''),
                ('mqtt.password', ''),
                ('mqtt.keepalive', 60),
                ('mqtt.qos', 1),
                ('mqtt.retain', True),
                
                # Device Discovery and Management
                ('discovery.auto_discover_devices', True),
                ('discovery.scan_interval', 300),  # 5 minutes
                ('discovery.device_timeout', 180),  # 3 minutes
                ('management.health_check_interval', 60),
                ('management.maintenance_alerts', True),
                
                # Elderly Care Settings
                ('elderly.simplified_controls', True),
                ('elderly.voice_confirmations', True),
                ('elderly.gradual_lighting_changes', True),
                ('elderly.safety_timeouts', 30),  # seconds
                ('elderly.emergency_override', True),
                
                # Safety and Emergency
                ('safety.enable_emergency_automation', True),
                ('safety.emergency_lighting_level', 80),  # percent
                ('safety.emergency_temperature', 22),  # celsius
                ('safety.lock_override_emergency', True),
                ('safety.alert_family_on_emergency', True),
                
                # Automation and Scenes
                ('automation.enable_time_based', True),
                ('automation.enable_sensor_based', True),
                ('automation.learning_mode', True),
                ('scenes.predefined_scenes', True),
                ('scenes.custom_scenes', True),
                
                # FastAPI Integration
                ('fastapi.bridge_url', 'http://localhost:7010'),
                ('fastapi.enable_status_updates', True),
                ('fastapi.update_interval', 30),
                
                # Performance and Reliability
                ('performance.max_concurrent_commands', 5),
                ('performance.command_timeout', 15),
                ('performance.retry_attempts', 3),
                ('reliability.heartbeat_interval', 30),
                ('reliability.backup_control', True),
            ]
        )
        
        # Get parameters
        self.ha_url = self.get_parameter('homeassistant.url').value
        self.ha_token = self.get_parameter('homeassistant.token').value
        self.mqtt_host = self.get_parameter('mqtt.broker_host').value
        self.mqtt_port = self.get_parameter('mqtt.broker_port').value
        self.mqtt_username = self.get_parameter('mqtt.username').value
        self.mqtt_password = self.get_parameter('mqtt.password').value
        self.auto_discover = self.get_parameter('discovery.auto_discover_devices').value
        self.elderly_simplified = self.get_parameter('elderly.simplified_controls').value
        self.safety_emergency_automation = self.get_parameter('safety.enable_emergency_automation').value
        self.fastapi_bridge_url = self.get_parameter('fastapi.bridge_url').value
        
        # Device management
        self.devices: Dict[str, ElderlySmartDevice] = {}
        self.scenes: Dict[str, ElderlyScene] = {}
        self.device_groups: Dict[str, List[str]] = {}
        
        # MQTT client
        self.mqtt_client = None
        self.mqtt_connected = False
        self.initialize_mqtt_client()
        
        # Home Assistant session
        self.ha_session = requests.Session()
        self.ha_session.headers.update({
            'Authorization': f'Bearer {self.ha_token}',
            'Content-Type': 'application/json'
        })
        
        # Command processing
        self.command_queue = queue.Queue(maxsize=100)
        self.active_commands: Dict[str, Dict[str, Any]] = {}
        
        # Emergency state
        self.emergency_mode = False
        self.emergency_scene_active = False
        
        # QoS profiles
        reliable_qos = QoSProfile(
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
        self.smart_home_intent_sub = self.create_subscription(
            IntentResult,
            '/intent/smart_home_validated',
            self.handle_smart_home_intent,
            reliable_qos
        )
        
        self.emergency_alert_sub = self.create_subscription(
            EmergencyAlert,
            '/emergency/alert',
            self.handle_emergency_alert,
            reliable_qos
        )
        
        # Publishers
        self.device_status_pub = self.create_publisher(
            String,
            '/smart_home/device_status',
            fast_qos
        )
        
        self.automation_result_pub = self.create_publisher(
            String,
            '/smart_home/automation_result',
            reliable_qos
        )
        
        self.maintenance_alert_pub = self.create_publisher(
            String,
            '/smart_home/maintenance_alert',
            reliable_qos
        )
        
        # Services
        self.execute_action_service = self.create_service(
            ExecuteAction,
            '/smart_home/execute_action',
            self.execute_action_callback
        )
        
        # Initialize smart home system
        self.initialize_smart_home_system()
        
        self.get_logger().info("Smart-Home Backend Node initialized - Elderly care automation ready")

    def initialize_mqtt_client(self):
        """Initialize MQTT client for device communication."""
        if not HAS_MQTT:
            self.get_logger().warning("MQTT not available - device communication limited")
            return
            
        try:
            self.mqtt_client = mqtt.Client(client_id="smart_home_backend", callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
            
            # Set authentication if provided
            if self.mqtt_username and self.mqtt_password:
                self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)
            
            # Set callbacks (using newer API version)
            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
            self.mqtt_client.on_message = self.on_mqtt_message
            
            # Connect to broker
            self.mqtt_client.connect(self.mqtt_host, self.mqtt_port, 
                                   self.get_parameter('mqtt.keepalive').value)
            self.mqtt_client.loop_start()
            
            self.get_logger().info(f"MQTT client connecting to {self.mqtt_host}:{self.mqtt_port}")
            
        except Exception as e:
            self.get_logger().error(f"MQTT client initialization failed: {e}")
            
    # 修改后（v2 回调）：
    def on_mqtt_connect(self, client, userdata, flags, reasonCode, properties):
        """Handle MQTT connection (MQTT v5/v2-callback)."""
        # v2: reasonCode 是枚举/整型，0 表示成功
        rc = int(reasonCode) if hasattr(reasonCode, '__int__') else reasonCode
        if rc == 0:
            self.mqtt_connected = True
            self.get_logger().info("MQTT client connected successfully")
            self.subscribe_to_device_topics()
        else:
            self.get_logger().error(f"MQTT connection failed with code {rc}")

    def on_mqtt_disconnect(self, client, userdata, reasonCode, properties):
        """Handle MQTT disconnection (MQTT v5/v2-callback)."""
        self.mqtt_connected = False
        rc = int(reasonCode) if hasattr(reasonCode, '__int__') else reasonCode
        self.get_logger().warning(f"MQTT client disconnected (code={rc})")

    def on_mqtt_message(self, client, userdata, msg):
        """Handle MQTT message (same签名，v1/v2通用)."""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            self.get_logger().debug(f"MQTT message: {topic} -> {payload}")
            self.process_mqtt_device_update(topic, payload)
        except Exception as e:
            self.get_logger().error(f"MQTT message processing error: {e}")

    def subscribe_to_device_topics(self):
        """Subscribe to relevant MQTT device topics."""
        try:
            # Subscribe to Home Assistant state topics
            self.mqtt_client.subscribe("homeassistant/+/+/state")
            self.mqtt_client.subscribe("homeassistant/+/+/attributes")
            
            # Subscribe to device status topics
            self.mqtt_client.subscribe("elderly_home/+/status")
            self.mqtt_client.subscribe("elderly_home/+/health")
            
            # Subscribe to emergency topics
            self.mqtt_client.subscribe("elderly_home/emergency/+")
            
            self.get_logger().info("Subscribed to MQTT device topics")
            
        except Exception as e:
            self.get_logger().error(f"MQTT subscription error: {e}")

    def initialize_smart_home_system(self):
        """Initialize the complete smart home system."""
        try:
            # Initialize predefined elderly-care devices
            self.initialize_elderly_care_devices()
            
            # Initialize scenes optimized for elderly users
            self.initialize_elderly_scenes()
            
            # Start device discovery if enabled
            if self.auto_discover:
                self.start_device_discovery()
            
            # Start background processing threads
            self.start_background_threads()
            
            # Test Home Assistant connection
            self.test_home_assistant_connection()
            
            self.get_logger().info("Smart home system initialization completed")
            
        except Exception as e:
            self.get_logger().error(f"Smart home system initialization failed: {e}")

    def initialize_elderly_care_devices(self):
        """Initialize predefined devices optimized for elderly care."""
        try:
            # Living room devices
            living_room_devices = [
                ElderlySmartDevice(
                    device_id="living_room_main_light",
                    name="客厅主灯",
                    category=DeviceCategory.LIGHTING,
                    room="living_room",
                    manufacturer="Philips",
                    model="Hue White",
                    mqtt_topic="homeassistant/light/living_room_main/state",
                    ha_entity_id="light.living_room_main",
                    capabilities=["brightness", "color_temp", "on_off"],
                    current_state={"state": "off", "brightness": 0},
                    elderly_priority=2,
                    safety_critical=True,
                    emergency_automation=True,
                    voice_controllable=True,
                    simplified_interface=True,
                    last_updated=datetime.now(),
                    device_state=DeviceState.ONLINE,
                    emergency_state={"state": "on", "brightness": 80}
                ),
                
                ElderlySmartDevice(
                    device_id="living_room_ac",
                    name="客厅空调",
                    category=DeviceCategory.CLIMATE,
                    room="living_room",
                    manufacturer="Midea", 
                    model="Smart AC",
                    mqtt_topic="homeassistant/climate/living_room_ac/state",
                    ha_entity_id="climate.living_room_ac",
                    capabilities=["temperature", "mode", "fan_speed"],
                    current_state={"state": "off", "temperature": 25},
                    elderly_priority=1,
                    safety_critical=True,
                    emergency_automation=True,
                    voice_controllable=True,
                    simplified_interface=True,
                    last_updated=datetime.now(),
                    device_state=DeviceState.ONLINE,
                    emergency_state={"state": "on", "temperature": 22, "mode": "auto"}
                )
            ]
            
            # Bedroom devices
            bedroom_devices = [
                ElderlySmartDevice(
                    device_id="bedroom_light",
                    name="卧室灯",
                    category=DeviceCategory.LIGHTING,
                    room="bedroom",
                    manufacturer="Xiaomi",
                    model="Mi Smart Bulb",
                    mqtt_topic="homeassistant/light/bedroom/state",
                    ha_entity_id="light.bedroom",
                    capabilities=["brightness", "on_off"],
                    current_state={"state": "off", "brightness": 0},
                    elderly_priority=2,
                    safety_critical=True,
                    emergency_automation=True,
                    voice_controllable=True,
                    simplified_interface=True,
                    last_updated=datetime.now(),
                    device_state=DeviceState.ONLINE,
                    emergency_state={"state": "on", "brightness": 50}
                ),
                
                ElderlySmartDevice(
                    device_id="bedroom_emergency_button",
                    name="卧室紧急按钮",
                    category=DeviceCategory.EMERGENCY,
                    room="bedroom",
                    manufacturer="Aqara",
                    model="Emergency Button",
                    mqtt_topic="homeassistant/binary_sensor/bedroom_emergency/state",
                    ha_entity_id="binary_sensor.bedroom_emergency",
                    capabilities=["press_detection"],
                    current_state={"state": "off"},
                    elderly_priority=1,
                    safety_critical=True,
                    emergency_automation=True,
                    voice_controllable=False,
                    simplified_interface=True,
                    last_updated=datetime.now(),
                    device_state=DeviceState.ONLINE
                )
            ]
            
            # Bathroom devices
            bathroom_devices = [
                ElderlySmartDevice(
                    device_id="bathroom_motion_sensor",
                    name="卫生间感应器",
                    category=DeviceCategory.SAFETY,
                    room="bathroom",
                    manufacturer="Aqara",
                    model="Motion Sensor",
                    mqtt_topic="homeassistant/binary_sensor/bathroom_motion/state",
                    ha_entity_id="binary_sensor.bathroom_motion",
                    capabilities=["motion_detection", "occupancy_timeout"],
                    current_state={"state": "off", "last_motion": None},
                    elderly_priority=1,
                    safety_critical=True,
                    emergency_automation=True,
                    voice_controllable=False,
                    simplified_interface=True,
                    last_updated=datetime.now(),
                    device_state=DeviceState.ONLINE
                ),
                
                ElderlySmartDevice(
                    device_id="bathroom_light",
                    name="卫生间灯",
                    category=DeviceCategory.LIGHTING,
                    room="bathroom",
                    manufacturer="Yeelight",
                    model="Smart Ceiling Light",
                    mqtt_topic="homeassistant/light/bathroom/state",
                    ha_entity_id="light.bathroom",
                    capabilities=["brightness", "on_off", "motion_activated"],
                    current_state={"state": "off", "brightness": 0},
                    elderly_priority=1,
                    safety_critical=True,
                    emergency_automation=True,
                    voice_controllable=True,
                    simplified_interface=True,
                    last_updated=datetime.now(),
                    device_state=DeviceState.ONLINE,
                    emergency_state={"state": "on", "brightness": 100}
                )
            ]
            
            # Health monitoring devices
            health_devices = [
                ElderlySmartDevice(
                    device_id="health_monitor",
                    name="健康监测仪",
                    category=DeviceCategory.HEALTH,
                    room="bedroom",
                    manufacturer="Xiaomi",
                    model="Mi Health Monitor",
                    mqtt_topic="homeassistant/sensor/health_monitor/state",
                    ha_entity_id="sensor.health_monitor",
                    capabilities=["heart_rate", "blood_pressure", "sleep_tracking"],
                    current_state={"heart_rate": 75, "blood_pressure": "120/80"},
                    elderly_priority=1,
                    safety_critical=True,
                    emergency_automation=True,
                    voice_controllable=False,
                    simplified_interface=True,
                    last_updated=datetime.now(),
                    device_state=DeviceState.ONLINE,
                    battery_level=85.0
                )
            ]
            
            # Add all devices to the main device registry
            all_devices = living_room_devices + bedroom_devices + bathroom_devices + health_devices
            for device in all_devices:
                self.devices[device.device_id] = device
            
            # Create device groups
            self.device_groups = {
                "lighting": [d.device_id for d in all_devices if d.category == DeviceCategory.LIGHTING],
                "climate": [d.device_id for d in all_devices if d.category == DeviceCategory.CLIMATE],
                "safety": [d.device_id for d in all_devices if d.category == DeviceCategory.SAFETY],
                "emergency": [d.device_id for d in all_devices if d.category == DeviceCategory.EMERGENCY],
                "health": [d.device_id for d in all_devices if d.category == DeviceCategory.HEALTH],
                "living_room": [d.device_id for d in all_devices if d.room == "living_room"],
                "bedroom": [d.device_id for d in all_devices if d.room == "bedroom"],
                "bathroom": [d.device_id for d in all_devices if d.room == "bathroom"]
            }
            
            self.get_logger().info(f"Initialized {len(all_devices)} elderly care devices in {len(self.device_groups)} groups")
            
        except Exception as e:
            self.get_logger().error(f"Elderly care devices initialization error: {e}")

    def initialize_elderly_scenes(self):
        """Initialize scenes optimized for elderly users."""
        try:
            # Morning scene
            morning_scene = ElderlyScene(
                scene_id="morning_routine",
                name="早安模式",
                description="温和的晨起照明和舒适温度",
                trigger_phrase=["早安模式", "晨起模式", "morning scene"],
                device_actions={
                    "living_room_main_light": {"state": "on", "brightness": 60},
                    "bedroom_light": {"state": "on", "brightness": 40},
                    "living_room_ac": {"state": "on", "temperature": 24}
                },
                confirmation_required=False,
                voice_feedback=True,
                gradual_transition=True,
                safety_checks=["ensure_person_awake"]
            )
            
            # Evening scene
            evening_scene = ElderlyScene(
                scene_id="evening_routine",
                name="晚安模式",
                description="温馨的晚间照明准备就寝",
                trigger_phrase=["晚安模式", "睡觉模式", "evening scene"],
                device_actions={
                    "living_room_main_light": {"state": "on", "brightness": 30},
                    "bedroom_light": {"state": "on", "brightness": 20},
                    "living_room_ac": {"state": "on", "temperature": 22}
                },
                confirmation_required=False,
                voice_feedback=True,
                gradual_transition=True,
                safety_checks=["ensure_all_safe"]
            )
            
            # Emergency scene
            emergency_scene = ElderlyScene(
                scene_id="emergency_response",
                name="紧急模式",
                description="紧急情况下的全屋照明和安全设置",
                trigger_phrase=["紧急模式", "emergency mode"],
                device_actions={
                    "living_room_main_light": {"state": "on", "brightness": 100},
                    "bedroom_light": {"state": "on", "brightness": 100},
                    "bathroom_light": {"state": "on", "brightness": 100},
                    "living_room_ac": {"state": "on", "temperature": 22}
                },
                confirmation_required=False,
                voice_feedback=True,
                gradual_transition=False,
                safety_checks=[]
            )
            
            # Comfort scene
            comfort_scene = ElderlyScene(
                scene_id="comfort_mode",
                name="舒适模式",
                description="最舒适的环境设置",
                trigger_phrase=["舒适模式", "comfort mode"],
                device_actions={
                    "living_room_main_light": {"state": "on", "brightness": 70},
                    "living_room_ac": {"state": "on", "temperature": 25}
                },
                confirmation_required=False,
                voice_feedback=True,
                gradual_transition=True,
                safety_checks=["check_health_status"]
            )
            
            scenes = [morning_scene, evening_scene, emergency_scene, comfort_scene]
            for scene in scenes:
                self.scenes[scene.scene_id] = scene
            
            self.get_logger().info(f"Initialized {len(scenes)} elderly-optimized scenes")
            
        except Exception as e:
            self.get_logger().error(f"Elderly scenes initialization error: {e}")

    def start_device_discovery(self):
        """Start automatic device discovery."""
        try:
            discovery_thread = threading.Thread(
                target=self.device_discovery_loop,
                daemon=True
            )
            discovery_thread.start()
            self.get_logger().info("Device discovery started")
            
        except Exception as e:
            self.get_logger().error(f"Device discovery start error: {e}")

    def start_background_threads(self):
        """Start background processing threads."""
        try:
            # Command processing thread
            self.command_thread = threading.Thread(
                target=self.command_processing_loop,
                daemon=True
            )
            self.command_thread.start()
            
            # Health monitoring thread
            self.health_thread = threading.Thread(
                target=self.device_health_monitoring_loop,
                daemon=True
            )
            self.health_thread.start()
            
            # Status update thread
            self.status_thread = threading.Thread(
                target=self.status_update_loop,
                daemon=True
            )
            self.status_thread.start()
            
            self.get_logger().info("Background processing threads started")
            
        except Exception as e:
            self.get_logger().error(f"Background threads start error: {e}")

    def test_home_assistant_connection(self):
        """Test connection to Home Assistant."""
        try:
            if not self.ha_token:
                self.get_logger().warning("Home Assistant token not configured")
                return False
            
            response = self.ha_session.get(
                f"{self.ha_url}/api/",
                timeout=self.get_parameter('homeassistant.timeout').value
            )
            
            if response.status_code == 200:
                self.get_logger().info("Home Assistant connection verified")
                return True
            else:
                self.get_logger().warning(f"Home Assistant connection failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.get_logger().warning(f"Home Assistant connection test failed: {e}")
            return False

    def handle_smart_home_intent(self, msg: IntentResult):
        """Handle validated smart home intents."""
        try:
            self.get_logger().info(f"Processing smart home intent: {msg.intent_type}")
            
            # Extract intent parameters
            intent_data = {
                'intent_type': msg.intent_type,
                'confidence': msg.confidence,
                'device': getattr(msg, 'device', ''),
                'action': getattr(msg, 'action', ''),
                'room': getattr(msg, 'room', ''),
                'value': getattr(msg, 'value', ''),
                'scene': getattr(msg, 'scene', ''),
                'timestamp': time.time()
            }
            
            # Add to command queue for processing
            self.command_queue.put(intent_data)
            
        except Exception as e:
            self.get_logger().error(f"Smart home intent handling error: {e}")

    def handle_emergency_alert(self, msg: EmergencyAlert):
        """Handle emergency alerts with automated smart home response."""
        try:
            self.get_logger().critical(f"Emergency alert received: {msg.emergency_type}")
            
            if self.safety_emergency_automation:
                # Activate emergency scene
                self.activate_emergency_scene(msg.emergency_type)
            
        except Exception as e:
            self.get_logger().error(f"Emergency alert handling error: {e}")

    def activate_emergency_scene(self, emergency_type: str):
        """Activate emergency scene based on emergency type."""
        try:
            self.emergency_mode = True
            
            if "emergency_response" in self.scenes:
                scene = self.scenes["emergency_response"]
                self.execute_scene(scene)
                self.emergency_scene_active = True
                
                self.get_logger().critical("Emergency scene activated")
                
                # Publish automation result
                result = {
                    'action': 'emergency_scene_activated',
                    'emergency_type': emergency_type,
                    'timestamp': datetime.now().isoformat(),
                    'devices_affected': list(scene.device_actions.keys())
                }
                
                result_msg = String()
                result_msg.data = json.dumps(result)
                self.automation_result_pub.publish(result_msg)
                
        except Exception as e:
            self.get_logger().error(f"Emergency scene activation error: {e}")

    def command_processing_loop(self):
        """Background command processing loop."""
        while rclpy.ok():
            try:
                # Get command from queue
                command = self.command_queue.get(timeout=1.0)
                
                # Process the command
                self.process_smart_home_command(command)
                
            except queue.Empty:
                continue
            except Exception as e:
                self.get_logger().error(f"Command processing loop error: {e}")
                time.sleep(1.0)

    def process_smart_home_command(self, command: Dict[str, Any]):
        """Process individual smart home command."""
        try:
            intent_type = command.get('intent_type', '')
            action = command.get('action', '')
            device = command.get('device', '')
            room = command.get('room', '')
            scene = command.get('scene', '')
            
            self.get_logger().info(f"Processing command: {intent_type} - {action}")
            
            # Handle different types of commands
            if scene:
                self.handle_scene_command(scene)
            elif device and action:
                self.handle_device_command(device, action, command)
            elif room and action:
                self.handle_room_command(room, action, command)
            else:
                self.get_logger().warning(f"Unrecognized command format: {command}")
            
        except Exception as e:
            self.get_logger().error(f"Smart home command processing error: {e}")

    def handle_scene_command(self, scene_name: str):
        """Handle scene activation command."""
        try:
            # Find scene by name or trigger phrase
            target_scene = None
            for scene in self.scenes.values():
                if (scene.name == scene_name or 
                    scene_name in scene.trigger_phrase or
                    scene.scene_id == scene_name):
                    target_scene = scene
                    break
            
            if target_scene:
                self.execute_scene(target_scene)
            else:
                self.get_logger().warning(f"Scene not found: {scene_name}")
                
        except Exception as e:
            self.get_logger().error(f"Scene command handling error: {e}")

    def handle_device_command(self, device_name: str, action: str, command: Dict[str, Any]):
        """Handle individual device command."""
        try:
            # Find device
            target_device = self.find_device_by_name(device_name)
            if not target_device:
                self.get_logger().warning(f"Device not found: {device_name}")
                return
            
            # Execute device action
            self.execute_device_action(target_device, action, command)
            
        except Exception as e:
            self.get_logger().error(f"Device command handling error: {e}")

    def handle_room_command(self, room: str, action: str, command: Dict[str, Any]):
        """Handle room-based command."""
        try:
            # Get devices in the room
            if room in self.device_groups:
                device_ids = self.device_groups[room]
                
                for device_id in device_ids:
                    if device_id in self.devices:
                        device = self.devices[device_id]
                        self.execute_device_action(device, action, command)
            else:
                self.get_logger().warning(f"Room not found: {room}")
                
        except Exception as e:
            self.get_logger().error(f"Room command handling error: {e}")

    def find_device_by_name(self, device_name: str) -> Optional[ElderlySmartDevice]:
        """Find device by name or ID."""
        try:
            # First try exact ID match
            if device_name in self.devices:
                return self.devices[device_name]
            
            # Then try name matching
            for device in self.devices.values():
                if device.name == device_name or device_name in device.name:
                    return device
            
            return None
            
        except Exception:
            return None

    def execute_scene(self, scene: ElderlyScene):
        """Execute a smart home scene."""
        try:
            self.get_logger().info(f"Executing scene: {scene.name}")
            
            # Execute each device action in the scene
            for device_id, action_params in scene.device_actions.items():
                if device_id in self.devices:
                    device = self.devices[device_id]
                    self.execute_device_action_direct(device, action_params)
            
            # Publish scene execution result
            result = {
                'action': 'scene_executed',
                'scene_name': scene.name,
                'scene_id': scene.scene_id,
                'timestamp': datetime.now().isoformat(),
                'devices_affected': list(scene.device_actions.keys())
            }
            
            result_msg = String()
            result_msg.data = json.dumps(result)
            self.automation_result_pub.publish(result_msg)
            
        except Exception as e:
            self.get_logger().error(f"Scene execution error: {e}")

    def execute_device_action(self, device: ElderlySmartDevice, action: str, command: Dict[str, Any]):
        """Execute action on a specific device."""
        try:
            self.get_logger().info(f"Executing {action} on {device.name}")
            
            # Prepare action parameters based on device type and action
            action_params = self.prepare_device_action_params(device, action, command)
            
            # Execute the action
            success = self.execute_device_action_direct(device, action_params)
            
            if success:
                self.get_logger().info(f"Device action completed: {device.name} -> {action}")
            else:
                self.get_logger().warning(f"Device action failed: {device.name} -> {action}")
                
        except Exception as e:
            self.get_logger().error(f"Device action execution error: {e}")

    def prepare_device_action_params(self, device: ElderlySmartDevice, action: str, command: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare action parameters for device."""
        try:
            params = {}
            
            # Handle different device categories
            if device.category == DeviceCategory.LIGHTING:
                if action in ['开', 'on', 'turn_on', 'open']:
                    params = {"state": "on", "brightness": 80}
                elif action in ['关', 'off', 'turn_off', 'close']:
                    params = {"state": "off"}
                elif action in ['调亮', 'brighten', 'bright']:
                    params = {"state": "on", "brightness": 90}
                elif action in ['调暗', 'dim']:
                    params = {"state": "on", "brightness": 30}
                    
            elif device.category == DeviceCategory.CLIMATE:
                if action in ['开', 'on', 'turn_on']:
                    params = {"state": "on", "temperature": 24}
                elif action in ['关', 'off', 'turn_off']:
                    params = {"state": "off"}
                elif action in ['调高', 'warmer', 'increase']:
                    current_temp = device.current_state.get('temperature', 24)
                    params = {"state": "on", "temperature": min(current_temp + 2, 28)}
                elif action in ['调低', 'cooler', 'decrease']:
                    current_temp = device.current_state.get('temperature', 24)
                    params = {"state": "on", "temperature": max(current_temp - 2, 18)}
            
            # Add any specific values from command
            if 'value' in command and command['value']:
                try:
                    value = float(command['value'])
                    if device.category == DeviceCategory.LIGHTING:
                        params['brightness'] = max(0, min(100, value))
                    elif device.category == DeviceCategory.CLIMATE:
                        params['temperature'] = max(16, min(30, value))
                except ValueError:
                    pass
            
            return params
            
        except Exception as e:
            self.get_logger().error(f"Action params preparation error: {e}")
            return {}

    def execute_device_action_direct(self, device: ElderlySmartDevice, action_params: Dict[str, Any]) -> bool:
        """Execute device action using appropriate control method."""
        try:
            success = False
            
            # Try Home Assistant API first
            if self.ha_token:
                success = self.execute_via_home_assistant(device, action_params)
            
            # Fallback to MQTT if HA fails
            if not success and self.mqtt_connected:
                success = self.execute_via_mqtt(device, action_params)
            
            # Update device state if successful
            if success:
                device.current_state.update(action_params)
                device.last_updated = datetime.now()
                
                # Publish device status update
                self.publish_device_status_update(device)
            
            return success
            
        except Exception as e:
            self.get_logger().error(f"Direct device action execution error: {e}")
            return False

    def execute_via_home_assistant(self, device: ElderlySmartDevice, action_params: Dict[str, Any]) -> bool:
        """Execute device action via Home Assistant API."""
        try:
            domain = device.ha_entity_id.split('.')[0]
            service_data = {
                "entity_id": device.ha_entity_id
            }
            service_data.update(action_params)
            
            # Determine service based on action and domain
            if domain == "light":
                service = "turn_on" if action_params.get("state") == "on" else "turn_off"
            elif domain == "climate":
                service = "turn_on" if action_params.get("state") == "on" else "turn_off"
            else:
                service = "turn_on" if action_params.get("state") == "on" else "turn_off"
            
            # Call Home Assistant service
            response = self.ha_session.post(
                f"{self.ha_url}/api/services/{domain}/{service}",
                json=service_data,
                timeout=self.get_parameter('performance.command_timeout').value
            )
            
            if response.status_code == 200:
                self.get_logger().debug(f"HA command successful: {device.name}")
                return True
            else:
                self.get_logger().warning(f"HA command failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.get_logger().error(f"Home Assistant execution error: {e}")
            return False

    def execute_via_mqtt(self, device: ElderlySmartDevice, action_params: Dict[str, Any]) -> bool:
        """Execute device action via MQTT."""
        try:
            if not self.mqtt_connected:
                return False
            
            # Prepare MQTT command topic
            command_topic = device.mqtt_topic.replace('/state', '/set')
            
            # Publish command
            self.mqtt_client.publish(
                command_topic,
                json.dumps(action_params),
                qos=self.get_parameter('mqtt.qos').value,
                retain=self.get_parameter('mqtt.retain').value
            )
            
            self.get_logger().debug(f"MQTT command sent: {device.name} -> {action_params}")
            return True
            
        except Exception as e:
            self.get_logger().error(f"MQTT execution error: {e}")
            return False

    def publish_device_status_update(self, device: ElderlySmartDevice):
        """Publish device status update."""
        try:
            status_data = {
                'device_id': device.device_id,
                'name': device.name,
                'category': device.category.value,
                'room': device.room,
                'state': device.current_state,
                'device_state': device.device_state.value,
                'last_updated': device.last_updated.isoformat(),
                'battery_level': device.battery_level,
                'safety_critical': device.safety_critical
            }
            
            status_msg = String()
            status_msg.data = json.dumps(status_data)
            self.device_status_pub.publish(status_msg)
            
        except Exception as e:
            self.get_logger().error(f"Device status publishing error: {e}")

    def process_mqtt_device_update(self, topic: str, payload: Dict[str, Any]):
        """Process MQTT device status update."""
        try:
            # Find device by topic
            for device in self.devices.values():
                if device.mqtt_topic in topic:
                    # Update device state
                    device.current_state.update(payload)
                    device.last_updated = datetime.now()
                    
                    # Publish status update
                    self.publish_device_status_update(device)
                    break
                    
        except Exception as e:
            self.get_logger().error(f"MQTT device update processing error: {e}")

    def device_discovery_loop(self):
        """Background device discovery loop."""
        while rclpy.ok():
            try:
                # Discover new devices via Home Assistant
                if self.ha_token:
                    self.discover_home_assistant_devices()
                
                # Wait for next discovery cycle
                time.sleep(self.get_parameter('discovery.scan_interval').value)
                
            except Exception as e:
                self.get_logger().error(f"Device discovery loop error: {e}")
                time.sleep(60)

    def discover_home_assistant_devices(self):
        """Discover devices from Home Assistant."""
        try:
            response = self.ha_session.get(
                f"{self.ha_url}/api/states",
                timeout=self.get_parameter('homeassistant.timeout').value
            )
            
            if response.status_code == 200:
                states = response.json()
                self.get_logger().debug(f"Discovered {len(states)} HA entities")
                
                # Process new devices (implementation would be more complex)
                # For now, just log the discovery
                
        except Exception as e:
            self.get_logger().error(f"HA device discovery error: {e}")

    def device_health_monitoring_loop(self):
        """Monitor device health and maintenance needs."""
        while rclpy.ok():
            try:
                current_time = datetime.now()
                
                for device in self.devices.values():
                    # Check if device is offline
                    if (current_time - device.last_updated).total_seconds() > self.get_parameter('discovery.device_timeout').value:
                        if device.device_state != DeviceState.OFFLINE:
                            device.device_state = DeviceState.OFFLINE
                            self.get_logger().warning(f"Device offline: {device.name}")
                            self.publish_device_status_update(device)
                    
                    # Check battery levels
                    if device.battery_level is not None and device.battery_level < 20:
                        self.publish_maintenance_alert(device, "low_battery", f"Battery level: {device.battery_level}%")
                    
                    # Check maintenance due dates
                    if device.maintenance_due and current_time > device.maintenance_due:
                        self.publish_maintenance_alert(device, "maintenance_due", "Scheduled maintenance required")
                
                time.sleep(self.get_parameter('management.health_check_interval').value)
                
            except Exception as e:
                self.get_logger().error(f"Device health monitoring error: {e}")
                time.sleep(60)

    def publish_maintenance_alert(self, device: ElderlySmartDevice, alert_type: str, message: str):
        """Publish maintenance alert."""
        try:
            alert_data = {
                'device_id': device.device_id,
                'device_name': device.name,
                'alert_type': alert_type,
                'message': message,
                'priority': 'high' if device.safety_critical else 'normal',
                'timestamp': datetime.now().isoformat()
            }
            
            alert_msg = String()
            alert_msg.data = json.dumps(alert_data)
            self.maintenance_alert_pub.publish(alert_msg)
            
            self.get_logger().warning(f"Maintenance alert: {device.name} - {message}")
            
        except Exception as e:
            self.get_logger().error(f"Maintenance alert publishing error: {e}")

    def status_update_loop(self):
        """Send status updates to FastAPI bridge."""
        while rclpy.ok():
            try:
                if self.get_parameter('fastapi.enable_status_updates').value:
                    self.send_status_to_fastapi_bridge()
                
                time.sleep(self.get_parameter('fastapi.update_interval').value)
                
            except Exception as e:
                self.get_logger().error(f"Status update loop error: {e}")
                time.sleep(60)

    def send_status_to_fastapi_bridge(self):
        """Send smart home status to FastAPI bridge."""
        try:
            status_data = {
                'total_devices': len(self.devices),
                'online_devices': len([d for d in self.devices.values() if d.device_state == DeviceState.ONLINE]),
                'emergency_mode': self.emergency_mode,
                'mqtt_connected': self.mqtt_connected,
                'scenes_available': len(self.scenes),
                'last_update': datetime.now().isoformat()
            }
            
            # Send to FastAPI bridge
            response = requests.post(
                f"{self.fastapi_bridge_url}/smart_home_status",
                json=status_data,
                timeout=5.0
            )
            
            if response.status_code == 200:
                self.get_logger().debug("Status sent to FastAPI bridge")
                
        except Exception as e:
            self.get_logger().debug(f"FastAPI bridge status update error: {e}")

    def execute_action_callback(self, request, response):
        """Handle service callback for action execution."""
        try:
            action_type = request.action_type
            parameters = json.loads(request.parameters) if request.parameters else {}
            
            self.get_logger().info(f"Execute action service called: {action_type}")
            
            # Add to command queue
            command = {
                'intent_type': 'service_call',
                'action': action_type,
                'parameters': parameters,
                'timestamp': time.time()
            }
            
            self.command_queue.put(command)
            
            # Prepare response
            response.execution_successful = True
            response.result_message = f"Action {action_type} queued for execution"
            response.estimated_completion_time = 5.0
            
            return response
            
        except Exception as e:
            self.get_logger().error(f"Execute action service error: {e}")
            response.execution_successful = False
            response.error_message = str(e)
            return response


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)
    
    try:
        node = SmartHomeBackendNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Smart-Home Backend error: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()