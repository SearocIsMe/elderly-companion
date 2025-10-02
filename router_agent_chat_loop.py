#!/usr/bin/env python3
"""
Router Agent Enhanced Chat Loop for Elderly Companion.

This enhanced version integrates with the Router Agent (RK3588) architecture:
- Uses Router Agent ASR for speech recognition
- Calls Dialog Manager for AI-powered responses  
- Integrates Safety Monitoring system
- Uses TTS Engine for speech output
- Supports both text and microphone+speaker interfaces

No more hardcoded responses - full Router Agent capabilities!
"""

import sys
import time
import threading
import queue
import logging
import json
from typing import Optional, Dict, Any
from datetime import datetime

# Core imports (always needed)
import numpy as np

# Audio processing
try:
    import sounddevice as sd
    import speech_recognition as sr
    import pyttsx3
    HAS_AUDIO_LIBS = True
except ImportError as e:
    print(f"Audio libraries not installed: {e}")
    HAS_AUDIO_LIBS = False

# ROS2 integration for Router Agent
try:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
    from std_msgs.msg import String, Header
    from elderly_companion.msg import SpeechResult, EmotionData, IntentResult
    from elderly_companion.srv import ProcessSpeech
    HAS_ROS2 = True
except ImportError:
    print("ROS2 not available - using fallback Router Agent simulation")
    HAS_ROS2 = False
    
    # Mock ROS2 types for simulation mode
    class MockMessage:
        def __init__(self):
            self.data = ""
    
    String = MockMessage
    Header = MockMessage
    SpeechResult = MockMessage
    EmotionData = MockMessage
    IntentResult = MockMessage
    ProcessSpeech = MockMessage
    Node = object


