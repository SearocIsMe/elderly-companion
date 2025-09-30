#!/usr/bin/env python3
"""
Rules-First Guard Engine - Industrial Implementation.

Based on the technical design:
- Picovoice/openWakeWord for KWS
- sherpa-onnx integration
- GeoFence/DeviceFence policy engine
- Multi-signal fusion for SOS detection
- Rules-first approach (not hardcoded patterns)
"""

import json
import numpy as np
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime
import logging
import re

# Industrial KWS imports
try:
    import pvporcupine
    PORCUPINE_AVAILABLE = True
except ImportError:
    PORCUPINE_AVAILABLE = False

try:
    import openwakeword
    OPENWAKEWORD_AVAILABLE = True
except ImportError:
    OPENWAKEWORD_AVAILABLE = False

# sherpa-onnx integration
try:
    import sherpa_onnx
    SHERPA_AVAILABLE = True
except ImportError:
    SHERPA_AVAILABLE = False


class GuardDecision(Enum):
    """Guard decision types."""
    ALLOW = "allow"
    DENY = "deny" 
    NEED_CONFIRM = "need_confirm"
    ESCALATE = "escalate"


@dataclass
class PolicyRule:
    """Policy rule definition."""
    rule_id: str
    rule_type: str  # 'device', 'geo', 'time', 'user', 'rate'
    conditions: Dict[str, Any]
    action: GuardDecision
    priority: int
    reason: str


@dataclass
class DeviceFence:
    """Device access control definition."""
    device_id: str
    device_type: str  # 'light', 'lock', 'camera', 'hvac'
    room: str
    risk_level: int  # 1=low, 4=critical
    allowed_actions: Set[str]
    require_confirm_actions: Set[str]
    time_restrictions: Optional[Dict[str, Any]]


@dataclass
class GeoFence:
    """Geographic fence definition."""
    fence_id: str
    room: str
    polygon_vertices: List[Tuple[float, float]]
    allowed_devices: Set[str]
    risk_level: int
    time_based_rules: Dict[str, Any]


@dataclass
class EventSummary:
    """Privacy-preserving event summary for audit."""
    timestamp: datetime
    event_type: str
    intent_category: str
    decision: GuardDecision
    risk_score: float
    location_zone: str
    device_accessed: Optional[str]
    confirmation_required: bool


