#!/usr/bin/env python3
"""
Configuration Loader for Enhanced Elderly Companion System.

Provides dynamic configuration loading based on deployment target
with environment variable substitution and validation.
"""

import os
import yaml
import json
import logging
from typing import Dict, Any, Optional, Union
from pathlib import Path
import re
from dataclasses import dataclass
from enum import Enum


class DeploymentTarget(Enum):
    """Deployment target types."""
    DEVELOPMENT = "development"
    RK3588 = "rk3588"
    PRODUCTION = "production"


@dataclass
class ConfigValidationResult:
    """Configuration validation result."""
    is_valid: bool
    errors: list
    warnings: list
    missing_required_fields: list


class ConfigurationLoader:
    """
    Dynamic configuration loader for elderly companion system.
    
    Features:
    - Environment variable substitution
    - Deployment-specific configuration loading
    - Configuration validation and error reporting
    - Secure handling of sensitive data
    - Configuration merging and overrides
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.config_dir = Path(__file__).parent
        self.loaded_config: Optional[Dict[str, Any]] = None
        self.deployment_target: Optional[DeploymentTarget] = None
        
        # Required configuration fields for validation
        self.required_fields = {
            'system.deployment_target',
            'router_agent.mode',
            'fastapi.orchestrator_url',
            'safety.emergency_response_time_ms'
        }
        
        # Sensitive fields that should use environment variables in production
        self.sensitive_fields = {
            'communication.sip.password',
            'communication.sms.api_secret',
            'communication.email.password',
            'smart_home.homeassistant.token',
            'smart_home.mqtt.password'
        }
    
    def load_configuration(self, deployment_target: str = None, 
                          config_override_path: str = None) -> Dict[str, Any]:
        """
        Load configuration based on deployment target.
        
        Args:
            deployment_target: Target deployment (development, rk3588, production)
            config_override_path: Path to custom configuration file
            
        Returns:
            Loaded and validated configuration dictionary
        """
        try:
            # Determine deployment target
            target = deployment_target or os.getenv('DEPLOYMENT_TARGET', 'development')
            self.deployment_target = DeploymentTarget(target)
            
            self.logger.info(f"Loading configuration for deployment target: {target}")
            
            # Load base configuration
            base_config = self.load_base_configuration()
            
            # Load deployment-specific configuration
            deployment_config = self.load_deployment_specific_configuration(target)
            
            # Merge configurations
            merged_config = self.merge_configurations(base_config, deployment_config)
            
            # Load custom overrides if provided
            if config_override_path and os.path.exists(config_override_path):
                override_config = self.load_yaml_file(config_override_path)
                merged_config = self.merge_configurations(merged_config, override_config)
                self.logger.info(f"Applied configuration overrides from: {config_override_path}")
            
            # Substitute environment variables
            final_config = self.substitute_environment_variables(merged_config)
            
            # Validate configuration
            validation_result = self.validate_configuration(final_config)
            if not validation_result.is_valid:
                self.logger.error(f"Configuration validation failed: {validation_result.errors}")
                raise ValueError(f"Invalid configuration: {validation_result.errors}")
            
            if validation_result.warnings:
                for warning in validation_result.warnings:
                    self.logger.warning(f"Configuration warning: {warning}")
            
            self.loaded_config = final_config
            self.logger.info("Configuration loaded and validated successfully")
            
            return final_config
            
        except Exception as e:
            self.logger.error(f"Configuration loading failed: {e}")
            raise
    
    def load_base_configuration(self) -> Dict[str, Any]:
        """Load base configuration file."""
        base_config_path = self.config_dir / 'enhanced_system_config.yaml'
        
        if not base_config_path.exists():
            raise FileNotFoundError(f"Base configuration file not found: {base_config_path}")
        
        return self.load_yaml_file(str(base_config_path))
    
    def load_deployment_specific_configuration(self, target: str) -> Dict[str, Any]:
        """Load deployment-specific configuration."""
        config_files = {
            'development': 'enhanced_system_config.yaml',  # Use base for development
            'rk3588': 'rk3588_config.yaml',
            'production': 'production_config.yaml'
        }
        
        config_file = config_files.get(target, 'enhanced_system_config.yaml')
        config_path = self.config_dir / config_file
        
        if config_path.exists():
            self.logger.info(f"Loading deployment-specific config: {config_file}")
            return self.load_yaml_file(str(config_path))
        else:
            self.logger.warning(f"Deployment-specific config not found: {config_file}, using base")
            return {}
    
    def load_yaml_file(self, file_path: str) -> Dict[str, Any]:
        """Load YAML configuration file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                return config or {}
        except Exception as e:
            self.logger.error(f"Failed to load YAML file {file_path}: {e}")
            raise
    
    def merge_configurations(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two configuration dictionaries."""
        def deep_merge(base_dict: dict, override_dict: dict) -> dict:
            result = base_dict.copy()
            
            for key, value in override_dict.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            
            return result
        
        return deep_merge(base, override)
    
    def substitute_environment_variables(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Substitute environment variables in configuration values."""
        def substitute_value(value: Any) -> Any:
            if isinstance(value, str):
                # Look for ${VAR_NAME} patterns
                pattern = r'\$\{([^}]+)\}'
                matches = re.findall(pattern, value)
                
                for match in matches:
                    env_var = match
                    env_value = os.getenv(env_var)
                    
                    if env_value is not None:
                        value = value.replace(f'${{{env_var}}}', env_value)
                    else:
                        # Check if this is a sensitive field
                        if self.is_sensitive_field_path(value):
                            self.logger.warning(f"Environment variable {env_var} not set for sensitive field")
                        else:
                            self.logger.debug(f"Environment variable {env_var} not set, keeping placeholder")
                
                return value
            elif isinstance(value, dict):
                return {k: substitute_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [substitute_value(item) for item in value]
            else:
                return value
        
        return substitute_value(config)
    
    def is_sensitive_field_path(self, value: str) -> bool:
        """Check if a field path contains sensitive data."""
        return any(sensitive in value.lower() for sensitive in 
                  ['password', 'token', 'secret', 'key', 'credential'])
    
    def validate_configuration(self, config: Dict[str, Any]) -> ConfigValidationResult:
        """Validate loaded configuration."""
        errors = []
        warnings = []
        missing_required = []
        
        try:
            # Check required fields
            for field_path in self.required_fields:
                if not self.get_nested_value(config, field_path):
                    missing_required.append(field_path)
            
            # Validate deployment-specific requirements
            if self.deployment_target == DeploymentTarget.PRODUCTION:
                errors.extend(self.validate_production_config(config))
            elif self.deployment_target == DeploymentTarget.RK3588:
                warnings.extend(self.validate_rk3588_config(config))
            
            # Check for placeholder values in production
            if self.deployment_target == DeploymentTarget.PRODUCTION:
                placeholder_warnings = self.check_production_placeholders(config)
                warnings.extend(placeholder_warnings)
            
            # Validate network settings
            network_errors = self.validate_network_configuration(config)
            errors.extend(network_errors)
            
            is_valid = len(errors) == 0 and len(missing_required) == 0
            
            return ConfigValidationResult(
                is_valid=is_valid,
                errors=errors,
                warnings=warnings,
                missing_required_fields=missing_required
            )
            
        except Exception as e:
            return ConfigValidationResult(
                is_valid=False,
                errors=[f"Configuration validation error: {e}"],
                warnings=[],
                missing_required_fields=[]
            )
    
    def validate_production_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate production-specific configuration requirements."""
        errors = []
        
        # Check SSL configuration
        if config.get('video', {}).get('webrtc', {}).get('ssl_enabled'):
            ssl_cert = config.get('video', {}).get('webrtc', {}).get('ssl_cert_path')
            ssl_key = config.get('video', {}).get('webrtc', {}).get('ssl_key_path')
            
            if not ssl_cert or not ssl_key:
                errors.append("SSL enabled but certificate paths not configured")
        
        # Check emergency contacts
        contacts = config.get('emergency_contacts', {})
        if not contacts or len(contacts) < 2:
            errors.append("Insufficient emergency contacts configured for production")
        
        return errors
    
    def validate_rk3588_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate RK3588-specific configuration."""
        warnings = []
        
        # Check RKNPU usage
        if not config.get('audio', {}).get('asr', {}).get('use_rknpu'):
            warnings.append("RKNPU not enabled for RK3588 deployment - performance may be suboptimal")
        
        # Check resource limits
        max_memory = config.get('resources', {}).get('max_memory_mb', 0)
        if max_memory > 4096:
            warnings.append("Memory limit exceeds typical RK3588 available memory")
        
        return warnings
    
    def check_production_placeholders(self, config: Dict[str, Any]) -> List[str]:
        """Check for placeholder values in production configuration."""
        warnings = []
        
        def check_placeholders(obj: Any, path: str = ""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    check_placeholders(value, current_path)
            elif isinstance(obj, str):
                if (obj in ["", "CONFIGURE IN PRODUCTION", "CONFIGURE_ME"] or
                    obj.startswith("example.com") or 
                    obj.startswith("+1234567890")):
                    warnings.append(f"Placeholder value found at {path}: {obj}")
        
        check_placeholders(config)
        return warnings
    
    def validate_network_configuration(self, config: Dict[str, Any]) -> List[str]:
        """Validate network configuration."""
        errors = []
        
        # Validate URLs
        fastapi_config = config.get('fastapi', {})
        for service, url in fastapi_config.items():
            if service.endswith('_url') and url:
                if not (url.startswith('http://') or url.startswith('https://')):
                    errors.append(f"Invalid URL format for {service}: {url}")
        
        # Validate ports
        webrtc_port = config.get('video', {}).get('webrtc', {}).get('server_port')
        if webrtc_port and (webrtc_port < 1024 or webrtc_port > 65535):
            errors.append(f"Invalid WebRTC server port: {webrtc_port}")
        
        return errors
    
    def get_nested_value(self, config: Dict[str, Any], field_path: str) -> Any:
        """Get nested configuration value using dot notation."""
        try:
            keys = field_path.split('.')
            value = config
            
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return None
            
            return value
            
        except Exception:
            return None
    
    def get_config_value(self, field_path: str, default_value: Any = None) -> Any:
        """Get configuration value with default fallback."""
        if not self.loaded_config:
            raise RuntimeError("Configuration not loaded. Call load_configuration() first.")
        
        value = self.get_nested_value(self.loaded_config, field_path)
        return value if value is not None else default_value
    
    def get_fastapi_urls(self) -> Dict[str, str]:
        """Get FastAPI service URLs."""
        if not self.loaded_config:
            raise RuntimeError("Configuration not loaded")
        
        fastapi_config = self.loaded_config.get('fastapi', {})
        return {
            'orchestrator': fastapi_config.get('orchestrator_url', 'http://localhost:7010'),
            'guard': fastapi_config.get('guard_url', 'http://localhost:7002'),
            'intent': fastapi_config.get('intent_url', 'http://localhost:7001'),
            'adapters': fastapi_config.get('adapters_url', 'http://localhost:7003')
        }
    
    def get_emergency_contacts(self) -> Dict[str, Dict[str, Any]]:
        """Get emergency contacts configuration."""
        if not self.loaded_config:
            raise RuntimeError("Configuration not loaded")
        
        return self.loaded_config.get('emergency_contacts', {})
    
    def get_smart_devices(self) -> Dict[str, Dict[str, Any]]:
        """Get smart devices configuration."""
        if not self.loaded_config:
            raise RuntimeError("Configuration not loaded")
        
        return self.loaded_config.get('smart_devices', {})
    
    def get_scenes(self) -> Dict[str, Dict[str, Any]]:
        """Get scene configurations."""
        if not self.loaded_config:
            raise RuntimeError("Configuration not loaded")
        
        return self.loaded_config.get('scenes', {})
    
    def export_configuration(self, output_path: str, format: str = 'yaml') -> bool:
        """Export current configuration to file."""
        try:
            if not self.loaded_config:
                raise RuntimeError("No configuration loaded to export")
            
            if format.lower() == 'yaml':
                with open(output_path, 'w', encoding='utf-8') as file:
                    yaml.dump(self.loaded_config, file, default_flow_style=False, 
                             allow_unicode=True, indent=2)
            elif format.lower() == 'json':
                with open(output_path, 'w', encoding='utf-8') as file:
                    json.dump(self.loaded_config, file, indent=2, ensure_ascii=False)
            else:
                raise ValueError(f"Unsupported export format: {format}")
            
            self.logger.info(f"Configuration exported to: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration export failed: {e}")
            return False
    
    def create_ros2_parameters(self) -> Dict[str, Any]:
        """Create ROS2 parameter dictionary from loaded configuration."""
        try:
            if not self.loaded_config:
                raise RuntimeError("Configuration not loaded")
            
            # Flatten configuration for ROS2 parameters
            ros2_params = {}
            
            def flatten_dict(d: dict, parent_key: str = ''):
                for key, value in d.items():
                    new_key = f"{parent_key}.{key}" if parent_key else key
                    
                    if isinstance(value, dict):
                        flatten_dict(value, new_key)
                    elif isinstance(value, (str, int, float, bool)):
                        ros2_params[new_key] = value
                    elif isinstance(value, list):
                        # Convert lists to JSON strings for ROS2 compatibility
                        ros2_params[new_key] = json.dumps(value)
            
            flatten_dict(self.loaded_config)
            
            self.logger.debug(f"Created {len(ros2_params)} ROS2 parameters")
            return ros2_params
            
        except Exception as e:
            self.logger.error(f"ROS2 parameters creation failed: {e}")
            return {}
    
    def get_docker_compose_file(self) -> Optional[str]:
        """Get appropriate Docker compose file path."""
        try:
            if not self.loaded_config:
                return None
            
            fastapi_config = self.loaded_config.get('fastapi', {})
            
            if self.deployment_target == DeploymentTarget.RK3588:
                compose_file = fastapi_config.get('docker_compose_rk3588')
            elif self.deployment_target == DeploymentTarget.PRODUCTION:
                compose_file = fastapi_config.get('docker_compose_gpu')
            else:
                compose_file = fastapi_config.get('docker_compose_pc')
            
            if compose_file:
                # Convert relative path to absolute
                if not os.path.isabs(compose_file):
                    compose_file = os.path.join(self.config_dir, compose_file)
                
                if os.path.exists(compose_file):
                    return compose_file
                else:
                    self.logger.warning(f"Docker compose file not found: {compose_file}")
            
            return None
            
        except Exception as e:
            self.logger.error(f"Docker compose file resolution error: {e}")
            return None
    
    def validate_emergency_contacts(self, contacts: Dict[str, Any]) -> List[str]:
        """Validate emergency contacts configuration."""
        errors = []
        
        if not contacts:
            errors.append("No emergency contacts configured")
            return errors
        
        required_contact_fields = ['name', 'phone_number', 'relationship', 'priority']
        
        for contact_id, contact_info in contacts.items():
            for field in required_contact_fields:
                if field not in contact_info or not contact_info[field]:
                    errors.append(f"Emergency contact {contact_id} missing required field: {field}")
            
            # Validate phone number format (basic validation)
            phone = contact_info.get('phone_number', '')
            if phone and not (phone.startswith('+') or phone.isdigit() or phone == '911'):
                errors.append(f"Emergency contact {contact_id} has invalid phone number format: {phone}")
        
        return errors
    
    def create_deployment_summary(self) -> Dict[str, Any]:
        """Create deployment summary for logging and monitoring."""
        try:
            if not self.loaded_config:
                return {}
            
            summary = {
                'deployment_target': self.deployment_target.value if self.deployment_target else 'unknown',
                'system_mode': self.get_config_value('router_agent.mode', 'unknown'),
                'components_enabled': {
                    'audio_pipeline': self.get_config_value('audio.enable_microphone', False),
                    'safety_systems': self.get_config_value('safety.enable_enhanced_guard', False),
                    'emergency_services': self.get_config_value('communication.enable_sip_voip', False),
                    'smart_home': self.get_config_value('smart_home.enable_automation', False),
                    'video_streaming': self.get_config_value('video.enable_webrtc_streaming', False)
                },
                'fastapi_integration': self.get_config_value('fastapi.enable_auto_start', False),
                'emergency_contacts_count': len(self.get_emergency_contacts()),
                'smart_devices_count': len(self.get_smart_devices()),
                'scenes_count': len(self.get_scenes()),
                'configuration_loaded_at': datetime.now().isoformat()
            }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Deployment summary creation error: {e}")
            return {'error': str(e)}


# Global configuration loader instance
_config_loader: Optional[ConfigurationLoader] = None


def get_config_loader(logger: Optional[logging.Logger] = None) -> ConfigurationLoader:
    """Get global configuration loader instance."""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigurationLoader(logger)
    return _config_loader


def load_system_configuration(deployment_target: str = None, 
                             config_override_path: str = None,
                             logger: Optional[logging.Logger] = None) -> Dict[str, Any]:
    """
    Convenience function to load system configuration.
    
    Args:
        deployment_target: Target deployment (development, rk3588, production)
        config_override_path: Path to custom configuration file
        logger: Optional logger instance
        
    Returns:
        Loaded configuration dictionary
    """
    loader = get_config_loader(logger)
    return loader.load_configuration(deployment_target, config_override_path)


def get_ros2_parameters(deployment_target: str = None,
                       logger: Optional[logging.Logger] = None) -> Dict[str, Any]:
    """
    Get ROS2 parameters from configuration.
    
    Args:
        deployment_target: Target deployment
        logger: Optional logger instance
        
    Returns:
        ROS2 parameters dictionary
    """
    loader = get_config_loader(logger)
    
    if not loader.loaded_config:
        loader.load_configuration(deployment_target)
    
    return loader.create_ros2_parameters()


if __name__ == '__main__':
    # Test configuration loading
    import logging
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    try:
        # Test development configuration
        config = load_system_configuration('development', logger=logger)
        print("✅ Development configuration loaded successfully")
        
        # Test RK3588 configuration
        config = load_system_configuration('rk3588', logger=logger)
        print("✅ RK3588 configuration loaded successfully")
        
        # Test production configuration
        config = load_system_configuration('production', logger=logger)
        print("✅ Production configuration loaded successfully")
        
        # Print deployment summary
        loader = get_config_loader()
        summary = loader.create_deployment_summary()
        print(f"\n📊 Deployment Summary:")
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"❌ Configuration loading test failed: {e}")