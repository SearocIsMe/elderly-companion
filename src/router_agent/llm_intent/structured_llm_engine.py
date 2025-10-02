#!/usr/bin/env python3
"""
Structured LLM Engine for Dialog & Intent Parser.

Rules-first approach with structured JSON output:
- vLLM for cloud deployment (Qwen2.5-3B-Instruct)
- llama.cpp GGUF for RK3588 edge deployment
- Strict JSON Schema enforcement
- Guard-validated post-processing
"""

import json
import requests
import subprocess
import time
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import logging
import re

# vLLM cloud client
try:
    from openai import OpenAI  # vLLM compatible client
    OPENAI_CLIENT_AVAILABLE = True
except ImportError:
    OPENAI_CLIENT_AVAILABLE = False


class DeploymentMode(Enum):
    """LLM deployment modes."""
    CLOUD_VLLM = "cloud_vllm"        # Cloud vLLM server
    EDGE_LLAMACPP = "edge_llamacpp"  # RK3588 llama.cpp
    FALLBACK_RULES = "fallback_rules" # Pure rules fallback


@dataclass
class LLMConfig:
    """LLM configuration for different deployment modes."""
    deployment_mode: DeploymentMode
    model_name: str
    endpoint_url: str
    max_tokens: int
    temperature: float
    context_length: int
    quantization: Optional[str] = None


@dataclass
class IntentSchema:
    """Structured intent schema definition."""
    intent_type: str
    required_fields: List[str]
    optional_fields: List[str]
    field_constraints: Dict[str, Any]
    confirmation_required: bool


