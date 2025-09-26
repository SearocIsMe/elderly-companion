#!/usr/bin/env python3
"""
Dialog Manager Node for Elderly Companion Robdog.

Manages conversation flow, context, and generates appropriate responses.
Specialized for elderly communication patterns and needs.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

import json
import time
import threading
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import random

# ROS2 message imports
from std_msgs.msg import Header, String
from elderly_companion.msg import (
    SpeechResult, EmotionData, IntentResult, 
    HealthStatus, EmergencyAlert, SafetyConstraints
)
from elderly_companion.srv import ValidateIntent


class ConversationState(Enum):
    """Conversation states."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    RESPONDING = "responding"
    WAITING_CONFIRMATION = "waiting_confirmation"
    EMERGENCY = "emergency"


class ResponseType(Enum):
    """Types of responses."""
    ACKNOWLEDGMENT = "acknowledgment"
    QUESTION = "question"
    INFORMATION = "information"
    COMFORT = "comfort"
    EMERGENCY = "emergency"
    CONFIRMATION = "confirmation"
    ERROR = "error"


@dataclass
class ConversationContext:
    """Conversation context data."""
    conversation_id: str
    start_time: datetime
    last_interaction: datetime
    turn_count: int
    current_topic: str
    emotion_history: List[str]
    intent_history: List[str]
    response_history: List[str]
    elderly_preferences: Dict[str, Any]
    safety_level: str


@dataclass
class ResponseTemplate:
    """Response template structure."""
    template_id: str
    category: str
    templates: List[str]
    conditions: Dict[str, Any]
    emotion_tags: List[str]


