#!/usr/bin/env python3
"""
Enhanced Guard Standalone Demo - No ROS2 dependencies.
Demonstrates wakeword detection, SOS detection, geofencing, and implicit commands.
"""

import time
import json
import math
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass
from collections import deque

class WakewordType(Enum):
    PRIMARY = "primary"
    EMERGENCY = "emergency" 
    ATTENTION = "attention"

class SOSCategory(Enum):
    EXPLICIT = "explicit"
    MEDICAL = "medical"
    FALL = "fall"
    CONFUSION = "confusion"
    EMOTIONAL = "emotional"

class GeofenceStatus(Enum):
    SAFE = "safe"
    WARNING = "warning"
    VIOLATION = "violation"
    EMERGENCY = "emergency"

@dataclass
class MockEmotion:
    primary_emotion: str = "neutral"
    stress_level: float = 0.2
    arousal: float = 0.5
    valence: float = 0.0
    voice_quality_score: float = 0.8

@dataclass
class MockPoint:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

class EnhancedGuardStandalone:
    """Standalone Enhanced Guard demonstration."""
    
    def __init__(self):
        # Wakeword patterns
        self.wake_patterns = {
            WakewordType.PRIMARY: ['小伴', '机器人', 'companion', 'robot'],
            WakewordType.EMERGENCY: ['救命', '救我', 'help', 'emergency'],
            WakewordType.ATTENTION: ['听着', '注意', 'listen', 'attention']
        }
        
        # SOS patterns
        self.sos_patterns = {
            SOSCategory.EXPLICIT: ['救命', 'SOS', '求救', 'help', 'emergency'],
            SOSCategory.MEDICAL: ['心脏病', '中风', '呼吸困难', '胸痛', 'heart attack', 'stroke', 'chest pain'],
            SOSCategory.FALL: ['摔倒', '跌倒', '起不来', 'fallen', 'fell down', 'cant get up'],
            SOSCategory.CONFUSION: ['迷路', '不记得', '糊涂', 'lost', 'confused', 'dont remember'],
            SOSCategory.EMOTIONAL: ['害怕', '孤独', '绝望', 'scared', 'lonely', 'desperate']
        }
        
        # Implicit command patterns
        self.implicit_patterns = {
            'temperature_control': ['冷', '热', '温度', 'cold', 'hot', 'temperature'],
            'lighting_control': ['暗', '亮', '看不清', 'dark', 'bright', 'cant see'],
            'assistance_request': ['帮我', '不会', 'help me', 'dont know how'],
            'social_interaction': ['孤独', '无聊', '聊天', 'lonely', 'bored', 'talk']
        }
        
        # Safe zones
        self.safe_zones = {
            'bedroom': {'center': (2.5, 3.0), 'radius': 2.0},
            'living_room': {'center': (0.0, 0.0), 'radius': 3.5},
            'bathroom': {'center': (-1.5, 2.0), 'radius': 1.5},
            'kitchen': {'center': (1.0, -2.0), 'radius': 2.0}
        }
        
        # Conversation memory
        self.conversation_context = deque(maxlen=10)
    
    def detect_wakeword(self, text: str, emotion: MockEmotion) -> Dict[str, Any]:
        """Detect wakewords with elderly adaptation."""
        text_lower = text.lower()
        
        for wake_type, patterns in self.wake_patterns.items():
            for pattern in patterns:
                if pattern in text_lower:
                    # Calculate confidence with elderly adaptation
                    base_confidence = 0.8
                    
                    # Enhance for elderly speech
                    if emotion.voice_quality_score < 0.7:
                        base_confidence += 0.15  # Clarity compensation
                    
                    if emotion.stress_level > 0.6:
                        base_confidence += 0.1   # Stress boost
                    
                    return {
                        'detected': True,
                        'type': wake_type.value,
                        'confidence': min(base_confidence, 1.0),
                        'keyword': pattern,
                        'elderly_adapted': True
                    }
        
        return {'detected': False, 'confidence': 0.0}
    
    def detect_sos(self, text: str, emotion: MockEmotion) -> Optional[Dict[str, Any]]:
        """Detect SOS with multilingual support."""
        text_lower = text.lower()
        
        for category, patterns in self.sos_patterns.items():
            for pattern in patterns:
                if pattern in text_lower:
                    base_confidence = 0.7
                    
                    # Emotional enhancement
                    if emotion.stress_level > 0.7:
                        base_confidence += 0.2
                    
                    if emotion.primary_emotion in ['fear', 'pain', 'distress']:
                        base_confidence += 0.15
                    
                    # Calculate urgency
                    urgency = 1
                    if category in [SOSCategory.EXPLICIT, SOSCategory.MEDICAL]:
                        urgency = 4
                    elif category == SOSCategory.FALL:
                        urgency = 3
                    elif emotion.stress_level > 0.8:
                        urgency += 1
                    
                    return {
                        'detected': True,
                        'category': category.value,
                        'confidence': min(base_confidence, 1.0),
                        'keywords': [pattern],
                        'urgency_level': urgency
                    }
        
        return None
    
    def recognize_implicit_command(self, text: str, emotion: MockEmotion) -> Optional[Dict[str, Any]]:
        """Recognize implicit commands."""
        text_lower = text.lower()
        
        for command_type, patterns in self.implicit_patterns.items():
            matches = sum(1 for pattern in patterns if pattern in text_lower)
            
            if matches > 0:
                confidence = 0.4 + (matches * 0.3)
                
                # Context enhancement
                context_boost = self.analyze_conversation_context(command_type)
                confidence += context_boost
                
                # Emotional enhancement
                if command_type == 'social_interaction' and emotion.valence < -0.3:
                    confidence += 0.2
                
                if confidence > 0.6:
                    return {
                        'detected': True,
                        'command_type': command_type,
                        'confidence': min(confidence, 1.0),
                        'requires_confirmation': confidence < 0.8
                    }
        
        return None
    
    def monitor_geofence(self, location: MockPoint, behavior_context: str = "") -> Dict[str, Any]:
        """Monitor geofence with behavioral analysis."""
        # Find current zone
        current_zone = None
        for zone_name, zone_info in self.safe_zones.items():
            center = zone_info['center']
            radius = zone_info['radius']
            
            distance = math.sqrt((location.x - center[0])**2 + (location.y - center[1])**2)
            if distance <= radius:
                current_zone = zone_name
                break
        
        # Determine status
        if current_zone is None:
            status = GeofenceStatus.VIOLATION
            anomaly_score = 0.8
        else:
            # Mock behavioral analysis
            anomaly_score = 0.1 if 'normal' in behavior_context else 0.3
            
            if anomaly_score > 0.7:
                status = GeofenceStatus.EMERGENCY
            elif anomaly_score > 0.5:
                status = GeofenceStatus.WARNING
            else:
                status = GeofenceStatus.SAFE
        
        return {
            'status': status.value,
            'zone': current_zone or 'outside_safe_zones',
            'anomaly_score': anomaly_score,
            'location': f"({location.x:.1f}, {location.y:.1f})"
        }
    
    def analyze_conversation_context(self, command_type: str) -> float:
        """Analyze conversation context for pattern reinforcement."""
        if len(self.conversation_context) < 2:
            return 0.0
        
        # Simple context analysis
        recent_topics = [ctx.get('topic', '') for ctx in list(self.conversation_context)[-3:]]
        related_mentions = sum(1 for topic in recent_topics if command_type in topic)
        
        return 0.1 * related_mentions
    
    def process_input(self, text: str, emotion: MockEmotion, location: MockPoint) -> Dict[str, Any]:
        """Process input through all Guard components."""
        start_time = time.time()
        
        # Add to conversation context
        self.conversation_context.append({
            'text': text,
            'emotion': emotion.primary_emotion,
            'timestamp': datetime.now(),
            'topic': 'general'
        })
        
        # Run all detections
        wakeword = self.detect_wakeword(text, emotion)
        sos = self.detect_sos(text, emotion)
        implicit = self.recognize_implicit_command(text, emotion)
        geofence = self.monitor_geofence(location, 'normal')
        
        processing_time = (time.time() - start_time) * 1000  # ms
        
        return {
            'wakeword': wakeword,
            'sos': sos,
            'implicit': implicit,
            'geofence': geofence,
            'processing_time_ms': processing_time,
            'emergency_detected': sos is not None and sos.get('urgency_level', 0) >= 3
        }


