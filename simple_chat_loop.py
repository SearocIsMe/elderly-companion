#!/usr/bin/env python3
"""
Simple Microphone-Speaker Chat Loop for Elderly Companion.

A minimal implementation that:
1. Listens to microphone input
2. Performs basic speech recognition 
3. Generates simple responses
4. Plays responses through speaker

No ROS2, no complex dependencies - just basic chat functionality.
"""

import sys
import time
import threading
import queue
import logging
from typing import Optional, Dict, Any

# Basic audio processing
try:
    import sounddevice as sd
    import numpy as np
    import speech_recognition as sr
    import pyttsx3
    HAS_AUDIO_LIBS = True
except ImportError as e:
    print(f"Audio libraries not installed: {e}")
    print("To install: pip install sounddevice speechrecognition pyttsx3 pyaudio")
    HAS_AUDIO_LIBS = False


class SimpleChatLoop:
    """Simple microphone-speaker chat loop."""
    
    def __init__(self):
        """Initialize the chat system."""
        self.setup_logging()
        
        # Audio configuration
        self.sample_rate = 16000
        self.chunk_size = 1024
        self.channels = 1
        
        # State management
        self.is_listening = False
        self.is_speaking = False
        self.audio_queue = queue.Queue(maxsize=100)
        
        # Initialize audio systems
        if HAS_AUDIO_LIBS:
            self.setup_audio_systems()
        else:
            self.setup_fallback_systems()
        
        # Simple response patterns
        self.responses = {
            # English responses
            "hello": "Hello! How can I help you today?",
            "hi": "Hi there! Nice to meet you!",
            "how are you": "I'm doing well, thank you for asking! How are you?",
            "what is your name": "I'm your companion robot. You can call me Robo!",
            "help": "I'm here to help! What do you need assistance with?",
            "emergency": "I understand this is urgent. Let me help you right away!",
            "thank you": "You're very welcome! I'm happy to help.",
            "goodbye": "Goodbye! Take care and have a wonderful day!",
            
            # Chinese responses (basic)
            "你好": "你好！我今天能为您做些什么？",
            "早上好": "早上好！祝您有美好的一天！",
            "晚安": "晚安！祝您睡个好觉！",
            "谢谢": "不客气！我很高兴能帮助您。",
            "帮助": "我在这里帮助您！您需要什么帮助？",
            "救命": "我明白这很紧急。让我立即帮助您！",
        }
        
        self.logger.info("Simple Chat Loop initialized successfully")
    
    def setup_logging(self):
        """Setup logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_audio_systems(self):
        """Setup real audio systems."""
        try:
            # Speech recognition
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
            
            # Text-to-speech
            self.tts_engine = pyttsx3.init()
            self.tts_engine.setProperty('rate', 150)  # Slower speech for elderly
            self.tts_engine.setProperty('volume', 0.8)
            
            # Test microphone
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
            
            self.logger.info("Audio systems initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to setup audio systems: {e}")
            self.setup_fallback_systems()
    
    def setup_fallback_systems(self):
        """Setup fallback text-based systems for testing."""
        self.recognizer = None
        self.microphone = None
        self.tts_engine = None
        self.logger.warning("Using fallback text-based interface")
    
    def listen_for_speech(self) -> Optional[str]:
        """Listen for speech input and return recognized text."""
        if not HAS_AUDIO_LIBS or self.recognizer is None:
            # Fallback: get text input
            try:
                return input("You (type your message): ").strip()
            except (EOFError, KeyboardInterrupt):
                return None
        
        try:
            print("Listening... (speak now)")
            
            with self.microphone as source:
                # Listen for speech with timeout
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
            
            print("Processing speech...")
            
            # Try different recognition services
            try:
                # Try Google Speech Recognition (free)
                text = self.recognizer.recognize_google(audio, language='en-US')
                return text.lower().strip()
            except sr.UnknownValueError:
                try:
                    # Try with Chinese
                    text = self.recognizer.recognize_google(audio, language='zh-CN')
                    return text.strip()
                except sr.UnknownValueError:
                    print("Could not understand speech")
                    return None
            except sr.RequestError as e:
                print(f"Speech recognition service error: {e}")
                return None
                
        except sr.WaitTimeoutError:
            print("No speech detected")
            return None
        except Exception as e:
            self.logger.error(f"Speech recognition error: {e}")
            return None
    
    def generate_response(self, user_input: str) -> str:
        """Generate a simple response to user input."""
        if not user_input:
            return "I didn't catch that. Could you please repeat?"
        
        user_input_lower = user_input.lower().strip()
        
        # Check for exact matches first
        if user_input_lower in self.responses:
            return self.responses[user_input_lower]
        
        # Check for partial matches
        for key, response in self.responses.items():
            if key in user_input_lower:
                return response
        
        # Check for emergency keywords
        emergency_keywords = ['help', 'emergency', 'pain', 'hurt', 'fell', 'can\'t', '救命', '急救', '痛', '摔倒']
        if any(keyword in user_input_lower for keyword in emergency_keywords):
            return "I understand this might be urgent. I'm here to help you. Can you tell me more about what you need?"
        
        # Default response
        return f"I heard you say '{user_input}'. That's interesting! Tell me more about that."
    
    def speak_response(self, text: str):
        """Speak the response using text-to-speech."""
        if not text:
            return
        
        print(f"Robot: {text}")
        
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
            # Fallback: just print
            time.sleep(1)  # Simulate speaking time
    
    def run_chat_loop(self):
        """Run the main chat loop."""
        print("=" * 50)
        print("Simple Elderly Companion Chat Loop")
        print("=" * 50)
        print("Say 'goodbye' or press Ctrl+C to exit")
        print()
        
        if not HAS_AUDIO_LIBS:
            print("NOTE: Running in text mode (audio libraries not available)")
            print("Type your messages and press Enter")
            print()
        
        try:
            while True:
                # Listen for user input
                user_input = self.listen_for_speech()
                
                if user_input is None:
                    continue
                
                # Check for exit commands
                if user_input.lower() in ['goodbye', 'bye', 'exit', 'quit', '再见', '退出']:
                    self.speak_response("Goodbye! Take care!")
                    break
                
                # Generate and speak response
                response = self.generate_response(user_input)
                self.speak_response(response)
                
                print()  # Add spacing between interactions
                
        except KeyboardInterrupt:
            print("\nShutting down chat loop...")
        except Exception as e:
            self.logger.error(f"Chat loop error: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources."""
        if hasattr(self, 'tts_engine') and self.tts_engine:
            try:
                self.tts_engine.stop()
            except:
                pass
        
        self.logger.info("Chat loop cleaned up")


def main():
    """Main entry point."""
    print("Starting Simple Chat Loop...")
    
    try:
        chat_loop = SimpleChatLoop()
        chat_loop.run_chat_loop()
    except Exception as e:
        print(f"Failed to start chat loop: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())