class DialogManagerNode(Node):
    """
    Dialog Manager Node for elderly companion conversation management.
    
    Responsibilities:
    - Manage conversation flow and context
    - Generate appropriate responses based on elderly communication needs
    - Handle multi-turn conversations with memory
    - Coordinate with safety systems for emergency responses
    - Provide comfort and companionship through natural dialogue
    """

    def __init__(self):
        super().__init__('dialog_manager_node')
        
        # Initialize parameters
        self.declare_parameters(
            namespace='',
            parameters=[
                ('dialog.max_conversation_length', 50),
                ('dialog.context_timeout_minutes', 30),
                ('dialog.response_delay_seconds', 1.0),
                ('elderly.preferred_language', 'zh-CN'),
                ('elderly.communication_style', 'formal'),
                ('elderly.response_speed', 'slow'),
                ('templates.enable_personalization', True),
                ('templates.comfort_frequency', 0.3),
                ('memory.enable_conversation_history', True),
                ('memory.max_history_days', 30),
            ]
        )
        
        # Get parameters
        self.max_conversation_length = self.get_parameter('dialog.max_conversation_length').value
        self.context_timeout = self.get_parameter('dialog.context_timeout_minutes').value
        self.response_delay = self.get_parameter('dialog.response_delay_seconds').value
        self.preferred_language = self.get_parameter('elderly.preferred_language').value
        self.communication_style = self.get_parameter('elderly.communication_style').value
        self.enable_personalization = self.get_parameter('templates.enable_personalization').value
        
        # Conversation state management
        self.current_state = ConversationState.IDLE
        self.active_conversations: Dict[str, ConversationContext] = {}
        self.current_conversation_id: Optional[str] = None
        
        # Response templates
        self.response_templates = self.initialize_response_templates()
        
        # Elderly-specific conversation patterns
        self.elderly_patterns = self.initialize_elderly_patterns()
        
        # Safety integration
        self.safety_client = None
        self.emergency_active = False
        
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
            self.process_validated_intent_callback,
            default_qos
        )
        
        self.emergency_alert_sub = self.create_subscription(
            EmergencyAlert,
            '/emergency/alert',
            self.handle_emergency_callback,
            default_qos
        )
        
        self.speech_with_emotion_sub = self.create_subscription(
            SpeechResult,
            '/speech/with_emotion',
            self.process_speech_input_callback,
            default_qos
        )
        
        # Publishers
        self.response_text_pub = self.create_publisher(
            String,
            '/dialog/response_text',
            default_qos
        )
        
        self.conversation_state_pub = self.create_publisher(
            String,
            '/dialog/conversation_state',
            default_qos
        )
        
        self.tts_request_pub = self.create_publisher(
            String,
            '/tts/request',
            default_qos
        )
        
        # Service clients
        self.safety_validation_client = self.create_client(
            ValidateIntent,
            '/safety_guard/validate_intent'
        )
        
        # Initialize conversation cleanup timer
        self.cleanup_timer = self.create_timer(300.0, self.cleanup_old_conversations)  # 5 minutes
        
        self.get_logger().info("Dialog Manager Node initialized - Ready for elderly conversation")

    def initialize_response_templates(self) -> Dict[str, ResponseTemplate]:
        """Initialize response templates for different situations."""
        templates = {}
        
        # Greeting templates
        templates['greeting'] = ResponseTemplate(
            template_id='greeting',
            category='social',
            templates=[
                "您好！我是您的陪伴机器人，有什么可以帮助您的吗？",
                "早上好！今天感觉怎么样？",
                "您好！很高兴见到您，需要我做什么吗？",
                "Hello! I'm your companion robot. How can I help you today?",
                "Good morning! How are you feeling today?"
            ],
            conditions={'time_of_day': 'any', 'emotion': 'neutral'},
            emotion_tags=['friendly', 'warm', 'welcoming']
        )
        
        # Acknowledgment templates
        templates['acknowledgment'] = ResponseTemplate(
            template_id='acknowledgment',
            category='response',
            templates=[
                "好的，我明白了",
                "是的，我听到了",
                "明白，我会帮您处理的",
                "OK, I understand",
                "Yes, I heard you",
                "I understand, I'll help you with that"
            ],
            conditions={'intent_confidence': '>0.7'},
            emotion_tags=['understanding', 'helpful']
        )
        
        # Comfort templates
        templates['comfort'] = ResponseTemplate(
            template_id='comfort',
            category='emotional_support',
            templates=[
                "没关系，我在这里陪着您",
                "别担心，一切都会好的",
                "我理解您的感受，您不是一个人",
                "It's okay, I'm here with you",
                "Don't worry, everything will be fine",
                "I understand how you feel, you're not alone"
            ],
            conditions={'emotion': ['sad', 'worried', 'lonely']},
            emotion_tags=['comforting', 'supportive', 'caring']
        )
        
        # Emergency response templates
        templates['emergency_response'] = ResponseTemplate(
            template_id='emergency_response',
            category='emergency',
            templates=[
                "我马上为您联系帮助！请保持冷静",
                "紧急情况已经记录，正在联系家人和医生",
                "不要慌张，帮助马上就到",
                "I'm getting help for you right away! Please stay calm",
                "Emergency recorded, contacting family and medical help",
                "Don't panic, help is coming"
            ],
            conditions={'emergency_detected': True},
            emotion_tags=['urgent', 'reassuring', 'professional']
        )
        
        # Health inquiry templates
        templates['health_inquiry'] = ResponseTemplate(
            template_id='health_inquiry',
            category='health',
            templates=[
                "您今天感觉怎么样？有什么不舒服的吗？",
                "需要我帮您记录一下身体状况吗？",
                "您有按时吃药吗？",
                "How are you feeling today? Any discomfort?",
                "Would you like me to record your health status?",
                "Have you taken your medication on time?"
            ],
            conditions={'time_since_last_health_check': '>4_hours'},
            emotion_tags=['caring', 'medical', 'attentive']
        )
        
        # Confusion handling templates
        templates['confusion_help'] = ResponseTemplate(
            template_id='confusion_help',
            category='assistance',
            templates=[
                "没关系，让我慢慢解释给您听",
                "我们可以一步一步来，不着急",
                "您可以再说一遍吗？我会仔细听的",
                "It's okay, let me explain slowly",
                "We can take it step by step, no rush",
                "Could you say that again? I'll listen carefully"
            ],
            conditions={'speech_confidence': '<0.5', 'elderly_confusion': True},
            emotion_tags=['patient', 'understanding', 'gentle']
        )
        
        # Smart home confirmation templates
        templates['smart_home_confirm'] = ResponseTemplate(
            template_id='smart_home_confirm',
            category='confirmation',
            templates=[
                "好的，我来为您{action}{device}",
                "正在{action}{device}，请稍等",
                "已经为您{action}了{device}",
                "OK, I'll {action} the {device} for you",
                "I'm {action} the {device}, please wait",
                "I've {action} the {device} for you"
            ],
            conditions={'intent_type': 'smart_home'},
            emotion_tags=['helpful', 'efficient', 'responsive']
        )
        
        return templates

    def initialize_elderly_patterns(self) -> Dict[str, Any]:
        """Initialize elderly-specific communication patterns."""
        return {
            'response_timing': {
                'slow': 2.0,      # Slower responses for processing
                'normal': 1.0,
                'fast': 0.5
            },
            'repetition_tolerance': {
                'high': 3,        # Allow more repetitions
                'normal': 2,
                'low': 1
            },
            'comfort_triggers': [
                'loneliness', 'sadness', 'worry', 'pain', 'confusion'
            ],
            'health_check_frequency': {
                'morning': timedelta(hours=4),
                'afternoon': timedelta(hours=6),
                'evening': timedelta(hours=4)
            },
            'preferred_topics': [
                'family', 'health', 'weather', 'memories', 'daily_activities'
            ]
        }

    def process_speech_input_callback(self, msg: SpeechResult):
        """Process incoming speech with emotion analysis."""
        try:
            self.get_logger().info(f"Processing speech input: '{msg.text}'")
            
            # Create or update conversation context
            if not self.current_conversation_id:
                self.start_new_conversation(msg)
            else:
                self.update_conversation_context(msg)
            
            # Set processing state
            self.set_conversation_state(ConversationState.PROCESSING)
            
            # Analyze speech for intent classification
            intent_result = self.classify_intent_from_speech(msg)
            
            if intent_result:
                # Request safety validation
                self.request_intent_validation(intent_result)
            else:
                # Generate conversational response without specific intent
                self.generate_conversational_response(msg)
            
        except Exception as e:
            self.get_logger().error(f"Speech input processing error: {e}")
            self.generate_error_response("Sorry, I didn't understand that clearly.")

    def start_new_conversation(self, speech_msg: SpeechResult):
        """Start a new conversation session."""
        try:
            self.current_conversation_id = f"conv_{int(time.time())}"
            
            context = ConversationContext(
                conversation_id=self.current_conversation_id,
                start_time=datetime.now(),
                last_interaction=datetime.now(),
                turn_count=1,
                current_topic="greeting",
                emotion_history=[speech_msg.emotion.primary_emotion],
                intent_history=[],
                response_history=[],
                elderly_preferences={
                    'language': self.preferred_language,
                    'style': self.communication_style
                },
                safety_level="normal"
            )
            
            self.active_conversations[self.current_conversation_id] = context
            
            self.get_logger().info(f"Started new conversation: {self.current_conversation_id}")
            
        except Exception as e:
            self.get_logger().error(f"New conversation start error: {e}")

    def update_conversation_context(self, speech_msg: SpeechResult):
        """Update existing conversation context."""
        try:
            if self.current_conversation_id in self.active_conversations:
                context = self.active_conversations[self.current_conversation_id]
                context.last_interaction = datetime.now()
                context.turn_count += 1
                context.emotion_history.append(speech_msg.emotion.primary_emotion)
                
                # Keep emotion history manageable
                if len(context.emotion_history) > 10:
                    context.emotion_history = context.emotion_history[-10:]
                
        except Exception as e:
            self.get_logger().error(f"Conversation context update error: {e}")

    def classify_intent_from_speech(self, speech_msg: SpeechResult) -> Optional[IntentResult]:
        """Classify intent from speech content."""
        try:
            text = speech_msg.text.lower()
            emotion = speech_msg.emotion
            
            # Create intent result
            intent = IntentResult()
            intent.header = Header()
            intent.header.stamp = self.get_clock().now().to_msg()
            intent.header.frame_id = "dialog_manager"
            
            # Pattern-based intent classification
            if any(keyword in text for keyword in ['救命', '急救', 'help', 'emergency']):
                intent.intent_type = 'emergency'
                intent.confidence = 0.9
                intent.priority_level = 4
                
            elif any(keyword in text for keyword in ['开灯', '关灯', 'turn on', 'turn off', 'light']):
                intent.intent_type = 'smart_home'
                intent.confidence = 0.8
                intent.parameter_names = ['device', 'action']
                intent.parameter_values = ['light', 'toggle']
                
            elif any(keyword in text for keyword in ['跟着', '跟我来', 'follow', 'come with']):
                intent.intent_type = 'follow'
                intent.confidence = 0.7
                intent.requires_confirmation = True
                
            elif any(keyword in text for keyword in ['聊天', '说话', 'chat', 'talk', 'tell me']):
                intent.intent_type = 'chat'
                intent.confidence = 0.6
                
            elif any(keyword in text for keyword in ['记住', '回忆', 'remember', 'memory']):
                intent.intent_type = 'memory'
                intent.confidence = 0.7
                
            else:
                # Default to chat intent
                intent.intent_type = 'chat'
                intent.confidence = 0.4
            
            # Add emotional context
            intent.emotional_context = emotion
            intent.conversation_id = self.current_conversation_id or ""
            
            return intent
            
        except Exception as e:
            self.get_logger().error(f"Intent classification error: {e}")
            return None

    def request_intent_validation(self, intent: IntentResult):
        """Request intent validation from safety guard."""
        try:
            if not self.safety_validation_client.service_is_ready():
                self.get_logger().warning("Safety validation service not ready")
                return
            
            # Create validation request
            request = ValidateIntent.Request()
            request.intent = intent
            
            # Add system status if available
            request.system_status = HealthStatus()  # Would be populated with actual status
            request.safety_constraints = SafetyConstraints()  # Would be populated with current constraints
            
            # Call service asynchronously
            future = self.safety_validation_client.call_async(request)
            future.add_done_callback(
                lambda f: self.handle_validation_response(f, intent)
            )
            
        except Exception as e:
            self.get_logger().error(f"Intent validation request error: {e}")
            self.generate_error_response("Sorry, I need to check if that's safe first.")

    def handle_validation_response(self, future, original_intent: IntentResult):
        """Handle validation response from safety guard."""
        try:
            response = future.result()
            
            if response.approved:
                self.get_logger().info(f"Intent approved: {original_intent.intent_type}")
                self.process_validated_intent(original_intent, response)
            else:
                self.get_logger().warning(f"Intent rejected: {response.rejection_reason}")
                self.generate_rejection_response(original_intent, response)
                
        except Exception as e:
            self.get_logger().error(f"Validation response handling error: {e}")
            self.generate_error_response("Sorry, there was a safety check problem.")

    def process_validated_intent_callback(self, msg: IntentResult):
        """Process validated intent and generate appropriate response."""
        try:
            self.get_logger().info(f"Processing validated intent: {msg.intent_type}")
            
            # Update conversation context
            if self.current_conversation_id in self.active_conversations:
                context = self.active_conversations[self.current_conversation_id]
                context.intent_history.append(msg.intent_type)
                context.current_topic = msg.intent_type
            
            # Generate response based on intent type
            if msg.intent_type == 'emergency':
                self.handle_emergency_intent(msg)
            elif msg.intent_type == 'smart_home':
                self.handle_smart_home_intent(msg)
            elif msg.intent_type == 'follow':
                self.handle_follow_intent(msg)
            elif msg.intent_type == 'chat':
                self.handle_chat_intent(msg)
            elif msg.intent_type == 'memory':
                self.handle_memory_intent(msg)
            else:
                self.generate_default_response(msg)
                
        except Exception as e:
            self.get_logger().error(f"Validated intent processing error: {e}")

    def process_validated_intent(self, intent: IntentResult, validation_response):
        """Process intent that has been validated by safety guard."""
        try:
            # Set response timing based on elderly preferences
            response_delay = self.elderly_patterns['response_timing'][self.communication_style]
            
            # Add delay for elderly-appropriate pacing
            threading.Timer(response_delay, lambda: self.execute_validated_intent(intent, validation_response)).start()
            
        except Exception as e:
            self.get_logger().error(f"Validated intent processing error: {e}")

    def execute_validated_intent(self, intent: IntentResult, validation_response):
        """Execute the validated intent with appropriate response."""
        try:
            if intent.intent_type == 'smart_home':
                self.execute_smart_home_action(intent)
            elif intent.intent_type == 'follow':
                self.execute_follow_action(intent)
            elif intent.intent_type == 'chat':
                self.execute_chat_response(intent)
            elif intent.intent_type == 'memory':
                self.execute_memory_action(intent)
            else:
                self.generate_default_response(intent)
                
        except Exception as e:
            self.get_logger().error(f"Intent execution error: {e}")

    def handle_emergency_intent(self, intent: IntentResult):
        """Handle emergency intent with immediate response."""
        try:
            self.emergency_active = True
            self.set_conversation_state(ConversationState.EMERGENCY)
            
            # Generate immediate emergency response
            templates = self.response_templates['emergency_response'].templates
            response = self.select_appropriate_template(templates, intent.emotional_context)
            
            self.send_response(response, ResponseType.EMERGENCY)
            
            self.get_logger().critical("Emergency response generated")
            
        except Exception as e:
            self.get_logger().error(f"Emergency intent handling error: {e}")

    def execute_smart_home_action(self, intent: IntentResult):
        """Execute smart home control action."""
        try:
            # Extract parameters
            device = "device"
            action = "control"
            
            if intent.parameter_names and intent.parameter_values:
                param_dict = dict(zip(intent.parameter_names, intent.parameter_values))
                device = param_dict.get('device', 'device')
                action = param_dict.get('action', 'control')
            
            # Generate confirmation response
            templates = self.response_templates['smart_home_confirm'].templates
            response = random.choice(templates).format(action=action, device=device)
            
            self.send_response(response, ResponseType.CONFIRMATION)
            
        except Exception as e:
            self.get_logger().error(f"Smart home action execution error: {e}")

    def execute_follow_action(self, intent: IntentResult):
        """Execute follow action with safety confirmation."""
        try:
            if intent.requires_confirmation:
                self.set_conversation_state(ConversationState.WAITING_CONFIRMATION)
                response = "好的，我来跟着您。请确认这样安全吗？"
            else:
                response = "好的，我开始跟着您了。请慢慢走。"
            
            self.send_response(response, ResponseType.CONFIRMATION)
            
        except Exception as e:
            self.get_logger().error(f"Follow action execution error: {e}")

    def execute_chat_response(self, intent: IntentResult):
        """Execute chat response with emotional consideration."""
        try:
            emotion = intent.emotional_context
            
            # Select appropriate response based on emotion
            if emotion.primary_emotion in ['sad', 'lonely', 'worried']:
                templates = self.response_templates['comfort'].templates
                response_type = ResponseType.COMFORT
            else:
                templates = self.response_templates['acknowledgment'].templates
                response_type = ResponseType.ACKNOWLEDGMENT
            
            response = self.select_appropriate_template(templates, emotion)
            self.send_response(response, response_type)
            
        except Exception as e:
            self.get_logger().error(f"Chat response execution error: {e}")

    def execute_memory_action(self, intent: IntentResult):
        """Execute memory-related action."""
        try:
            response = "我会记住这个信息。还有什么想让我记住的吗？"
            self.send_response(response, ResponseType.INFORMATION)
            
        except Exception as e:
            self.get_logger().error(f"Memory action execution error: {e}")

    def generate_conversational_response(self, speech_msg: SpeechResult):
        """Generate conversational response without specific intent."""
        try:
            emotion = speech_msg.emotion
            
            # Check if comfort is needed
            if emotion.primary_emotion in self.elderly_patterns['comfort_triggers']:
                templates = self.response_templates['comfort'].templates
                response_type = ResponseType.COMFORT
            else:
                templates = self.response_templates['acknowledgment'].templates
                response_type = ResponseType.ACKNOWLEDGMENT
            
            response = self.select_appropriate_template(templates, emotion)
            self.send_response(response, response_type)
            
        except Exception as e:
            self.get_logger().error(f"Conversational response generation error: {e}")

    def select_appropriate_template(self, templates: List[str], emotion: EmotionData) -> str:
        """Select appropriate template based on context and emotion."""
        try:
            # Filter templates by language preference
            if self.preferred_language == 'zh-CN':
                chinese_templates = [t for t in templates if any('\u4e00' <= c <= '\u9fff' for c in t)]
                if chinese_templates:
                    return random.choice(chinese_templates)
            else:
                english_templates = [t for t in templates if not any('\u4e00' <= c <= '\u9fff' for c in t)]
                if english_templates:
                    return random.choice(english_templates)
            
            # Fallback to any template
            return random.choice(templates)
            
        except Exception as e:
            self.get_logger().error(f"Template selection error: {e}")
            return "I understand."

    def send_response(self, response_text: str, response_type: ResponseType):
        """Send response through multiple channels."""
        try:
            # Log the response
            self.get_logger().info(f"Sending response ({response_type.value}): {response_text}")
            
            # Publish response text
            response_msg = String()
            response_msg.data = response_text
            self.response_text_pub.publish(response_msg)
            
            # Send to TTS system
            self.tts_request_pub.publish(response_msg)
            
            # Update conversation context
            if self.current_conversation_id in self.active_conversations:
                context = self.active_conversations[self.current_conversation_id]
                context.response_history.append(response_text)
                
                # Keep response history manageable
                if len(context.response_history) > 20:
                    context.response_history = context.response_history[-20:]
            
            # Update conversation state
            self.set_conversation_state(ConversationState.RESPONDING)
            
        except Exception as e:
            self.get_logger().error(f"Response sending error: {e}")

    def generate_rejection_response(self, intent: IntentResult, validation_response):
        """Generate response for rejected intent."""
        try:
            reason = validation_response.rejection_reason
            alternatives = validation_response.alternative_suggestions
            
            if alternatives:
                response = f"抱歉，现在不能{intent.intent_type}，但是我可以{alternatives[0]}。"
            else:
                response = f"抱歉，为了安全考虑，现在不能执行这个操作：{reason}"
            
            self.send_response(response, ResponseType.ERROR)
            
        except Exception as e:
            self.get_logger().error(f"Rejection response generation error: {e}")

    def generate_error_response(self, error_message: str):
        """Generate error response."""
        try:
            response = f"抱歉，{error_message}，请再说一遍好吗？"
            self.send_response(response, ResponseType.ERROR)
            
        except Exception as e:
            self.get_logger().error(f"Error response generation error: {e}")

    def generate_default_response(self, intent: IntentResult):
        """Generate default response for unhandled intents."""
        try:
            response = "我明白了，让我想想怎么帮助您。"
            self.send_response(response, ResponseType.ACKNOWLEDGMENT)
            
        except Exception as e:
            self.get_logger().error(f"Default response generation error: {e}")

    def handle_emergency_callback(self, msg: EmergencyAlert):
        """Handle emergency alert from safety system."""
        try:
            self.emergency_active = True
            self.set_conversation_state(ConversationState.EMERGENCY)
            
            self.get_logger().critical(f"Emergency alert received: {msg.emergency_type}")
            
            # Generate emergency-specific response
            if msg.emergency_type == "medical":
                response = "医疗紧急情况已确认，正在联系医生和家人，请保持冷静。"
            elif msg.emergency_type == "fall":
                response = "检测到跌倒，正在立即联系帮助，请不要强行站起。"
            else:
                response = "紧急情况已记录，帮助正在路上，请保持冷静。"
            
            self.send_response(response, ResponseType.EMERGENCY)
            
        except Exception as e:
            self.get_logger().error(f"Emergency callback handling error: {e}")

    def set_conversation_state(self, state: ConversationState):
        """Set and publish conversation state."""
        try:
            self.current_state = state
            
            state_msg = String()
            state_msg.data = state.value
            self.conversation_state_pub.publish(state_msg)
            
        except Exception as e:
            self.get_logger().error(f"Conversation state setting error: {e}")

    def cleanup_old_conversations(self):
        """Clean up old conversation contexts."""
        try:
            cutoff_time = datetime.now() - timedelta(minutes=self.context_timeout)
            
            # Remove old conversations
            to_remove = []
            for conv_id, context in self.active_conversations.items():
                if context.last_interaction < cutoff_time:
                    to_remove.append(conv_id)
            
            for conv_id in to_remove:
                del self.active_conversations[conv_id]
                if self.current_conversation_id == conv_id:
                    self.current_conversation_id = None
                    self.set_conversation_state(ConversationState.IDLE)
            
            if to_remove:
                self.get_logger().info(f"Cleaned up {len(to_remove)} old conversations")
                
        except Exception as e:
            self.get_logger().error(f"Conversation cleanup error: {e}")


def main(args=None):
    """Run the main entry point."""
    rclpy.init(args=args)
    
    try:
        node = DialogManagerNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()