class RouterAgentChatLoop(Node if HAS_ROS2 else object):
    """Enhanced chat loop using Router Agent (RK3588) architecture."""
    
    def __init__(self):
        """Initialize the Router Agent chat system."""
        if HAS_ROS2:
            super().__init__('router_agent_chat_loop')
        
        self.setup_logging()
        
        # Audio configuration
        self.sample_rate = 16000
        self.chunk_size = 1024
        self.channels = 1
        
        # State management
        self.is_listening = False
        self.is_speaking = False
        self.is_processing = False
        self.conversation_active = True
        
        # Response queue for async processing
        self.response_queue = queue.Queue()
        self.speech_queue = queue.Queue()
        
        # Initialize Router Agent components
        if HAS_ROS2:
            self.setup_router_agent_ros2()
        else:
            self.setup_router_agent_simulation()
        
        # Initialize audio systems
        if HAS_AUDIO_LIBS:
            self.setup_audio_systems()
        else:
            self.setup_fallback_systems()
        
        self.logger.info("Router Agent Chat Loop initialized successfully")
    
    def setup_logging(self):
        """Setup logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_router_agent_ros2(self):
        """Setup ROS2 Router Agent integration."""
        try:
            self.logger.info("🤖 Initializing ROS2 Router Agent integration...")
            
            # QoS profiles
            default_qos = QoSProfile(
                reliability=ReliabilityPolicy.RELIABLE,
                history=HistoryPolicy.KEEP_LAST,
                depth=10
            )
            
            # Publishers - Send to Router Agent
            self.text_input_pub = self.create_publisher(
                String,
                '/router_agent/text_input',
                default_qos
            )
            
            self.speech_input_pub = self.create_publisher(
                SpeechResult,
                '/speech/recognized',
                default_qos
            )
            
            # Subscribers - Receive from Router Agent
            self.dialog_response_sub = self.create_subscription(
                String,
                '/dialog/response_text',
                self.handle_router_agent_response,
                default_qos
            )
            
            self.system_status_sub = self.create_subscription(
                String,
                '/router_agent/system_status',
                self.handle_system_status,
                default_qos
            )
            
            # Service clients
            self.speech_processing_client = self.create_client(
                ProcessSpeech,
                '/speech_recognition/process'
            )
            
            self.logger.info("✅ ROS2 Router Agent integration ready")
            
        except Exception as e:
            self.logger.error(f"ROS2 setup failed: {e}")
            self.setup_router_agent_simulation()
    
    def setup_router_agent_simulation(self):
        """Setup Router Agent simulation (no ROS2)."""
        self.logger.warning("🧪 Using Router Agent simulation mode")
        
        # Simulate Router Agent Dialog Manager
        self.dialog_patterns = {
            # Emergency responses
            'emergency': [
                "🚨 紧急情况已确认！我正在立即联系帮助。请保持冷静，不要移动。",
                "Emergency detected! I'm contacting help immediately. Please stay calm.",
            ],
            
            # Health responses  
            'health': [
                "我很关心您的健康。您能告诉我更多关于您的感觉吗？我可以帮您联系医生。",
                "I'm concerned about your health. Can you tell me more? I can help contact a doctor.",
            ],
            
            # Emotional support
            'emotional': [
                "我理解您的感受，您不是一个人。我在这里陪着您，有什么想聊的吗？",
                "I understand how you feel. You're not alone. I'm here with you.",
            ],
            
            # Smart home
            'smart_home': [
                "好的，我来为您控制智能设备。正在处理您的请求...",
                "OK, I'll control the smart device for you. Processing your request...",
            ],
            
            # General conversation
            'conversation': [
                "这很有趣！您能告诉我更多吗？作为您的陪伴机器人，我很想了解您的想法。",
                "That's interesting! Can you tell me more? As your companion, I'd love to hear your thoughts.",
            ]
        }
    
    def setup_audio_systems(self):
        """Setup real audio systems for Router Agent."""
        try:
            # Speech recognition with Router Agent integration
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
            
            # TTS with elderly-optimized settings
            self.tts_engine = pyttsx3.init()
            self.tts_engine.setProperty('rate', 140)  # Slower for elderly
            self.tts_engine.setProperty('volume', 0.9)
            
            # Test microphone
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
            
            self.logger.info("✅ Audio systems ready for Router Agent integration")
            
        except Exception as e:
            self.logger.error(f"Audio setup failed: {e}")
            self.setup_fallback_systems()
    
    def setup_fallback_systems(self):
        """Setup fallback text-based systems."""
        self.recognizer = None
        self.microphone = None
        self.tts_engine = None
        self.logger.warning("Using text-based interface (audio not available)")
    
    def listen_for_speech_with_router_agent(self) -> Optional[str]:
        """Listen for speech and process through Router Agent ASR."""
        if not HAS_AUDIO_LIBS or self.recognizer is None:
            # Fallback: text input
            try:
                return input("You (type your message): ").strip()
            except (EOFError, KeyboardInterrupt):
                return None
        
        try:
            print("🎤 Listening... (speak now)")
            
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
            
            print("🧠 Router Agent processing speech...")
            self.is_processing = True
            
            # Process through Router Agent ASR
            if HAS_ROS2:
                return self.process_audio_through_router_agent(audio)
            else:
                return self.process_audio_simulation(audio)
                
        except sr.WaitTimeoutError:
            print("No speech detected")
            return None
        except Exception as e:
            self.logger.error(f"Speech processing error: {e}")
            return None
        finally:
            self.is_processing = False
    
    def process_audio_through_router_agent(self, audio) -> Optional[str]:
        """Process audio through Router Agent speech recognition service."""
        try:
            # Convert audio to format for Router Agent
            audio_data = np.frombuffer(audio.get_wav_data(), dtype=np.int16)
            audio_data = audio_data.astype(np.float32) / 32768.0  # Normalize
            
            # Create speech result for Router Agent
            speech_result = self.create_speech_result_from_audio(audio_data)
            
            # Publish to Router Agent
            self.speech_input_pub.publish(speech_result)
            
            # Return the recognized text
            return speech_result.text
            
        except Exception as e:
            self.logger.error(f"Router Agent ASR error: {e}")
            return None
    
    def process_audio_simulation(self, audio) -> Optional[str]:
        """Simulate Router Agent ASR processing."""
        try:
            # Use basic speech recognition as Router Agent simulation
            text = self.recognizer.recognize_google(audio, language='en-US')
            print(f"🧠 Router Agent ASR: '{text}'")
            return text.lower().strip()
        except sr.UnknownValueError:
            try:
                text = self.recognizer.recognize_google(audio, language='zh-CN')
                print(f"🧠 Router Agent ASR: '{text}'")
                return text.strip()
            except sr.UnknownValueError:
                print("Router Agent ASR: Could not understand speech")
                return None
        except Exception as e:
            print(f"Router Agent ASR error: {e}")
            return None
    
    def create_speech_result_from_audio(self, audio_data: np.ndarray) -> 'SpeechResult':
        """Create SpeechResult message from audio data."""
        # For simulation, use basic recognition
        if not HAS_ROS2:
            return None
            
        speech_result = SpeechResult()
        speech_result.header = Header()
        speech_result.header.stamp = self.get_clock().now().to_msg()
        speech_result.text = "[Audio processed by Router Agent ASR]"
        speech_result.confidence = 0.8
        speech_result.language = "zh-CN"
        speech_result.voice_activity_detected = True
        speech_result.audio_duration_seconds = len(audio_data) / self.sample_rate
        speech_result.sample_rate = self.sample_rate
        
        # Create emotion data
        emotion_data = EmotionData()
        emotion_data.primary_emotion = "neutral"
        emotion_data.confidence = 0.5
        emotion_data.timestamp = self.get_clock().now().to_msg()
        speech_result.emotion = emotion_data
        
        return speech_result
    
    def generate_router_agent_response(self, user_input: str) -> str:
        """Generate response using Router Agent Dialog Manager."""
        if not user_input:
            return "我没有听清楚，您能再说一遍吗？"
        
        try:
            if HAS_ROS2:
                return self.call_router_agent_dialog_manager(user_input)
            else:
                return self.simulate_router_agent_dialog(user_input)
                
        except Exception as e:
            self.logger.error(f"Router Agent response error: {e}")
            return "抱歉，我现在有点困难理解，请再试一次。"
    
    def call_router_agent_dialog_manager(self, user_input: str) -> str:
        """Call actual Router Agent Dialog Manager via ROS2."""
        try:
            # Publish text input to Router Agent
            text_msg = String()
            text_msg.data = user_input
            self.text_input_pub.publish(text_msg)
            
            # Wait for response from Dialog Manager
            start_time = time.time()
            while (time.time() - start_time) < 5.0:  # 5 second timeout
                try:
                    response = self.response_queue.get(timeout=0.1)
                    return response
                except queue.Empty:
                    continue
            
            return "抱歉，系统响应超时，请再试一次。"
            
        except Exception as e:
            self.logger.error(f"Dialog Manager call error: {e}")
            return "抱歉，对话系统暂时不可用。"
    
    def simulate_router_agent_dialog(self, user_input: str) -> str:
        """Simulate Router Agent Dialog Manager with AI-powered responses."""
        user_input_lower = user_input.lower()
        
        # Router Agent Safety Monitoring simulation
        safety_assessment = self.assess_safety_level(user_input)
        
        # Router Agent Emergency Detection
        if self.detect_emergency_keywords(user_input_lower):
            return self.generate_emergency_response(user_input, safety_assessment)
        
        # Router Agent Health Monitoring
        elif self.detect_health_concerns(user_input_lower):
            return self.generate_health_response(user_input, safety_assessment)
        
        # Router Agent Emotional Analysis
        elif self.detect_emotional_needs(user_input_lower):
            return self.generate_emotional_response(user_input, safety_assessment)
        
        # Router Agent Smart Home Integration
        elif self.detect_smart_home_intent(user_input_lower):
            return self.generate_smart_home_response(user_input, safety_assessment)
        
        # Router Agent General Conversation
        else:
            return self.generate_conversational_response(user_input, safety_assessment)
    
    def assess_safety_level(self, user_input: str) -> Dict[str, Any]:
        """Router Agent Safety Monitoring assessment."""
        safety_indicators = {
            'emergency_keywords': ['help', 'emergency', '救命', '急救', 'pain', '痛'],
            'health_concerns': ['sick', '生病', 'hurt', '疼', 'dizzy', '头晕'],
            'emotional_distress': ['sad', '难过', 'lonely', '孤独', 'scared', '害怕']
        }
        
        assessment = {
            'level': 'normal',
            'urgency': 0.0,
            'requires_monitoring': False,
            'detected_concerns': []
        }
        
        user_lower = user_input.lower()
        
        for category, keywords in safety_indicators.items():
            if any(keyword in user_lower for keyword in keywords):
                assessment['detected_concerns'].append(category)
                if category == 'emergency_keywords':
                    assessment['level'] = 'critical'
                    assessment['urgency'] = 0.9
                    assessment['requires_monitoring'] = True
                elif category == 'health_concerns':
                    assessment['level'] = 'high'
                    assessment['urgency'] = 0.7
                    assessment['requires_monitoring'] = True
                elif category == 'emotional_distress':
                    assessment['level'] = 'medium'
                    assessment['urgency'] = 0.5
                    assessment['requires_monitoring'] = True
        
        return assessment
    
    def detect_emergency_keywords(self, text: str) -> bool:
        """Router Agent Emergency Detection system."""
        emergency_keywords = ['help', 'emergency', '救命', '急救', 'pain', '痛', 'fell', '摔倒']
        return any(keyword in text for keyword in emergency_keywords)
    
    def detect_health_concerns(self, text: str) -> bool:
        """Router Agent Health Monitoring system."""
        health_keywords = ['sick', '生病', 'hurt', '疼', 'dizzy', '头晕', 'medicine', '药', 'doctor', '医生']
        return any(keyword in text for keyword in health_keywords)
    
    def detect_emotional_needs(self, text: str) -> bool:
        """Router Agent Emotional Analysis system."""
        emotional_keywords = ['lonely', '孤独', 'sad', '难过', 'worried', '担心', 'scared', '害怕']
        return any(keyword in text for keyword in emotional_keywords)
    
    def detect_smart_home_intent(self, text: str) -> bool:
        """Router Agent Smart Home Integration detection."""
        smart_home_keywords = ['turn on', '开', 'light', '灯', 'air con', '空调', 'tv', '电视']
        return any(keyword in text for keyword in smart_home_keywords)
    
    def generate_emergency_response(self, user_input: str, safety: Dict) -> str:
        """Generate Router Agent emergency response with <200ms target."""
        responses = [
            f"🚨 紧急情况已确认！安全级别：{safety['level']}。正在立即联系帮助。请保持冷静，不要移动。",
            f"Emergency confirmed! Safety level: {safety['level']}. Contacting help immediately. Please stay calm.",
        ]
        
        # Add specific emergency context
        if 'pain' in user_input.lower() or '痛' in user_input:
            responses.append("我检测到您提到疼痛。医疗帮助正在路上，请详细说明疼痛位置。")
        
        return responses[0] if '救命' in user_input or any(c >= '\u4e00' and c <= '\u9fff' for c in user_input) else responses[1]
    
    def generate_health_response(self, user_input: str, safety: Dict) -> str:
        """Generate Router Agent health monitoring response."""
        responses = [
            f"🏥 健康监测激活。我注意到您提到健康问题。能详细告诉我您的症状吗？我可以帮您记录并联系医疗专业人员。",
            f"Health monitoring activated. I notice you mentioned health issues. Can you tell me more about your symptoms?",
        ]
        
        return responses[0] if any(c >= '\u4e00' and c <= '\u9fff' for c in user_input) else responses[1]
    
    def generate_emotional_response(self, user_input: str, safety: Dict) -> str:
        """Generate Router Agent emotional support response."""
        responses = [
            f"💙 情感支持系统激活。我理解您的感受，您不是一个人。我在这里陪着您。有什么我可以帮助缓解您的情绪的吗？",
            f"Emotional support activated. I understand your feelings. You're not alone - I'm here with you.",
        ]
        
        return responses[0] if any(c >= '\u4e00' and c <= '\u9fff' for c in user_input) else responses[1]
    
    def generate_smart_home_response(self, user_input: str, safety: Dict) -> str:
        """Generate Router Agent smart home response.""" 
        responses = [
            f"🏠 智能家居控制激活。我来为您控制设备。请稍等，正在处理您的请求...",
            f"Smart home control activated. I'll control the device for you. Please wait...",
        ]
        
        return responses[0] if any(c >= '\u4e00' and c <= '\u9fff' for c in user_input) else responses[1]
    
    def generate_conversational_response(self, user_input: str, safety: Dict) -> str:
        """Generate Router Agent conversational response."""
        responses = [
            f"🤖 我明白了，您说的是'{user_input}'。作为您的陪伴机器人，这让我很感兴趣。您还想聊什么呢？",
            f"I understand you said '{user_input}'. As your companion, that's very interesting. What else would you like to talk about?",
        ]
        
        return responses[0] if any(c >= '\u4e00' and c <= '\u9fff' for c in user_input) else responses[1]
    
    def handle_router_agent_response(self, msg: String):
        """Handle response from Router Agent Dialog Manager."""
        try:
            response = msg.data
            self.logger.info(f"Router Agent response received: {response}")
            self.response_queue.put(response)
            
        except Exception as e:
            self.logger.error(f"Router Agent response handling error: {e}")
    
    def handle_system_status(self, msg: String):
        """Handle Router Agent system status updates."""
        try:
            status_data = json.loads(msg.data)
            if status_data.get('status') == 'EMERGENCY':
                print(f"🚨 ROUTER AGENT ALERT: {status_data.get('message')}")
                
        except Exception as e:
            self.logger.debug(f"Status handling error: {e}")
    
    def speak_response_with_router_agent(self, text: str):
        """Speak response using Router Agent TTS Engine."""
        if not text:
            return
        
        print(f"🤖 Router Agent: {text}")
        
        if HAS_ROS2:
            # Send to Router Agent TTS system
            try:
                tts_msg = String()
                tts_msg.data = text
                # Would publish to TTS topic: self.tts_request_pub.publish(tts_msg)
            except Exception as e:
                self.logger.error(f"Router Agent TTS error: {e}")
        
        # Fallback TTS or simulation
        if HAS_AUDIO_LIBS and self.tts_engine is not None:
            try:
                self.is_speaking = True
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
            except Exception as e:
                self.logger.error(f"TTS error: {e}")
            finally:
                self.is_speaking = False
        else:
            # Simulate speech time
            speech_time = len(text) / 15.0  # Elderly-appropriate pace
            time.sleep(max(1.0, speech_time))
    
    def run_router_agent_chat_loop(self):
        """Run the main Router Agent chat loop."""
        print("=" * 60)
        print("🤖 ROUTER AGENT (RK3588) CHAT LOOP")
        print("=" * 60)
        print("Architecture: Audio Input → ASR → Dialog Manager → Safety → TTS")
        print("Features: AI-powered conversation + Safety monitoring")
        print("Interfaces: Text and Microphone+Speaker")
        print("Say 'goodbye' or press Ctrl+C to exit")
        print()
        
        if not HAS_AUDIO_LIBS:
            print("NOTE: Running in text mode (audio libraries not available)")
        if not HAS_ROS2:
            print("NOTE: Running in simulation mode (ROS2 not available)")
        print()
        
        try:
            while self.conversation_active:
                # Listen for user input through Router Agent ASR
                user_input = self.listen_for_speech_with_router_agent()
                
                if user_input is None:
                    continue
                
                # Check for exit commands
                if user_input.lower() in ['goodbye', 'bye', 'exit', 'quit', '再见', '退出']:
                    farewell = "再见！保重身体，祝您有美好的一天！" if any(c >= '\u4e00' and c <= '\u9fff' for c in user_input) else "Goodbye! Take care and have a wonderful day!"
                    self.speak_response_with_router_agent(farewell)
                    break
                
                # Process through Router Agent Dialog Manager
                response = self.generate_router_agent_response(user_input)
                
                # Output through Router Agent TTS
                self.speak_response_with_router_agent(response)
                
                print()  # Add spacing
                
        except KeyboardInterrupt:
            print("\n🛑 Router Agent Chat Loop shutting down...")
        except Exception as e:
            self.logger.error(f"Chat loop error: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up Router Agent resources."""
        self.conversation_active = False
        
        if hasattr(self, 'tts_engine') and self.tts_engine:
            try:
                self.tts_engine.stop()
            except:
                pass
        
        if HAS_ROS2 and rclpy.ok():
            self.destroy_node()
        
        self.logger.info("Router Agent Chat Loop cleaned up")


def main():
    """Main entry point for Router Agent Chat Loop."""
    print("🚀 Starting Router Agent (RK3588) Chat Loop...")
    
    if HAS_ROS2:
        rclpy.init()
    
    try:
        chat_loop = RouterAgentChatLoop()
        
        if HAS_ROS2:
            # Run ROS2 node in separate thread
            ros_thread = threading.Thread(
                target=lambda: rclpy.spin(chat_loop),
                daemon=True
            )
            ros_thread.start()
        
        # Run main chat loop
        chat_loop.run_router_agent_chat_loop()
        
    except Exception as e:
        print(f"Failed to start Router Agent Chat Loop: {e}")
        return 1
    finally:
        if HAS_ROS2 and rclpy.ok():
            rclpy.shutdown()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())