def main():
    """Run Enhanced Guard standalone demonstration."""
    print("🔧 Enhanced Guard Standalone Demo")
    print("="*60)
    
    guard = EnhancedGuardStandalone()
    
    # Test cases
    test_cases = [
        {
            'text': '小伴，请帮我开灯',
            'emotion': MockEmotion(),
            'location': MockPoint(1.0, 1.0),
            'description': 'Primary wakeword + smart home request'
        },
        {
            'text': '救命！我摔倒了',
            'emotion': MockEmotion(primary_emotion='fear', stress_level=0.9, arousal=0.8, valence=-0.7),
            'location': MockPoint(2.5, 3.0),  # Bedroom
            'description': 'Emergency wakeword + fall SOS'
        },
        {
            'text': '听着，我觉得有点冷',
            'emotion': MockEmotion(primary_emotion='uncomfortable', stress_level=0.3),
            'location': MockPoint(0.0, 0.0),  # Living room
            'description': 'Attention wakeword + implicit temperature control'
        },
        {
            'text': '我心脏很疼，呼吸困难',
            'emotion': MockEmotion(primary_emotion='pain', stress_level=0.95, arousal=0.9, valence=-0.8),
            'location': MockPoint(1.5, 2.5),
            'description': 'Medical emergency SOS'
        },
        {
            'text': '我感觉很孤独，想和人聊天',
            'emotion': MockEmotion(primary_emotion='sad', stress_level=0.4, valence=-0.5),
            'location': MockPoint(0.5, 0.5),
            'description': 'Emotional distress + implicit social request'
        },
        {
            'text': '这里太暗了，看不清楚',
            'emotion': MockEmotion(primary_emotion='frustrated', stress_level=0.3),
            'location': MockPoint(-0.5, -0.5),  # Outside safe zone
            'description': 'Implicit lighting control + geofence concern'
        }
    ]
    
    print("🎯 ENHANCED GUARD SYSTEM DEMONSTRATION")
    print("="*60)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 Test Case {i}: {test_case['description']}")
        print(f"   Input: \"{test_case['text']}\"")
        print(f"   Location: ({test_case['location'].x:.1f}, {test_case['location'].y:.1f})")
        print(f"   Emotion: {test_case['emotion'].primary_emotion} (stress: {test_case['emotion'].stress_level:.1f})")
        
        # Process through Guard
        result = guard.process_input(test_case['text'], test_case['emotion'], test_case['location'])
        
        # Display results
        if result['wakeword']['detected']:
            ww = result['wakeword']
            print(f"   🎯 Wakeword: {ww['type']} - '{ww['keyword']}' (confidence: {ww['confidence']:.2f})")
        
        if result['sos']:
            sos = result['sos']
            print(f"   🚨 SOS: {sos['category']} - Level {sos['urgency_level']} (confidence: {sos['confidence']:.2f})")
        
        if result['implicit']:
            imp = result['implicit']
            print(f"   🧠 Implicit: {imp['command_type']} (confidence: {imp['confidence']:.2f})")
        
        gf = result['geofence']
        print(f"   🗺️  Geofence: {gf['status']} in {gf['zone']}")
        
        # Overall assessment
        if result['emergency_detected']:
            print(f"   🚨 EMERGENCY RESPONSE REQUIRED")
        
        response_time = result['processing_time_ms']
        print(f"   ⏱️  Response Time: {response_time:.1f}ms {'✅' if response_time < 200 else '⚠️'}")
        
        print("-" * 60)
        time.sleep(0.3)
    
    print("\n🎉 Enhanced Guard Demo Completed")
    print("="*60)
    print("Enhanced Guard Features:")
    print("✅ Wakeword Detection (Primary, Emergency, Attention)")
    print("✅ SOS Detection (5 categories, multilingual)")
    print("✅ Implicit Command Recognition (4 types)")
    print("✅ Geofence Monitoring (4 safe zones)")
    print("✅ Elderly Speech Adaptation")
    print("✅ <200ms Emergency Response")
    print("✅ Conversation Memory & Context")

if __name__ == '__main__':
    main()