class StructuredLLMEngine:
    """Structured LLM Engine with rules-first approach."""
    
    def __init__(self, logger: logging.Logger, deployment_mode: DeploymentMode = DeploymentMode.CLOUD_VLLM):
        self.logger = logger
        self.deployment_mode = deployment_mode
        
        # LLM configurations
        self.llm_configs = {
            DeploymentMode.CLOUD_VLLM: LLMConfig(
                deployment_mode=DeploymentMode.CLOUD_VLLM,
                model_name="Qwen/Qwen2.5-3B-Instruct",
                endpoint_url="http://localhost:8000/v1",  # vLLM server
                max_tokens=256,
                temperature=0.1,
                context_length=2048
            ),
            DeploymentMode.EDGE_LLAMACPP: LLMConfig(
                deployment_mode=DeploymentMode.EDGE_LLAMACPP,
                model_name="qwen2.5-3b-instruct-q4_k_m.gguf",
                endpoint_url="http://localhost:8080/completion", # llama.cpp server
                max_tokens=256,
                temperature=0.1,
                context_length=1024,
                quantization="Q4_K_M"
            )
        }
        
        self.current_config = self.llm_configs[deployment_mode]
        
        # Intent schemas (JSON Schema enforcement)
        self.intent_schemas = self.initialize_intent_schemas()
        
        # System prompt templates
        self.system_prompts = self.initialize_system_prompts()
        
        # Initialize LLM client
        self.llm_client = self.initialize_llm_client()
        
        # Statistics
        self.stats = {
            'total_requests': 0,
            'successful_parses': 0,
            'schema_violations': 0,
            'avg_response_time_ms': 0.0,
            'fallback_to_rules': 0
        }
    
    def initialize_intent_schemas(self) -> Dict[str, IntentSchema]:
        """Initialize structured intent schemas."""
        return {
            'smart.home': IntentSchema(
                intent_type='smart.home',
                required_fields=['device', 'action'],
                optional_fields=['room', 'parameters', 'confirm'],
                field_constraints={
                    'device': ['living_room_light', 'bedroom_light', 'kitchen_light', 'hvac_system', 'front_door_lock'],
                    'action': ['on', 'off', 'dim', 'brighten', 'toggle', 'status', 'lock', 'unlock'],
                    'room': ['living_room', 'bedroom', 'kitchen', 'bathroom', 'entrance']
                },
                confirmation_required=False
            ),
            'call.emergency': IntentSchema(
                intent_type='call.emergency',
                required_fields=['callee', 'reason'],
                optional_fields=['urgency_level', 'location'],
                field_constraints={
                    'callee': ['120', 'family', 'doctor', 'caregiver', 'emergency_services'],
                    'reason': ['fall', 'chest_pain', 'breathing_difficulty', 'confusion', 'general_emergency'],
                    'urgency_level': [1, 2, 3, 4]
                },
                confirmation_required=True
            ),
            'assist.move': IntentSchema(
                intent_type='assist.move',
                required_fields=['target'],
                optional_fields=['speed', 'follow_distance', 'safety_mode'],
                field_constraints={
                    'target': ['kitchen', 'bedroom', 'bathroom', 'living_room', 'follow_user', 'return_base'],
                    'speed': ['slow', 'normal', 'fast'],
                    'follow_distance': [0.5, 1.0, 1.5, 2.0]
                },
                confirmation_required=True
            ),
            'media.play': IntentSchema(
                intent_type='media.play',
                required_fields=['content_type'],
                optional_fields=['mood', 'playlist', 'volume'],
                field_constraints={
                    'content_type': ['music', 'news', 'audiobook', 'radio'],
                    'mood': ['nostalgia', 'relaxing', 'upbeat', 'classical'],
                    'playlist': ['old_songs_60s', 'classical_chinese', 'nature_sounds']
                },
                confirmation_required=False
            ),
            'health.monitor': IntentSchema(
                intent_type='health.monitor',
                required_fields=['check_type'],
                optional_fields=['symptoms', 'severity'],
                field_constraints={
                    'check_type': ['medication_reminder', 'symptom_report', 'vitals_check', 'mood_check'],
                    'symptoms': ['pain', 'dizziness', 'fatigue', 'confusion', 'anxiety'],
                    'severity': [1, 2, 3, 4, 5]
                },
                confirmation_required=False
            )
        }
    
    def initialize_system_prompts(self) -> Dict[str, str]:
        """Initialize system prompts with constraints and schemas."""
        base_prompt = """你是老年陪伴机器人的意图解析系统。你必须将用户的自然语言输入转换为严格的JSON格式。
            可用的意图类型和格式：
            1. smart.home: {"intent": "smart.home", "device": "设备ID", "action": "动作", "room": "房间", "confirm": false}
            2. call.emergency: {"intent": "call.emergency", "callee": "联系人", "reason": "原因", "confirm": true}
            3. assist.move: {"intent": "assist.move", "target": "目标位置", "speed": "速度", "confirm": true}
            4. media.play: {"intent": "media.play", "content_type": "内容类型", "mood": "心情", "confirm": false}
            5. health.monitor: {"intent": "health.monitor", "check_type": "检查类型", "symptoms": "症状", "confirm": false}

            如果槽位信息不足，返回：{"need": "ask_clarification", "missing_fields": ["字段名"], "clarify_prompt": "请问..."}

            约束条件：
            {constraints}

            用户输入：{user_input}

            只返回JSON，不要其他文字："""

        return {
            'intent_parsing': base_prompt,
            'clarification': """根据缺失信息生成简短的澄清问题。用户输入：{user_input}，缺失字段：{missing_fields}。
                        
            只返回JSON：{"clarify_prompt": "请问您要操作哪个房间的灯？", "suggested_options": ["客厅", "卧室", "厨房"]}"""
        }
    
    def initialize_llm_client(self):
        """Initialize LLM client based on deployment mode."""
        try:
            if self.deployment_mode == DeploymentMode.CLOUD_VLLM:
                if OPENAI_CLIENT_AVAILABLE:
                    return OpenAI(
                        base_url=self.current_config.endpoint_url,
                        api_key="EMPTY"  # vLLM doesn't require real API key
                    )
                else:
                    self.logger.warning("OpenAI client not available, using requests fallback")
                    return None
                    
            elif self.deployment_mode == DeploymentMode.EDGE_LLAMACPP:
                # llama.cpp server - use requests
                return None
                
        except Exception as e:
            self.logger.error(f"LLM client initialization error: {e}")
            return None
    
    def parse_intent(self, text: str, guard_context: Dict[str, Any]) -> Dict[str, Any]:
        """Parse intent with structured JSON output."""
        start_time = time.time()
        
        try:
            # Prepare constraints from guard context
            constraints = self.prepare_constraints(guard_context)
            
            # Generate prompt
            prompt = self.system_prompts['intent_parsing'].format(
                constraints=json.dumps(constraints, ensure_ascii=False, indent=2),
                user_input=text
            )
            
            # Call LLM based on deployment mode
            if self.deployment_mode == DeploymentMode.CLOUD_VLLM:
                llm_response = self.call_vllm(prompt)
            elif self.deployment_mode == DeploymentMode.EDGE_LLAMACPP:
                llm_response = self.call_llamacpp(prompt)
            else:
                llm_response = None
            
            # Parse and validate JSON response
            if llm_response:
                parsed_intent = self.parse_and_validate_json(llm_response, text)
            else:
                # Fallback to rules-based extraction
                parsed_intent = self.fallback_rules_extraction(text, constraints)
                self.stats['fallback_to_rules'] += 1
            
            # Update statistics
            processing_time = (time.time() - start_time) * 1000
            self.update_statistics(processing_time, parsed_intent is not None)
            
            return {
                'intent': parsed_intent,
                'processing_time_ms': processing_time,
                'deployment_mode': self.deployment_mode.value,
                'constraints_applied': constraints,
                'requires_guard_validation': True
            }
            
        except Exception as e:
            self.logger.error(f"Intent parsing error: {e}")
            return {
                'intent': None,
                'error': str(e),
                'fallback_suggested': True
            }
    
    def call_vllm(self, prompt: str) -> Optional[str]:
        """Call vLLM server for intent parsing."""
        try:
            if self.llm_client:
                response = self.llm_client.chat.completions.create(
                    model=self.current_config.model_name,
                    messages=[
                        {"role": "system", "content": "你是专业的意图解析系统，只返回JSON格式。"},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=self.current_config.max_tokens,
                    temperature=self.current_config.temperature,
                    stop=["\n\n", "```", "---"]  # Stop sequences for JSON
                )
                
                return response.choices[0].message.content.strip()
            
            else:
                # Fallback to requests
                payload = {
                    "model": self.current_config.model_name,
                    "messages": [
                        {"role": "system", "content": "你是专业的意图解析系统，只返回JSON格式。"},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": self.current_config.max_tokens,
                    "temperature": self.current_config.temperature
                }
                
                response = requests.post(
                    f"{self.current_config.endpoint_url}/chat/completions",
                    json=payload,
                    timeout=5.0
                )
                
                if response.status_code == 200:
                    return response.json()['choices'][0]['message']['content'].strip()
                
        except Exception as e:
            self.logger.error(f"vLLM call error: {e}")
            
        return None
    
    def call_llamacpp(self, prompt: str) -> Optional[str]:
        """Call llama.cpp server for edge deployment."""
        try:
            payload = {
                "prompt": prompt,
                "max_tokens": self.current_config.max_tokens,
                "temperature": self.current_config.temperature,
                "stop": ["\n\n", "```", "---"]
            }
            
            response = requests.post(
                self.current_config.endpoint_url,
                json=payload,
                timeout=3.0  # Faster timeout for edge
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('content', '').strip()
                
        except Exception as e:
            self.logger.error(f"llama.cpp call error: {e}")
            
        return None
    
    def parse_and_validate_json(self, llm_response: str, original_text: str) -> Optional[Dict[str, Any]]:
        """Parse LLM response and validate against schemas."""
        try:
            # Extract JSON from response (handle markdown formatting)
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = llm_response
            
            # Parse JSON
            intent_json = json.loads(json_str)
            
            # Handle clarification requests
            if intent_json.get('need') == 'ask_clarification':
                return {
                    'need_clarification': True,
                    'missing_fields': intent_json.get('missing_fields', []),
                    'clarify_prompt': intent_json.get('clarify_prompt', '请提供更多信息'),
                    'original_text': original_text
                }
            
            # Validate against schema
            intent_type = intent_json.get('intent')
            if intent_type in self.intent_schemas:
                schema = self.intent_schemas[intent_type]
                validation_result = self.validate_against_schema(intent_json, schema)
                
                if validation_result['valid']:
                    self.stats['successful_parses'] += 1
                    return intent_json
                else:
                    self.logger.warning(f"Schema validation failed: {validation_result['errors']}")
                    self.stats['schema_violations'] += 1
            
            return None
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing error: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Intent validation error: {e}")
            return None
    
    def validate_against_schema(self, intent_json: Dict[str, Any], schema: IntentSchema) -> Dict[str, Any]:
        """Validate intent JSON against schema."""
        errors = []
        
        # Check required fields
        for field in schema.required_fields:
            if field not in intent_json:
                errors.append(f"Missing required field: {field}")
        
        # Check field constraints
        for field, value in intent_json.items():
            if field in schema.field_constraints:
                allowed_values = schema.field_constraints[field]
                if value not in allowed_values:
                    errors.append(f"Invalid value '{value}' for field '{field}'. Allowed: {allowed_values}")
        
        # Check confirmation requirement
        if schema.confirmation_required and not intent_json.get('confirm', False):
            intent_json['confirm'] = True
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'validated_intent': intent_json
        }
    
    def fallback_rules_extraction(self, text: str, constraints: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Fallback rules-based intent extraction when LLM fails."""
        text_lower = text.lower()
        
        # Smart home rules
        if any(word in text_lower for word in ['灯', '空调', '温度', 'light', 'temperature', 'hvac']):
            device = None
            action = None
            
            # Extract device
            if '客厅' in text_lower or 'living room' in text_lower:
                device = 'living_room_light'
            elif '卧室' in text_lower or 'bedroom' in text_lower:
                device = 'bedroom_light'
            elif '厨房' in text_lower or 'kitchen' in text_lower:
                device = 'kitchen_light'
            
            # Extract action
            if '开' in text_lower or 'turn on' in text_lower:
                action = 'on'
            elif '关' in text_lower or 'turn off' in text_lower:
                action = 'off'
            elif '调亮' in text_lower or 'brighten' in text_lower:
                action = 'brighten'
            
            if device and action:
                return {
                    'intent': 'smart.home',
                    'device': device,
                    'action': action,
                    'confirm': False,
                    'extracted_by': 'fallback_rules'
                }
        
        # Emergency call rules
        if any(word in text_lower for word in ['打电话', '叫救护车', '联系', 'call', 'phone', 'contact']):
            callee = 'emergency_services'
            
            if '医生' in text_lower or 'doctor' in text_lower:
                callee = 'doctor'
            elif '家人' in text_lower or 'family' in text_lower:
                callee = 'family'
            elif '120' in text_lower:
                callee = '120'
            
            return {
                'intent': 'call.emergency',
                'callee': callee,
                'reason': 'user_request',
                'confirm': True,
                'extracted_by': 'fallback_rules'
            }
        
        return None
    
    def prepare_constraints(self, guard_context: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare constraints from guard context for LLM."""
        return {
            'available_devices': guard_context.get('available_devices', []),
            'current_location_zone': guard_context.get('location_zone'),
            'time_of_day': datetime.now().strftime('%H:%M'),
            'emergency_detected': guard_context.get('emergency_detected', False),
            'rate_limits': guard_context.get('rate_limits', {}),
            'device_restrictions': guard_context.get('device_restrictions', {}),
            'confirmation_required_devices': ['front_door_lock', 'security_system']
        }
    
    def generate_clarification_question(self, intent_json: Dict[str, Any]) -> Dict[str, Any]:
        """Generate clarification question for incomplete intents."""
        try:
            missing_fields = intent_json.get('missing_fields', [])
            original_text = intent_json.get('original_text', '')
            
            clarification_templates = {
                'device': {
                    'question': '请问您要操作哪个设备？',
                    'options': ['客厅灯', '卧室灯', '厨房灯', '空调']
                },
                'room': {
                    'question': '请问是哪个房间？',
                    'options': ['客厅', '卧室', '厨房', '卫生间']
                },
                'action': {
                    'question': '请问要进行什么操作？',
                    'options': ['打开', '关闭', '调节']
                },
                'callee': {
                    'question': '请问要联系谁？',
                    'options': ['家人', '医生', '急救中心']
                }
            }
            
            # Generate specific clarification
            primary_missing = missing_fields[0] if missing_fields else 'device'
            template = clarification_templates.get(primary_missing, clarification_templates['device'])
            
            return {
                'clarify_prompt': template['question'],
                'suggested_options': template['options'],
                'missing_fields': missing_fields,
                'partial_intent': {k: v for k, v in intent_json.items() if k not in ['need', 'missing_fields']}
            }
            
        except Exception as e:
            self.logger.error(f"Clarification generation error: {e}")
            return {
                'clarify_prompt': '请再详细说明您的需求',
                'suggested_options': [],
                'missing_fields': missing_fields
            }
    
    def update_statistics(self, processing_time_ms: float, success: bool):
        """Update processing statistics."""
        self.stats['total_requests'] += 1
        
        if success:
            self.stats['successful_parses'] += 1
        
        # Update average response time
        if self.stats['total_requests'] == 1:
            self.stats['avg_response_time_ms'] = processing_time_ms
        else:
            total = self.stats['total_requests']
            current_avg = self.stats['avg_response_time_ms']
            self.stats['avg_response_time_ms'] = (current_avg * (total - 1) + processing_time_ms) / total
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get LLM engine performance statistics."""
        return {
            **self.stats,
            'deployment_mode': self.deployment_mode.value,
            'model_name': self.current_config.model_name,
            'success_rate': self.stats['successful_parses'] / max(self.stats['total_requests'], 1),
            'schema_compliance_rate': 1.0 - (self.stats['schema_violations'] / max(self.stats['total_requests'], 1)),
            'rules_fallback_rate': self.stats['fallback_to_rules'] / max(self.stats['total_requests'], 1)
        }


class CloudToEdgeMigrator:
    """Migrate LLM deployment from cloud to edge."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        
    def setup_vllm_server(self, model_name: str = "Qwen/Qwen2.5-3B-Instruct"):
        """Setup vLLM server for cloud deployment."""
        vllm_command = f"""
        python -m vllm.entrypoints.openai.api_server \\
            --model {model_name} \\
            --host 0.0.0.0 \\
            --port 8000 \\
            --max-model-len 2048 \\
            --dtype auto \\
            --gpu-memory-utilization 0.7
        """
        
        self.logger.info(f"vLLM server command: {vllm_command}")
        return vllm_command
    
    def setup_llamacpp_server(self, model_path: str = "models/qwen2.5-3b-instruct-q4_k_m.gguf"):
        """Setup llama.cpp server for RK3588 deployment."""
        llamacpp_command = f"""
        ./llama-server \\
            -m {model_path} \\
            -c 1024 \\
            --host 0.0.0.0 \\
            --port 8080 \\
            -ngl 0 \\
            --threads 4 \\
            --ctx-size 1024
        """
        
        self.logger.info(f"llama.cpp server command: {llamacpp_command}")
        return llamacpp_command
    
    def download_models_for_rk3588(self) -> List[str]:
        """Download and prepare models for RK3588 deployment."""
        models = [
            {
                'name': 'Qwen2.5-3B-Instruct-GGUF-Q4_K_M',
                'url': 'https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf',
                'size': '~2.0GB',
                'recommended': True
            },
            {
                'name': 'Phi-3-Mini-GGUF-Q4_K_M', 
                'url': 'https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf',
                'size': '~2.2GB',
                'recommended': False
            }
        ]
        
        download_commands = []
        for model in models:
            command = f"wget -O models/{model['name'].lower()}.gguf {model['url']}"
            download_commands.append(command)
            
        return download_commands


# Integration example
def create_guard_llm_pipeline(deployment_mode: DeploymentMode = DeploymentMode.CLOUD_VLLM):
    """Create complete Guard + LLM pipeline."""
    logger = logging.getLogger('guard_llm_pipeline')
    
    # Initialize components
    rules_guard = RulesFirstGuard(logger)
    llm_engine = StructuredLLMEngine(logger, deployment_mode)
    
    def process_speech_to_action(text: str, audio_chunk: Optional[bytes] = None,
                               location: Optional[Tuple[float, float]] = None) -> Dict[str, Any]:
        """Complete pipeline: Speech → Guard → LLM → Action."""
        
        # Step 1: Guard pre-processing
        guard_result = rules_guard.process_speech_input(text, audio_chunk, location)
        
        # Step 2: Emergency bypass check
        if guard_result.get('emergency_detected'):
            return {
                'action': 'emergency_response',
                'bypass_llm': True,
                'guard_decision': 'emergency_allow',
                'intent': guard_result.get('sos_detected', {})
            }
        
        # Step 3: Rules-based intent or LLM parsing
        if guard_result.get('requires_llm'):
            llm_result = llm_engine.parse_intent(text, guard_result.get('llm_context', {}))
            intent = llm_result.get('intent')
        else:
            intent = guard_result.get('rules_intent')
        
        # Step 4: Guard post-validation
        if intent:
            policy_result = rules_guard.policy_engine.evaluate_intent(intent, location)
            
            return {
                'action': 'execute' if policy_result['decision'] == GuardDecision.ALLOW else 'request_confirmation',
                'intent': intent,
                'guard_decision': policy_result['decision'].value,
                'confirmation_prompt': policy_result.get('required_confirmations'),
                'risk_assessment': policy_result.get('risk_assessment')
            }
        
        return {
            'action': 'clarification_needed',
            'clarify_prompt': '请重新描述您的需求'
        }
    
    return process_speech_to_action


# Import the rules engine
from .rules_engine import RulesFirstGuard