class IndustrialKWSEngine:
    """Industrial Keyword Spotting using Picovoice/openWakeWord."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.kws_engine = None
        self.initialize_kws()
        
        # Custom wake words for elderly companion
        self.wake_words = {
            'primary': ['小伴', 'companion'],
            'emergency': ['救命', 'help'],  
            'attention': ['听着', 'listen']
        }
        
        # SOS keyword dictionary (multi-language)
        self.sos_patterns = self.load_sos_dictionary()
        
    def initialize_kws(self):
        """Initialize industrial KWS engine."""
        try:
            if PORCUPINE_AVAILABLE:
                # Picovoice Porcupine (commercial grade)
                self.kws_engine = self.initialize_porcupine()
                self.logger.info("✅ Picovoice Porcupine KWS initialized")
                
            elif OPENWAKEWORD_AVAILABLE:
                # openWakeWord (open source)
                self.kws_engine = self.initialize_openwakeword()
                self.logger.info("✅ openWakeWord KWS initialized")
                
            else:
                self.logger.warning("⚠️ No industrial KWS available, using pattern matching fallback")
                
        except Exception as e:
            self.logger.error(f"KWS initialization error: {e}")
    
    def initialize_porcupine(self):
        """Initialize Picovoice Porcupine."""
        try:
            # Load custom wake word models for elderly companion
            keyword_paths = [
                "models/小伴_zh_rpi_v2_1_0.ppn",  # Custom trained
                "models/companion_en_rpi_v2_1_0.ppn",
                "models/emergency_zh_en_v2_1_0.ppn"
            ]
            
            return pvporcupine.create(
                access_key="YOUR_PICOVOICE_ACCESS_KEY",  # Replace with actual key
                keyword_paths=keyword_paths,
                sensitivities=[0.7, 0.8, 0.9]  # Emergency more sensitive
            )
            
        except Exception as e:
            self.logger.error(f"Porcupine initialization error: {e}")
            return None
    
    def initialize_openwakeword(self):
        """Initialize openWakeWord."""
        try:
            # Load pre-trained models
            return openwakeword.Model(
                wakeword_models=[
                    "alexa_v0.1.onnx",  # Use as base, retrain for elderly
                    "hey_jarvis_v0.1.onnx"
                ],
                inference_framework='onnx'
            )
            
        except Exception as e:
            self.logger.error(f"openWakeWord initialization error: {e}")
            return None
    
    def load_sos_dictionary(self) -> Dict[str, Dict[str, Any]]:
        """Load structured SOS keyword dictionary."""
        return {
            'critical_medical': {
                'keywords': {
                    'zh': ['心脏病', '中风', '呼吸困难', '胸痛', '意识不清'],
                    'en': ['heart attack', 'stroke', 'cant breathe', 'chest pain', 'unconscious']
                },
                'urgency_level': 4,
                'auto_dispatch': True,
                'confirmation_bypass': True
            },
            'fall_incident': {
                'keywords': {
                    'zh': ['摔倒', '跌倒', '起不来', '腿断了'],
                    'en': ['fallen', 'fell down', 'cant get up', 'broken leg']
                },
                'urgency_level': 3,
                'auto_dispatch': False,
                'confirmation_required': True
            },
            'explicit_help': {
                'keywords': {
                    'zh': ['救命', 'SOS', '求救', '报警'],
                    'en': ['help', 'sos', 'emergency', 'call police']
                },
                'urgency_level': 4,
                'auto_dispatch': True,
                'confirmation_bypass': True
            },
            'confusion_distress': {
                'keywords': {
                    'zh': ['迷路', '不记得', '糊涂', '不知道在哪'],
                    'en': ['lost', 'confused', 'dont remember', 'where am i']
                },
                'urgency_level': 2,
                'auto_dispatch': False,
                'confirmation_required': True
            },
            'emotional_distress': {
                'keywords': {
                    'zh': ['害怕', '孤独', '绝望', '想死'],
                    'en': ['scared', 'lonely', 'desperate', 'want to die']
                },
                'urgency_level': 2,
                'auto_dispatch': False,
                'confirmation_required': True
            }
        }
    
    def detect_wake_word(self, audio_chunk: np.ndarray) -> Optional[Dict[str, Any]]:
        """Detect wake words using industrial KWS."""
        try:
            if self.kws_engine and hasattr(self.kws_engine, 'process'):
                # Porcupine detection
                keyword_index = self.kws_engine.process(audio_chunk)
                
                if keyword_index >= 0:
                    wake_types = ['primary', 'emergency', 'attention']
                    return {
                        'detected': True,
                        'type': wake_types[keyword_index] if keyword_index < len(wake_types) else 'unknown',
                        'confidence': 0.9,  # Porcupine provides binary detection
                        'timestamp': datetime.now(),
                        'industrial_kws': True
                    }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Industrial KWS detection error: {e}")
            return None
    
    def detect_sos_keywords(self, text: str, audio_features: Optional[Dict[str, float]] = None) -> Optional[Dict[str, Any]]:
        """Multi-signal SOS detection with prosodic analysis."""
        try:
            text_lower = text.lower()
            
            # Dictionary-based detection with confidence scoring
            for sos_type, sos_config in self.sos_patterns.items():
                for lang, keywords in sos_config['keywords'].items():
                    for keyword in keywords:
                        if keyword in text_lower:
                            # Base confidence from keyword match
                            confidence = 0.8
                            
                            # Enhance with prosodic features
                            if audio_features:
                                confidence = self.enhance_with_prosodic_analysis(
                                    confidence, audio_features, sos_type
                                )
                            
                            # Enhance with context patterns
                            confidence = self.enhance_with_context_patterns(
                                confidence, text, sos_type
                            )
                            
                            if confidence > 0.7:  # Threshold for SOS confirmation
                                return {
                                    'detected': True,
                                    'sos_type': sos_type,
                                    'matched_keyword': keyword,
                                    'language': lang,
                                    'confidence': min(confidence, 1.0),
                                    'urgency_level': sos_config['urgency_level'],
                                    'auto_dispatch': sos_config['auto_dispatch'],
                                    'confirmation_required': sos_config.get('confirmation_required', True),
                                    'timestamp': datetime.now()
                                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"SOS detection error: {e}")
            return None
    
    def enhance_with_prosodic_analysis(self, base_confidence: float, 
                                     audio_features: Dict[str, float], 
                                     sos_type: str) -> float:
        """Enhance SOS confidence with prosodic/energy analysis."""
        enhanced = base_confidence
        
        # Energy/RMS突变检测
        if audio_features.get('rms_energy', 0) > 0.8:
            enhanced += 0.1
        
        # 音高异常检测 (sudden pitch changes indicate distress)
        if audio_features.get('pitch_variance', 0) > 0.6:
            enhanced += 0.15
        
        # 语速异常检测
        speaking_rate = audio_features.get('speaking_rate', 1.0)
        if speaking_rate < 0.5 or speaking_rate > 2.0:  # Too slow or too fast
            enhanced += 0.1
        
        # 特定SOS类型的韵律特征
        if sos_type == 'critical_medical':
            # Medical emergencies often have weak/breathless speech
            if audio_features.get('breath_ratio', 0) > 0.7:
                enhanced += 0.2
        
        elif sos_type == 'fall_incident':
            # Falls often have sudden energy spikes followed by weakness
            if audio_features.get('energy_spike', False):
                enhanced += 0.15
        
        return enhanced
    
    def enhance_with_context_patterns(self, base_confidence: float, 
                                    text: str, sos_type: str) -> float:
        """Enhance with contextual patterns and urgency indicators."""
        enhanced = base_confidence
        
        # Urgency intensifiers
        urgency_patterns = ['快', '马上', '立刻', 'quickly', 'immediately', 'now', 'urgent']
        urgency_matches = sum(1 for pattern in urgency_patterns if pattern in text.lower())
        enhanced += urgency_matches * 0.05
        
        # Pain intensifiers
        pain_patterns = ['非常', '很', '太', '极度', 'very', 'extremely', 'so much', 'terrible']
        pain_matches = sum(1 for pattern in pain_patterns if pattern in text.lower())
        enhanced += pain_matches * 0.03
        
        # Location context
        location_patterns = ['这里', '房间', '卫生间', 'here', 'room', 'bathroom', 'bedroom']
        if any(pattern in text.lower() for pattern in location_patterns):
            enhanced += 0.05
        
        return enhanced


class PolicyEngine:
    """Rules-based policy engine for device and geographic fencing."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        
        # Load policy configurations
        self.device_fences = self.load_device_fences()
        self.geo_fences = self.load_geo_fences()
        self.policy_rules = self.load_policy_rules()
        
        # Rate limiting
        self.rate_limits = {
            'smart_home': {'max_per_minute': 30, 'current': 0, 'reset_time': datetime.now()},
            'emergency_call': {'max_per_hour': 5, 'current': 0, 'reset_time': datetime.now()},
            'assist_move': {'max_per_hour': 20, 'current': 0, 'reset_time': datetime.now()}
        }
    
    def load_device_fences(self) -> Dict[str, DeviceFence]:
        """Load device access control policies."""
        # In production, load from secure config file
        return {
            'living_room_light': DeviceFence(
                device_id='living_room_light',
                device_type='light',
                room='living_room',
                risk_level=1,
                allowed_actions={'on', 'off', 'dim'},
                require_confirm_actions=set(),
                time_restrictions=None
            ),
            'bedroom_light': DeviceFence(
                device_id='bedroom_light',
                device_type='light', 
                room='bedroom',
                risk_level=1,
                allowed_actions={'on', 'off', 'dim'},
                require_confirm_actions=set(),
                time_restrictions={'quiet_hours': {'start': '22:00', 'end': '07:00'}}
            ),
            'front_door_lock': DeviceFence(
                device_id='front_door_lock',
                device_type='lock',
                room='entrance',
                risk_level=4,
                allowed_actions={'status'},
                require_confirm_actions={'unlock', 'lock'},
                time_restrictions={'night_lockdown': {'start': '20:00', 'end': '08:00'}}
            ),
            'hvac_system': DeviceFence(
                device_id='hvac_system',
                device_type='hvac',
                room='全屋',
                risk_level=2,
                allowed_actions={'temperature_adjust', 'mode_change'},
                require_confirm_actions={'emergency_heat', 'emergency_cool'},
                time_restrictions=None
            )
        }
    
    def load_geo_fences(self) -> Dict[str, GeoFence]:
        """Load geographic fence policies."""
        return {
            'bedroom': GeoFence(
                fence_id='bedroom',
                room='bedroom',
                polygon_vertices=[(1.5, 2.0), (3.5, 2.0), (3.5, 4.0), (1.5, 4.0)],
                allowed_devices={'bedroom_light', 'bedroom_hvac', 'emergency_button'},
                risk_level=1,
                time_based_rules={'sleep_hours': {'enhanced_monitoring': True}}
            ),
            'living_room': GeoFence(
                fence_id='living_room', 
                room='living_room',
                polygon_vertices=[(-1.0, -1.0), (2.0, -1.0), (2.0, 2.0), (-1.0, 2.0)],
                allowed_devices={'living_room_light', 'tv', 'hvac_system'},
                risk_level=1,
                time_based_rules={}
            ),
            'bathroom': GeoFence(
                fence_id='bathroom',
                room='bathroom', 
                polygon_vertices=[(-2.5, 1.0), (-0.5, 1.0), (-0.5, 3.0), (-2.5, 3.0)],
                allowed_devices={'bathroom_light', 'emergency_button'},
                risk_level=3,  # Higher risk due to fall potential
                time_based_rules={'extended_stay_alert': {'threshold_minutes': 30}}
            ),
            'entrance': GeoFence(
                fence_id='entrance',
                room='entrance',
                polygon_vertices=[(-1.0, -2.0), (1.0, -2.0), (1.0, -1.0), (-1.0, -1.0)],
                allowed_devices={'front_door_lock', 'security_camera'},
                risk_level=4,  # Critical security zone
                time_based_rules={'night_restrictions': {'enhanced_security': True}}
            )
        }
    
    def load_policy_rules(self) -> List[PolicyRule]:
        """Load comprehensive policy rules."""
        return [
            # Emergency bypass rules
            PolicyRule(
                rule_id='emergency_bypass',
                rule_type='emergency',
                conditions={'sos_detected': True, 'urgency_level': '>=3'},
                action=GuardDecision.ALLOW,
                priority=10,
                reason='Emergency situation - safety protocols bypassed'
            ),
            
            # High-risk device controls
            PolicyRule(
                rule_id='door_lock_night_restriction',
                rule_type='device',
                conditions={'device_type': 'lock', 'time_range': '20:00-08:00'},
                action=GuardDecision.NEED_CONFIRM,
                priority=8,
                reason='Door lock access during night hours requires confirmation'
            ),
            
            # Geofence violations
            PolicyRule(
                rule_id='outside_safe_zones',
                rule_type='geo',
                conditions={'location': 'outside_fences', 'duration': '>5min'},
                action=GuardDecision.ESCALATE,
                priority=7,
                reason='Person outside safe zones for extended period'
            ),
            
            # Rate limiting
            PolicyRule(
                rule_id='smart_home_rate_limit',
                rule_type='rate',
                conditions={'intent_type': 'smart_home', 'rate': '>30/min'},
                action=GuardDecision.DENY,
                priority=6,
                reason='Smart home control rate limit exceeded'
            ),
            
            # Time-based restrictions
            PolicyRule(
                rule_id='quiet_hours_hvac',
                rule_type='time',
                conditions={'device_type': 'hvac', 'time_range': '22:00-07:00', 'action': 'noisy_operation'},
                action=GuardDecision.NEED_CONFIRM,
                priority=5,
                reason='HVAC operation during quiet hours'
            )
        ]
    
    def evaluate_intent(self, intent_json: Dict[str, Any], 
                       current_location: Optional[Tuple[float, float]] = None,
                       audio_features: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """Evaluate intent against all policy rules."""
        try:
            evaluation_result = {
                'decision': GuardDecision.ALLOW,
                'confidence': 1.0,
                'violated_rules': [],
                'required_confirmations': [],
                'alternative_suggestions': [],
                'risk_assessment': self.assess_risk(intent_json),
                'audit_summary': None
            }
            
            # Check emergency bypass first
            if self.is_emergency_situation(intent_json, audio_features):
                evaluation_result['decision'] = GuardDecision.ALLOW
                evaluation_result['reason'] = 'Emergency bypass activated'
                return evaluation_result
            
            # Apply policy rules in priority order
            applicable_rules = self.get_applicable_rules(intent_json, current_location)
            
            for rule in sorted(applicable_rules, key=lambda r: r.priority, reverse=True):
                if self.rule_matches(rule, intent_json, current_location):
                    if rule.action == GuardDecision.DENY:
                        evaluation_result['decision'] = GuardDecision.DENY
                        evaluation_result['violated_rules'].append(rule.rule_id)
                        evaluation_result['reason'] = rule.reason
                        break
                    
                    elif rule.action == GuardDecision.NEED_CONFIRM:
                        evaluation_result['decision'] = GuardDecision.NEED_CONFIRM
                        evaluation_result['required_confirmations'].append({
                            'rule_id': rule.rule_id,
                            'reason': rule.reason,
                            'confirm_prompt': self.generate_confirmation_prompt(rule, intent_json)
                        })
            
            # Rate limiting check
            rate_check = self.check_rate_limits(intent_json)
            if not rate_check['allowed']:
                evaluation_result['decision'] = GuardDecision.DENY
                evaluation_result['reason'] = rate_check['reason']
            
            # Generate audit summary
            evaluation_result['audit_summary'] = self.create_audit_summary(
                intent_json, evaluation_result, current_location
            )
            
            return evaluation_result
            
        except Exception as e:
            self.logger.error(f"Intent evaluation error: {e}")
            return {
                'decision': GuardDecision.DENY,
                'reason': f'Evaluation error: {str(e)}',
                'confidence': 0.0
            }
    
    def is_emergency_situation(self, intent_json: Dict[str, Any], 
                             audio_features: Optional[Dict[str, float]]) -> bool:
        """Check if current situation qualifies for emergency bypass."""
        intent_type = intent_json.get('intent', '')
        
        # Direct emergency intents
        if intent_type == 'call.emergency':
            return True
        
        # High stress audio indicators
        if audio_features:
            stress_indicators = [
                audio_features.get('rms_energy', 0) > 0.9,
                audio_features.get('pitch_variance', 0) > 0.8,
                audio_features.get('speaking_rate', 1.0) > 2.5  # Very fast speech
            ]
            return sum(stress_indicators) >= 2
        
        return False
    
    def get_applicable_rules(self, intent_json: Dict[str, Any], 
                           location: Optional[Tuple[float, float]]) -> List[PolicyRule]:
        """Get rules applicable to current intent and context."""
        applicable = []
        
        intent_type = intent_json.get('intent', '')
        device_id = intent_json.get('device', '')
        
        for rule in self.policy_rules:
            # Check rule type applicability
            if rule.rule_type == 'device':
                if 'device_type' in rule.conditions:
                    device_fence = self.device_fences.get(device_id)
                    if device_fence and device_fence.device_type == rule.conditions['device_type']:
                        applicable.append(rule)
                        
            elif rule.rule_type == 'geo':
                if location and self.is_location_relevant(location, rule):
                    applicable.append(rule)
                    
            elif rule.rule_type == 'rate':
                if rule.conditions.get('intent_type') in intent_type:
                    applicable.append(rule)
                    
            elif rule.rule_type == 'emergency':
                applicable.append(rule)  # Always check emergency rules
        
        return applicable
    
    def rule_matches(self, rule: PolicyRule, intent_json: Dict[str, Any], 
                    location: Optional[Tuple[float, float]]) -> bool:
        """Check if rule conditions match current situation."""
        conditions = rule.conditions
        
        # Time-based conditions
        if 'time_range' in conditions:
            if not self.is_time_in_range(conditions['time_range']):
                return False
        
        # Device-specific conditions
        if 'device_type' in conditions:
            device_id = intent_json.get('device', '')
            device_fence = self.device_fences.get(device_id)
            if not device_fence or device_fence.device_type != conditions['device_type']:
                return False
        
        # Action-specific conditions
        if 'action' in conditions:
            if intent_json.get('action', '') != conditions['action']:
                return False
        
        return True
    
    def check_rate_limits(self, intent_json: Dict[str, Any]) -> Dict[str, Any]:
        """Check rate limiting policies."""
        intent_type = intent_json.get('intent', '').split('.')[0]  # Get main category
        
        if intent_type in self.rate_limits:
            limit_config = self.rate_limits[intent_type]
            
            # Reset counter if time window passed
            now = datetime.now()
            if (now - limit_config['reset_time']).total_seconds() > 60:  # 1 minute window
                limit_config['current'] = 0
                limit_config['reset_time'] = now
            
            # Check limit
            if limit_config['current'] >= limit_config['max_per_minute']:
                return {
                    'allowed': False,
                    'reason': f'Rate limit exceeded for {intent_type}: {limit_config["max_per_minute"]}/min'
                }
            
            # Increment counter
            limit_config['current'] += 1
        
        return {'allowed': True}
    
    def is_time_in_range(self, time_range: str) -> bool:
        """Check if current time is in specified range."""
        try:
            start_time, end_time = time_range.split('-')
            current_time = datetime.now().strftime('%H:%M')
            
            # Simple time comparison (assumes same day)
            return start_time <= current_time <= end_time
            
        except Exception:
            return True  # Default to allow if time parsing fails
    
    def is_location_relevant(self, location: Tuple[float, float], rule: PolicyRule) -> bool:
        """Check if location is relevant to geographic rule."""
        x, y = location
        
        # Check if location is outside all safe zones
        if rule.conditions.get('location') == 'outside_fences':
            for fence in self.geo_fences.values():
                if self.point_in_polygon((x, y), fence.polygon_vertices):
                    return False  # Inside a fence, rule not applicable
            return True  # Outside all fences
        
        return False
    
    def point_in_polygon(self, point: Tuple[float, float], 
                        polygon: List[Tuple[float, float]]) -> bool:
        """Check if point is inside polygon using ray casting."""
        x, y = point
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    def assess_risk(self, intent_json: Dict[str, Any]) -> Dict[str, Any]:
        """Assess risk level of intent."""
        intent_type = intent_json.get('intent', '')
        device_id = intent_json.get('device', '')
        action = intent_json.get('action', '')
        
        risk_score = 0.0
        risk_factors = []
        
        # Device risk assessment
        if device_id in self.device_fences:
            device_fence = self.device_fences[device_id]
            risk_score += device_fence.risk_level * 0.25
            
            if action in device_fence.require_confirm_actions:
                risk_score += 0.3
                risk_factors.append(f'High-risk action: {action}')
        
        # Intent type risk
        intent_risks = {
            'call.emergency': 0.9,
            'assist.move': 0.6,
            'smart.home': 0.3,
            'media.play': 0.1
        }
        risk_score += intent_risks.get(intent_type, 0.2)
        
        return {
            'risk_score': min(risk_score, 1.0),
            'risk_level': 'critical' if risk_score > 0.8 else 
                         'high' if risk_score > 0.6 else
                         'medium' if risk_score > 0.4 else 'low',
            'risk_factors': risk_factors
        }
    
    def generate_confirmation_prompt(self, rule: PolicyRule, intent_json: Dict[str, Any]) -> str:
        """Generate confirmation prompt for user."""
        device = intent_json.get('device', 'device')
        action = intent_json.get('action', 'action')
        
        prompts = {
            'door_lock_night_restriction': f"晚间时段操作门锁 {device}，是否确认执行 {action}？",
            'quiet_hours_hvac': f"安静时段调节空调，可能影响休息，是否确认？",
            'high_risk_device': f"即将操作高风险设备 {device}，请确认是否继续？"
        }
        
        return prompts.get(rule.rule_id, f"是否确认执行：{action} {device}？")
    
    def create_audit_summary(self, intent_json: Dict[str, Any], 
                           evaluation: Dict[str, Any],
                           location: Optional[Tuple[float, float]]) -> EventSummary:
        """Create privacy-preserving audit summary."""
        return EventSummary(
            timestamp=datetime.now(),
            event_type=intent_json.get('intent', 'unknown'),
            intent_category=intent_json.get('intent', '').split('.')[0],
            decision=evaluation['decision'],
            risk_score=evaluation['risk_assessment']['risk_score'],
            location_zone=self.get_location_zone(location) if location else 'unknown',
            device_accessed=intent_json.get('device'),
            confirmation_required=evaluation['decision'] == GuardDecision.NEED_CONFIRM
        )
    
    def get_location_zone(self, location: Tuple[float, float]) -> str:
        """Get zone name for location."""
        for zone_name, fence in self.geo_fences.items():
            if self.point_in_polygon(location, fence.polygon_vertices):
                return zone_name
        return 'outside_safe_zones'


class RulesFirstGuard:
    """Rules-First Guard Engine - Industrial Implementation."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        
        # Initialize components
        self.kws_engine = IndustrialKWSEngine(logger)
        self.policy_engine = PolicyEngine(logger)
        
        # Processing statistics
        self.stats = {
            'total_processed': 0,
            'rules_matched': 0,
            'llm_bypassed': 0,
            'emergencies_detected': 0,
            'avg_response_time_ms': 0.0
        }
    
    def process_speech_input(self, text: str, audio_chunk: Optional[np.ndarray] = None,
                           location: Optional[Tuple[float, float]] = None,
                           audio_features: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """Process speech input through rules-first Guard pipeline."""
        start_time = datetime.now()
        
        try:
            result = {
                'timestamp': start_time.isoformat(),
                'input_text': text,
                'processing_path': [],
                'guard_decisions': [],
                'final_decision': GuardDecision.ALLOW,
                'requires_llm': False,
                'emergency_detected': False
            }
            
            # Step 1: Wake word detection (if audio available)
            if audio_chunk is not None:
                wake_result = self.kws_engine.detect_wake_word(audio_chunk)
                if wake_result:
                    result['processing_path'].append('industrial_kws')
                    result['wake_word'] = wake_result
            
            # Step 2: SOS detection (priority check)
            sos_result = self.kws_engine.detect_sos_keywords(text, audio_features)
            if sos_result:
                result['processing_path'].append('sos_detection')
                result['sos_detected'] = sos_result
                result['emergency_detected'] = sos_result['urgency_level'] >= 3
                
                if result['emergency_detected']:
                    result['final_decision'] = GuardDecision.ALLOW
                    result['emergency_bypass'] = True
                    self.stats['emergencies_detected'] += 1
                    return result
            
            # Step 3: Rules-based intent extraction
            rules_intent = self.extract_rules_based_intent(text)
            if rules_intent:
                result['processing_path'].append('rules_extraction')
                result['rules_intent'] = rules_intent
                result['requires_llm'] = False
                
                # Step 4: Policy evaluation for rules-based intent
                policy_eval = self.policy_engine.evaluate_intent(
                    rules_intent, location, audio_features
                )
                result['policy_evaluation'] = policy_eval
                result['final_decision'] = policy_eval['decision']
                self.stats['rules_matched'] += 1
                
            else:
                # Step 5: Requires LLM for complex intent parsing
                result['processing_path'].append('requires_llm')
                result['requires_llm'] = True
                result['llm_context'] = {
                    'text': text,
                    'location_zone': self.policy_engine.get_location_zone(location) if location else None,
                    'available_devices': list(self.policy_engine.device_fences.keys()),
                    'constraints': self.get_current_constraints()
                }
            
            # Update statistics
            self.stats['total_processed'] += 1
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            self.update_avg_response_time(processing_time)
            
            result['processing_time_ms'] = processing_time
            
            return result
            
        except Exception as e:
            self.logger.error(f"Speech processing error: {e}")
            return {
                'final_decision': GuardDecision.DENY,
                'reason': f'Processing error: {str(e)}',
                'emergency_detected': False
            }
    
    def extract_rules_based_intent(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract intent using rules/patterns (before LLM)."""
        text_lower = text.lower()
        
        # Smart home patterns
        smart_home_patterns = {
            'light_control': {
                'patterns': ['开灯', '关灯', '调亮', '调暗', 'turn on light', 'turn off light'],
                'extract_device': ['客厅', '卧室', '厨房', 'living room', 'bedroom', 'kitchen'],
                'extract_action': ['开', '关', '调亮', '调暗', 'on', 'off', 'dim', 'bright']
            },
            'hvac_control': {
                'patterns': ['开空调', '关空调', '调温度', 'turn on ac', 'adjust temperature'],
                'extract_device': ['空调', '暖气', 'hvac', 'air conditioner', 'heater'],
                'extract_action': ['开', '关', '调高', '调低', 'on', 'off', 'increase', 'decrease']
            }
        }
        
        for control_type, config in smart_home_patterns.items():
            for pattern in config['patterns']:
                if pattern in text_lower:
                    # Extract device and action
                    device = self.extract_device_from_text(text_lower, config['extract_device'])
                    action = self.extract_action_from_text(text_lower, config['extract_action'])
                    
                    return {
                        'intent': 'smart.home',
                        'device': device or f'{control_type.split("_")[0]}_default',
                        'action': action or 'toggle',
                        'room': self.extract_room_from_text(text_lower),
                        'confirm': False,
                        'extracted_by': 'rules_engine'
                    }
        
        # Emergency call patterns
        emergency_patterns = ['打电话', '叫救护车', '联系医生', 'call ambulance', 'call doctor', 'phone emergency']
        for pattern in emergency_patterns:
            if pattern in text_lower:
                callee = 'emergency_services'
                if '医生' in text or 'doctor' in text:
                    callee = 'doctor'
                elif '家人' in text or 'family' in text:
                    callee = 'family'
                
                return {
                    'intent': 'call.emergency',
                    'callee': callee,
                    'reason': 'user_request',
                    'confirm': True,
                    'extracted_by': 'rules_engine'
                }
        
        return None  # Requires LLM
    
    def extract_device_from_text(self, text: str, device_keywords: List[str]) -> Optional[str]:
        """Extract device from text using keyword matching."""
        for keyword in device_keywords:
            if keyword in text:
                # Map to actual device IDs
                device_mapping = {
                    '客厅': 'living_room_light',
                    '卧室': 'bedroom_light', 
                    '厨房': 'kitchen_light',
                    'living room': 'living_room_light',
                    'bedroom': 'bedroom_light',
                    'kitchen': 'kitchen_light',
                    '空调': 'hvac_system',
                    'hvac': 'hvac_system'
                }
                return device_mapping.get(keyword)
        return None
    
    def extract_action_from_text(self, text: str, action_keywords: List[str]) -> Optional[str]:
        """Extract action from text using keyword matching."""
        action_mapping = {
            '开': 'on', '关': 'off', '调亮': 'brighten', '调暗': 'dim',
            'on': 'on', 'off': 'off', 'dim': 'dim', 'bright': 'brighten',
            '调高': 'increase', '调低': 'decrease',
            'increase': 'increase', 'decrease': 'decrease'
        }
        
        for keyword in action_keywords:
            if keyword in text:
                return action_mapping.get(keyword, keyword)
        return None
    
    def extract_room_from_text(self, text: str) -> Optional[str]:
        """Extract room from text."""
        room_mapping = {
            '客厅': 'living_room', '卧室': 'bedroom', '厨房': 'kitchen', 
            '卫生间': 'bathroom', '书房': 'study',
            'living room': 'living_room', 'bedroom': 'bedroom', 
            'kitchen': 'kitchen', 'bathroom': 'bathroom'
        }
        
        for keyword, room in room_mapping.items():
            if keyword in text:
                return room
        return None
    
    def get_current_constraints(self) -> Dict[str, Any]:
        """Get current system constraints for LLM context."""
        return {
            'available_devices': list(self.policy_engine.device_fences.keys()),
            'safe_zones': list(self.policy_engine.geo_fences.keys()),
            'current_time': datetime.now().strftime('%H:%M'),
            'emergency_contacts': ['family', 'doctor', 'emergency_services'],
            'rate_limits': {k: v['max_per_minute'] for k, v in self.policy_engine.rate_limits.items()}
        }
    
    def update_avg_response_time(self, processing_time_ms: float):
        """Update average response time statistics."""
        if self.stats['total_processed'] == 0:
            self.stats['avg_response_time_ms'] = processing_time_ms
        else:
            # Running average
            total = self.stats['total_processed']
            current_avg = self.stats['avg_response_time_ms']
            self.stats['avg_response_time_ms'] = (current_avg * total + processing_time_ms) / (total + 1)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get Guard processing statistics."""
        return {
            **self.stats,
            'rules_efficiency': self.stats['rules_matched'] / max(self.stats['total_processed'], 1),
            'emergency_rate': self.stats['emergencies_detected'] / max(self.stats['total_processed'], 1),
            'llm_dependency': (self.stats['total_processed'] - self.stats['llm_bypassed']) / max(self.stats['total_processed'], 1)
        }