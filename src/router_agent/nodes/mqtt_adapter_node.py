#!/usr/bin/env python3
"""
MQTT Adapter Node for Elderly Companion Robdog.

Handles smart home device integration via MQTT, Matter, and REST APIs.
Specialized for elderly-friendly device control and monitoring.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

import json
import time
import threading
import ssl
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio

# MQTT and networking imports
import paho.mqtt.client as mqtt
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ROS2 message imports
from std_msgs.msg import Header, String, Bool, Float32
from geometry_msgs.msg import Point
from elderly_companion.msg import IntentResult, HealthStatus, EmergencyAlert


class DeviceType(Enum):
    """Smart home device types."""
    LIGHT = "light"
    THERMOSTAT = "thermostat"
    SECURITY_CAMERA = "camera"
    DOOR_LOCK = "lock"
    MEDICAL_DEVICE = "medical"
    EMERGENCY_BUTTON = "emergency_button"
    AIR_PURIFIER = "air_purifier"
    CURTAINS = "curtains"
    TV = "television"
    SPEAKER = "speaker"


class DeviceProtocol(Enum):
    """Device communication protocols."""
    MQTT = "mqtt"
    MATTER = "matter"
    REST_API = "rest"
    ZIGBEE = "zigbee"
    ZWAVE = "zwave"


@dataclass
class SmartDevice:
    """Smart home device representation."""
    device_id: str
    name: str
    device_type: DeviceType
    protocol: DeviceProtocol
    mqtt_topic: Optional[str] = None
    rest_endpoint: Optional[str] = None
    current_state: Dict[str, Any] = None
    capabilities: List[str] = None
    elderly_friendly: bool = True
    location: str = ""
    last_updated: Optional[datetime] = None


@dataclass
class DeviceCommand:
    """Device command structure."""
    device_id: str
    action: str
    parameters: Dict[str, Any]
    timestamp: datetime
    user_intent: str
    safety_validated: bool = False


class MQTTAdapterNode(Node):
    """
    MQTT Adapter Node for smart home integration.
    
    Handles:
    - MQTT device communication for various smart home protocols
    - Device discovery and status monitoring
    - Elderly-friendly device control with safety validation
    - Integration with home assistants (Home Assistant, OpenHAB, etc.)
    - Emergency device coordination
    """

    def __init__(self):
        super().__init__('mqtt_adapter_node')
        
        # Initialize parameters
        self.declare_parameters(
            namespace='',
            parameters=[
                ('mqtt.broker_host', 'localhost'),
                ('mqtt.broker_port', 1883),
                ('mqtt.username', ''),
                ('mqtt.password', ''),
                ('mqtt.use_tls', False),
                ('mqtt.keepalive', 60),
                ('mqtt.client_id', 'elderly_companion_robot'),
                ('devices.discovery_enabled', True),
                ('devices.auto_refresh_interval', 300),  # 5 minutes
                ('devices.command_timeout', 10),
                ('elderly.simple_commands_only', True),
                ('elderly.confirmation_required', True),
                ('safety.emergency_device_override', True),
                ('integration.homeassistant.enabled', False),
                ('integration.homeassistant.url', ''),
                ('integration.homeassistant.token', ''),
            ]
        )
        
        # Get parameters
        self.broker_host = self.get_parameter('mqtt.broker_host').value
        self.broker_port = self.get_parameter('mqtt.broker_port').value
        self.username = self.get_parameter('mqtt.username').value
        self.password = self.get_parameter('mqtt.password').value
        self.use_tls = self.get_parameter('mqtt.use_tls').value
        self.discovery_enabled = self.get_parameter('devices.discovery_enabled').value
        self.simple_commands_only = self.get_parameter('elderly.simple_commands_only').value
        self.confirmation_required = self.get_parameter('elderly.confirmation_required').value
        self.ha_enabled = self.get_parameter('integration.homeassistant.enabled').value
        self.ha_url = self.get_parameter('integration.homeassistant.url').value
        self.ha_token = self.get_parameter('integration.homeassistant.token').value
        
        # Device management
        self.discovered_devices: Dict[str, SmartDevice] = {}
        self.device_commands_queue: List[DeviceCommand] = []
        self.command_history: List[DeviceCommand] = []
        
        # MQTT client
        self.mqtt_client = None
        self.mqtt_connected = False
        
        # HTTP session for REST APIs
        self.http_session = self.create_http_session()
        
        # Emergency device mappings
        self.emergency_devices = {
            'lights': ['all_lights', 'bedroom_light', 'living_room_light'],
            'security': ['door_locks', 'security_cameras'],
            'medical': ['emergency_button', 'medical_alert_system'],
            'communication': ['speakers', 'intercom']
        }
        
        # Elderly-friendly device mappings
        self.elderly_device_mappings = {
            # Simplified Chinese commands
            '开灯': {'action': 'turn_on', 'device_type': 'light'},
            '关灯': {'action': 'turn_off', 'device_type': 'light'},
            '开空调': {'action': 'turn_on', 'device_type': 'air_conditioner'},
            '关空调': {'action': 'turn_off', 'device_type': 'air_conditioner'},
            '开电视': {'action': 'turn_on', 'device_type': 'tv'},
            '关电视': {'action': 'turn_off', 'device_type': 'tv'},
            '拉窗帘': {'action': 'close', 'device_type': 'curtains'},
            '开窗帘': {'action': 'open', 'device_type': 'curtains'},
            
            # English commands
            'turn on lights': {'action': 'turn_on', 'device_type': 'light'},
            'turn off lights': {'action': 'turn_off', 'device_type': 'light'},
            'lights on': {'action': 'turn_on', 'device_type': 'light'},
            'lights off': {'action': 'turn_off', 'device_type': 'light'},
            'turn on tv': {'action': 'turn_on', 'device_type': 'tv'},
            'turn off tv': {'action': 'turn_off', 'device_type': 'tv'},
        }
        
        # QoS profiles
        default_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        # Subscribers
        self.smart_home_intent_sub = self.create_subscription(
            IntentResult,
            '/intent/validated',
            self.handle_smart_home_intent_callback,
            default_qos
        )
        
        self.emergency_alert_sub = self.create_subscription(
            EmergencyAlert,
            '/emergency/alert',
            self.handle_emergency_alert_callback,
            default_qos
        )
        
        # Publishers
        self.device_status_pub = self.create_publisher(
            String,
            '/smart_home/device_status',
            default_qos
        )
        
        self.command_result_pub = self.create_publisher(
            String,
            '/smart_home/command_result',
            default_qos
        )
        
        self.device_discovery_pub = self.create_publisher(
            String,
            '/smart_home/discovered_devices',
            default_qos
        )
        
        # Initialize MQTT connection
        self.initialize_mqtt_client()
        
        # Start device discovery if enabled
        if self.discovery_enabled:
            self.start_device_discovery()
        
        # Initialize predefined devices
        self.initialize_default_devices()
        
        # Start device refresh timer
        self.device_refresh_timer = self.create_timer(
            self.get_parameter('devices.auto_refresh_interval').value,
            self.refresh_device_states
        )
        
        self.get_logger().info("MQTT Adapter Node initialized - Smart home integration ready")

    def create_http_session(self) -> requests.Session:
        """Create HTTP session with retry strategy."""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session

    def initialize_mqtt_client(self):
        """Initialize MQTT client connection."""
        try:
            self.mqtt_client = mqtt.Client(
                client_id=self.get_parameter('mqtt.client_id').value,
                clean_session=True
            )
            
            # Set credentials if provided
            if self.username and self.password:
                self.mqtt_client.username_pw_set(self.username, self.password)
            
            # Configure TLS if enabled
            if self.use_tls:
                self.mqtt_client.tls_set(ca_certs=None, certfile=None, keyfile=None,
                                       cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS,
                                       ciphers=None)
            
            # Set callbacks
            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
            self.mqtt_client.on_message = self.on_mqtt_message
            self.mqtt_client.on_publish = self.on_mqtt_publish
            
            # Connect to broker
            self.get_logger().info(f"Connecting to MQTT broker: {self.broker_host}:{self.broker_port}")
            self.mqtt_client.connect(self.broker_host, self.broker_port, 
                                   self.get_parameter('mqtt.keepalive').value)
            
            # Start MQTT loop in separate thread
            self.mqtt_client.loop_start()
            
        except Exception as e:
            self.get_logger().error(f"MQTT client initialization failed: {e}")

    def on_mqtt_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection callback."""
        if rc == 0:
            self.mqtt_connected = True
            self.get_logger().info("Connected to MQTT broker successfully")
            
            # Subscribe to device topics
            self.subscribe_to_device_topics()
            
        else:
            self.get_logger().error(f"MQTT connection failed with code {rc}")

    def on_mqtt_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnection callback."""
        self.mqtt_connected = False
        if rc != 0:
            self.get_logger().warning("Unexpected MQTT disconnection")
        else:
            self.get_logger().info("MQTT disconnected")

    def on_mqtt_message(self, client, userdata, msg):
        """Handle MQTT message callback."""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            self.get_logger().debug(f"MQTT message received - Topic: {topic}, Payload: {payload}")
            
            # Process device status updates
            self.process_device_status_update(topic, payload)
            
        except Exception as e:
            self.get_logger().error(f"MQTT message processing error: {e}")

    def on_mqtt_publish(self, client, userdata, mid):
        """Handle MQTT publish callback."""
        self.get_logger().debug(f"MQTT message published: {mid}")

    def subscribe_to_device_topics(self):
        """Subscribe to device status topics."""
        try:
            # Subscribe to common device discovery topics
            discovery_topics = [
                "homeassistant/+/+/config",
                "zigbee2mqtt/+",
                "tasmota/+/+",
                "elderly_companion/devices/+/status",
                "elderly_companion/devices/+/state"
            ]
            
            for topic in discovery_topics:
                self.mqtt_client.subscribe(topic)
                self.get_logger().debug(f"Subscribed to MQTT topic: {topic}")
                
        except Exception as e:
            self.get_logger().error(f"Device topic subscription error: {e}")

    def start_device_discovery(self):
        """Start device discovery process."""
        try:
            self.get_logger().info("Starting smart home device discovery...")
            
            # Discover Home Assistant devices
            if self.ha_enabled:
                self.discover_homeassistant_devices()
            
            # Discover MQTT devices
            self.discover_mqtt_devices()
            
            # Publish discovered devices
            self.publish_discovered_devices()
            
        except Exception as e:
            self.get_logger().error(f"Device discovery error: {e}")

    def discover_homeassistant_devices(self):
        """Discover devices from Home Assistant."""
        try:
            if not self.ha_url or not self.ha_token:
                return
            
            headers = {
                'Authorization': f'Bearer {self.ha_token}',
                'Content-Type': 'application/json'
            }
            
            # Get device registry
            response = self.http_session.get(
                f"{self.ha_url}/api/config/device_registry",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                devices_data = response.json()
                
                for device_info in devices_data:
                    device = self.create_device_from_ha_info(device_info)
                    if device:
                        self.discovered_devices[device.device_id] = device
                
                self.get_logger().info(f"Discovered {len(devices_data)} Home Assistant devices")
                
        except Exception as e:
            self.get_logger().error(f"Home Assistant device discovery error: {e}")

    def discover_mqtt_devices(self):
        """Discover devices through MQTT."""
        try:
            # Send discovery requests
            discovery_requests = [
                {"topic": "elderly_companion/devices/discover", "payload": "request"},
                {"topic": "zigbee2mqtt/bridge/request/devices", "payload": ""},
                {"topic": "tasmota/cmnd/tasmotas/status", "payload": "0"}
            ]
            
            for request in discovery_requests:
                if self.mqtt_connected:
                    self.mqtt_client.publish(request["topic"], request["payload"])
                    
        except Exception as e:
            self.get_logger().error(f"MQTT device discovery error: {e}")

    def initialize_default_devices(self):
        """Initialize default devices for elderly home."""
        try:
            default_devices = [
                # Living room devices
                SmartDevice(
                    device_id="living_room_light",
                    name="Living Room Light",
                    device_type=DeviceType.LIGHT,
                    protocol=DeviceProtocol.MQTT,
                    mqtt_topic="elderly_companion/devices/living_room_light",
                    capabilities=["turn_on", "turn_off", "dimming"],
                    location="living_room"
                ),
                
                # Bedroom devices
                SmartDevice(
                    device_id="bedroom_light",
                    name="Bedroom Light", 
                    device_type=DeviceType.LIGHT,
                    protocol=DeviceProtocol.MQTT,
                    mqtt_topic="elderly_companion/devices/bedroom_light",
                    capabilities=["turn_on", "turn_off", "dimming"],
                    location="bedroom"
                ),
                
                # Emergency button
                SmartDevice(
                    device_id="emergency_button",
                    name="Emergency Button",
                    device_type=DeviceType.EMERGENCY_BUTTON,
                    protocol=DeviceProtocol.MQTT,
                    mqtt_topic="elderly_companion/devices/emergency_button",
                    capabilities=["press", "status"],
                    location="bedroom"
                ),
                
                # Thermostat
                SmartDevice(
                    device_id="main_thermostat",
                    name="Main Thermostat",
                    device_type=DeviceType.THERMOSTAT,
                    protocol=DeviceProtocol.MQTT,
                    mqtt_topic="elderly_companion/devices/thermostat",
                    capabilities=["set_temperature", "get_temperature", "set_mode"],
                    location="living_room"
                ),
            ]
            
            for device in default_devices:
                self.discovered_devices[device.device_id] = device
                
            self.get_logger().info(f"Initialized {len(default_devices)} default devices")
            
        except Exception as e:
            self.get_logger().error(f"Default device initialization error: {e}")

    def handle_smart_home_intent_callback(self, msg: IntentResult):
        """Handle validated smart home intents."""
        try:
            if msg.intent_type != 'smart_home':
                return
            
            self.get_logger().info(f"Processing smart home intent: {msg.parameter_names}")
            
            # Extract device command from intent
            command = self.extract_device_command_from_intent(msg)
            
            if command:
                # Execute the command
                self.execute_device_command(command)
            else:
                self.get_logger().warning("Could not extract device command from intent")
                self.publish_command_result("error", "Could not understand device command")
                
        except Exception as e:
            self.get_logger().error(f"Smart home intent handling error: {e}")

    def extract_device_command_from_intent(self, intent: IntentResult) -> Optional[DeviceCommand]:
        """Extract device command from intent parameters."""
        try:
            # Create parameter dictionary
            params = {}
            if intent.parameter_names and intent.parameter_values:
                params = dict(zip(intent.parameter_names, intent.parameter_values))
            
            # Determine device and action
            device_id = params.get('device', '')
            action = params.get('action', '')
            
            # If not found in parameters, try to parse from conversation context
            if not device_id or not action:
                device_id, action = self.parse_device_command_from_context(intent)
            
            if device_id and action:
                command = DeviceCommand(
                    device_id=device_id,
                    action=action,
                    parameters=params,
                    timestamp=datetime.now(),
                    user_intent=intent.intent_type,
                    safety_validated=True  # Already validated by safety guard
                )
                
                return command
            
            return None
            
        except Exception as e:
            self.get_logger().error(f"Device command extraction error: {e}")
            return None

    def parse_device_command_from_context(self, intent: IntentResult) -> Tuple[str, str]:
        """Parse device command from conversation context."""
        try:
            # This would integrate with the dialog manager to get the original speech text
            # For now, we'll use a simple approach based on common patterns
            
            # Default to living room light for basic commands
            device_id = "living_room_light"
            action = "toggle"
            
            # Check if we can infer from emotion or other context
            if intent.emotional_context:
                emotion = intent.emotional_context.primary_emotion
                
                # If person seems stressed, they might want brighter lights
                if emotion in ['fear', 'worried']:
                    action = "turn_on"
                elif emotion in ['tired', 'sleepy']:
                    action = "turn_off"
            
            return device_id, action
            
        except Exception as e:
            self.get_logger().error(f"Context parsing error: {e}")
            return "", ""

    def execute_device_command(self, command: DeviceCommand):
        """Execute device command."""
        try:
            self.get_logger().info(f"Executing command: {command.action} on {command.device_id}")
            
            # Find the device
            device = self.discovered_devices.get(command.device_id)
            if not device:
                self.get_logger().warning(f"Device not found: {command.device_id}")
                self.publish_command_result("error", f"Device {command.device_id} not found")
                return
            
            # Execute based on protocol
            if device.protocol == DeviceProtocol.MQTT:
                self.execute_mqtt_command(device, command)
            elif device.protocol == DeviceProtocol.REST_API:
                self.execute_rest_command(device, command)
            else:
                self.get_logger().warning(f"Unsupported protocol: {device.protocol}")
                self.publish_command_result("error", f"Protocol {device.protocol.value} not supported")
            
            # Add to command history
            self.command_history.append(command)
            if len(self.command_history) > 100:
                self.command_history = self.command_history[-100:]
                
        except Exception as e:
            self.get_logger().error(f"Device command execution error: {e}")
            self.publish_command_result("error", str(e))

    def execute_mqtt_command(self, device: SmartDevice, command: DeviceCommand):
        """Execute MQTT device command."""
        try:
            if not self.mqtt_connected:
                raise Exception("MQTT not connected")
            
            # Prepare command payload
            payload = self.prepare_mqtt_payload(device, command)
            
            # Publish command
            topic = f"{device.mqtt_topic}/command"
            self.mqtt_client.publish(topic, json.dumps(payload))
            
            self.get_logger().info(f"MQTT command sent to {topic}: {payload}")
            
            # Publish success result
            self.publish_command_result("success", 
                f"Command {command.action} sent to {device.name}")
            
        except Exception as e:
            self.get_logger().error(f"MQTT command execution error: {e}")
            self.publish_command_result("error", str(e))

    def prepare_mqtt_payload(self, device: SmartDevice, command: DeviceCommand) -> Dict[str, Any]:
        """Prepare MQTT payload for device command."""
        try:
            base_payload = {
                "device_id": device.device_id,
                "command": command.action,
                "timestamp": command.timestamp.isoformat(),
                "source": "elderly_companion_robot"
            }
            
            # Add device-specific parameters
            if device.device_type == DeviceType.LIGHT:
                if command.action == "turn_on":
                    base_payload.update({"state": "ON", "brightness": 255})
                elif command.action == "turn_off":
                    base_payload.update({"state": "OFF"})
                elif command.action == "toggle":
                    base_payload.update({"state": "TOGGLE"})
                    
            elif device.device_type == DeviceType.THERMOSTAT:
                if command.action == "set_temperature":
                    temp = command.parameters.get("temperature", 22)
                    base_payload.update({"temperature": temp})
                    
            # Add any additional parameters from command
            base_payload.update(command.parameters)
            
            return base_payload
            
        except Exception as e:
            self.get_logger().error(f"MQTT payload preparation error: {e}")
            return {"error": str(e)}

    def execute_rest_command(self, device: SmartDevice, command: DeviceCommand):
        """Execute REST API device command."""
        try:
            if not device.rest_endpoint:
                raise Exception("No REST endpoint configured for device")
            
            # Prepare request
            payload = self.prepare_rest_payload(device, command)
            headers = {'Content-Type': 'application/json'}
            
            # Add authentication if needed
            if self.ha_token and 'homeassistant' in device.rest_endpoint:
                headers['Authorization'] = f'Bearer {self.ha_token}'
            
            # Send request
            response = self.http_session.post(
                device.rest_endpoint,
                json=payload,
                headers=headers,
                timeout=self.get_parameter('devices.command_timeout').value
            )
            
            if response.status_code in [200, 201, 202]:
                self.get_logger().info(f"REST command successful: {response.status_code}")
                self.publish_command_result("success", 
                    f"Command {command.action} sent to {device.name}")
            else:
                raise Exception(f"REST API error: {response.status_code} - {response.text}")
                
        except Exception as e:
            self.get_logger().error(f"REST command execution error: {e}")
            self.publish_command_result("error", str(e))

    def prepare_rest_payload(self, device: SmartDevice, command: DeviceCommand) -> Dict[str, Any]:
        """Prepare REST API payload for device command."""
        try:
            # Home Assistant format
            if 'homeassistant' in (device.rest_endpoint or ''):
                return {
                    "entity_id": device.device_id,
                    "action": command.action,
                    **command.parameters
                }
            
            # Generic format
            return {
                "device_id": device.device_id,
                "command": command.action,
                "parameters": command.parameters,
                "timestamp": command.timestamp.isoformat()
            }
            
        except Exception as e:
            self.get_logger().error(f"REST payload preparation error: {e}")
            return {"error": str(e)}

    def handle_emergency_alert_callback(self, msg: EmergencyAlert):
        """Handle emergency alerts with device coordination."""
        try:
            self.get_logger().critical(f"Emergency alert - coordinating devices: {msg.emergency_type}")
            
            # Execute emergency device protocols
            emergency_commands = self.generate_emergency_device_commands(msg)
            
            for command in emergency_commands:
                self.execute_device_command(command)
            
        except Exception as e:
            self.get_logger().error(f"Emergency device coordination error: {e}")

    def generate_emergency_device_commands(self, alert: EmergencyAlert) -> List[DeviceCommand]:
        """Generate device commands for emergency situations."""
        commands = []
        
        try:
            timestamp = datetime.now()
            
            if alert.emergency_type in ["medical", "fall"]:
                # Turn on all lights for visibility
                for device_id in self.emergency_devices['lights']:
                    if device_id in self.discovered_devices:
                        commands.append(DeviceCommand(
                            device_id=device_id,
                            action="turn_on",
                            parameters={"brightness": 100, "emergency": True},
                            timestamp=timestamp,
                            user_intent="emergency",
                            safety_validated=True
                        ))
                
                # Unlock doors for emergency responders
                for device_id in self.emergency_devices['security']:
                    if device_id in self.discovered_devices and 'lock' in device_id:
                        commands.append(DeviceCommand(
                            device_id=device_id,
                            action="unlock",
                            parameters={"emergency_override": True},
                            timestamp=timestamp,
                            user_intent="emergency",
                            safety_validated=True
                        ))
            
            elif alert.emergency_type == "security":
                # Activate security devices
                for device_id in self.emergency_devices['security']:
                    if device_id in self.discovered_devices:
                        commands.append(DeviceCommand(
                            device_id=device_id,
                            action="activate",
                            parameters={"alert_mode": True},
                            timestamp=timestamp,
                            user_intent="emergency",
                            safety_validated=True
                        ))
            
            return commands
            
        except Exception as e:
            self.get_logger().error(f"Emergency command generation error: {e}")
            return []

    def process_device_status_update(self, topic: str, payload: str):
        """Process device status updates from MQTT."""
        try:
            # Parse payload
            try:
                data = json.loads(payload)
            except:
                data = {"value": payload}
            
            # Extract device ID from topic
            device_id = self.extract_device_id_from_topic(topic)
            
            if device_id and device_id in self.discovered_devices:
                device = self.discovered_devices[device_id]
                device.current_state = data
                device.last_updated = datetime.now()
                
                # Publish status update
                self.publish_device_status(device)
                
        except Exception as e:
            self.get_logger().error(f"Device status update processing error: {e}")

    def extract_device_id_from_topic(self, topic: str) -> Optional[str]:
        """Extract device ID from MQTT topic."""
        try:
            # Handle different topic patterns
            if "elderly_companion/devices/" in topic:
                parts = topic.split("/")
                if len(parts) >= 3:
                    return parts[2]
            
            # Add other topic patterns as needed
            return None
            
        except Exception as e:
            self.get_logger().error(f"Device ID extraction error: {e}")
            return None

    def create_device_from_ha_info(self, device_info: Dict[str, Any]) -> Optional[SmartDevice]:
        """Create SmartDevice from Home Assistant device info."""
        try:
            device_id = device_info.get('id', '')
            name = device_info.get('name', '')
            
            if not device_id or not name:
                return None
            
            # Determine device type
            device_type = self.determine_device_type_from_ha(device_info)
            
            device = SmartDevice(
                device_id=device_id,
                name=name,
                device_type=device_type,
                protocol=DeviceProtocol.REST_API,
                rest_endpoint=f"{self.ha_url}/api/services/{device_type.value}/toggle",
                capabilities=self.get_ha_device_capabilities(device_info),
                location=device_info.get('area_id', 'unknown')
            )
            
            return device
            
        except Exception as e:
            self.get_logger().error(f"HA device creation error: {e}")
            return None

    def determine_device_type_from_ha(self, device_info: Dict[str, Any]) -> DeviceType:
        """Determine device type from Home Assistant device info."""
        name = device_info.get('name', '').lower()
        model = device_info.get('model', '').lower()
        
        if any(keyword in name or keyword in model for keyword in ['light', 'lamp', 'bulb']):
            return DeviceType.LIGHT
        elif any(keyword in name or keyword in model for keyword in ['thermostat', 'temperature']):
            return DeviceType.THERMOSTAT
        elif any(keyword in name or keyword in model for keyword in ['camera', 'cam']):
            return DeviceType.SECURITY_CAMERA
        elif any(keyword in name or keyword in model for keyword in ['lock', 'door']):
            return DeviceType.DOOR_LOCK
        else:
            return DeviceType.LIGHT  # Default

    def get_ha_device_capabilities(self, device_info: Dict[str, Any]) -> List[str]:
        """Get device capabilities from Home Assistant device info."""
        # This would be expanded based on actual HA device information
        return ["turn_on", "turn_off", "toggle"]

    def publish_device_status(self, device: SmartDevice):
        """Publish device status update."""
        try:
            status_data = {
                "device_id": device.device_id,
                "name": device.name,
                "type": device.device_type.value,
                "state": device.current_state,
                "last_updated": device.last_updated.isoformat() if device.last_updated else None
            }
            
            status_msg = String()
            status_msg.data = json.dumps(status_data)
            self.device_status_pub.publish(status_msg)
            
        except Exception as e:
            self.get_logger().error(f"Device status publishing error: {e}")

    def publish_command_result(self, status: str, message: str):
        """Publish command execution result."""
        try:
            result_data = {
                "status": status,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
            
            result_msg = String()
            result_msg.data = json.dumps(result_data)
            self.command_result_pub.publish(result_msg)
            
        except Exception as e:
            self.get_logger().error(f"Command result publishing error: {e}")

    def publish_discovered_devices(self):
        """Publish list of discovered devices."""
        try:
            devices_data = {
                "devices": [
                    {
                        "device_id": device.device_id,
                        "name": device.name,
                        "type": device.device_type.value,
                        "protocol": device.protocol.value,
                        "capabilities": device.capabilities,
                        "location": device.location,
                        "elderly_friendly": device.elderly_friendly
                    }
                    for device in self.discovered_devices.values()
                ],
                "count": len(self.discovered_devices),
                "timestamp": datetime.now().isoformat()
            }
            
            discovery_msg = String()
            discovery_msg.data = json.dumps(devices_data)
            self.device_discovery_pub.publish(discovery_msg)
            
            self.get_logger().info(f"Published {len(self.discovered_devices)} discovered devices")
            
        except Exception as e:
            self.get_logger().error(f"Device discovery publishing error: {e}")

    def refresh_device_states(self):
        """Refresh all device states."""
        try:
            self.get_logger().debug("Refreshing device states...")
            
            for device in self.discovered_devices.values():
                if device.protocol == DeviceProtocol.MQTT and self.mqtt_connected:
                    # Request status update via MQTT
                    status_topic = f"{device.mqtt_topic}/status/request"
                    self.mqtt_client.publish(status_topic, "")
                    
        except Exception as e:
            self.get_logger().error(f"Device state refresh error: {e}")

    def __del__(self):
        """Clean up when node is destroyed."""
        try:
            if hasattr(self, 'mqtt_client') and self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
        except:
            pass


def main(args=None):
    """Run the main entry point."""
    rclpy.init(args=args)
    
    try:
        node = MQTTAdapterNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()