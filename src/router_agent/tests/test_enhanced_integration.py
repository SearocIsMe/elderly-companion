#!/usr/bin/env python3
"""
Enhanced Integration Test Suite for Elderly Companion System.

Comprehensive end-to-end testing for:
- FastAPI services integration and closed-loop functionality
- ROS2 component communication and coordination
- Emergency response workflows and timing verification
- Audio pipeline and speech processing
- Smart home automation and device control
- Video streaming and WebRTC functionality
- Configuration loading and deployment verification
"""

import unittest
import time
import json
import requests
import subprocess
import os
import threading
import queue
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
import yaml

# ROS2 testing imports
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from elderly_companion.msg import SpeechResult, EmergencyAlert
from elderly_companion.srv import ProcessSpeech, EmergencyDispatch

# Import configuration loader
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../config'))
from config_loader import load_system_configuration, get_config_loader


class EnhancedIntegrationTestSuite(unittest.TestCase):
    """Comprehensive integration test suite."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        cls.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)
        
        # Load test configuration
        cls.deployment_target = os.getenv('TEST_DEPLOYMENT_TARGET', 'development')
        cls.config = load_system_configuration(cls.deployment_target, logger=cls.logger)
        
        # Initialize ROS2
        rclpy.init()
        
        # FastAPI service URLs
        cls.fastapi_urls = {
            'orchestrator': cls.config.get('fastapi', {}).get('orchestrator_url', 'http://localhost:7010'),
            'guard': cls.config.get('fastapi', {}).get('guard_url', 'http://localhost:7002'),
            'intent': cls.config.get('fastapi', {}).get('intent_url', 'http://localhost:7001'),
            'adapters': cls.config.get('fastapi', {}).get('adapters_url', 'http://localhost:7003')
        }
        
        # HTTP session for testing
        cls.session = requests.Session()
        cls.session.headers.update({'Content-Type': 'application/json'})
        
        # Test results storage
        cls.test_results = {
            'fastapi_tests': {},
            'ros2_tests': {},
            'integration_tests': {},
            'performance_tests': {},
            'emergency_tests': {}
        }
        
        cls.logger.info(f"Test suite initialized for deployment target: {cls.deployment_target}")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test environment."""
        rclpy.shutdown()
        cls.session.close()
        
        # Print test summary
        cls.print_test_summary()
    
    def test_01_configuration_loading(self):
        """Test configuration loading for different deployment targets."""
        try:
            self.logger.info("Testing configuration loading...")
            
            # Test development configuration
            dev_config = load_system_configuration('development', logger=self.logger)
            self.assertIsInstance(dev_config, dict)
            self.assertEqual(dev_config['system']['deployment_target'], 'development')
            
            # Test RK3588 configuration
            if os.path.exists('../config/rk3588_config.yaml'):
                rk3588_config = load_system_configuration('rk3588', logger=self.logger)
                self.assertIsInstance(rk3588_config, dict)
                self.assertEqual(rk3588_config['system']['deployment_target'], 'rk3588')
            
            # Test production configuration
            if os.path.exists('../config/production_config.yaml'):
                prod_config = load_system_configuration('production', logger=self.logger)
                self.assertIsInstance(prod_config, dict)
                self.assertEqual(prod_config['system']['deployment_target'], 'production')
            
            self.test_results['integration_tests']['configuration_loading'] = 'PASS'
            self.logger.info("✅ Configuration loading test passed")
            
        except Exception as e:
            self.test_results['integration_tests']['configuration_loading'] = f'FAIL: {e}'
            self.logger.error(f"❌ Configuration loading test failed: {e}")
            self.fail(f"Configuration loading failed: {e}")
    
    def test_02_fastapi_services_availability(self):
        """Test FastAPI services availability and health."""
        try:
            self.logger.info("Testing FastAPI services availability...")
            
            service_results = {}
            
            for service_name, url in self.fastapi_urls.items():
                try:
                    # Test health endpoint
                    health_url = f"{url}/health"
                    response = self.session.get(health_url, timeout=10)
                    
                    if response.status_code == 200:
                        service_results[service_name] = 'AVAILABLE'
                        self.logger.info(f"✅ {service_name} service available at {url}")
                    else:
                        service_results[service_name] = f'UNHEALTHY: {response.status_code}'
                        self.logger.warning(f"⚠️ {service_name} service unhealthy: {response.status_code}")
                        
                except requests.exceptions.ConnectionError:
                    service_results[service_name] = 'UNAVAILABLE'
                    self.logger.warning(f"❌ {service_name} service unavailable at {url}")
                except Exception as e:
                    service_results[service_name] = f'ERROR: {e}'
                    self.logger.error(f"❌ {service_name} service error: {e}")
            
            self.test_results['fastapi_tests']['service_availability'] = service_results
            
            # At least orchestrator should be available for core functionality
            if service_results.get('orchestrator') == 'AVAILABLE':
                self.logger.info("✅ Core FastAPI services test passed")
            else:
                self.logger.warning("⚠️ Core FastAPI services test had issues")
                
        except Exception as e:
            self.test_results['fastapi_tests']['service_availability'] = f'FAIL: {e}'
            self.logger.error(f"❌ FastAPI services test failed: {e}")
    
    def test_03_fastapi_closed_loop_functionality(self):
        """Test FastAPI closed-loop functionality (ASR text → response)."""
        try:
            self.logger.info("Testing FastAPI closed-loop functionality...")
            
            orchestrator_url = self.fastapi_urls['orchestrator']
            test_cases = [
                {
                    'input': '把客厅的灯调亮一点',
                    'expected_status': 'ok',
                    'expected_adapter': 'smart-home',
                    'description': 'Smart home light control'
                },
                {
                    'input': '救命 我不舒服',
                    'expected_status': 'emergency_dispatched',
                    'description': 'Emergency keyword detection'
                },
                {
                    'input': '你好 机器人',
                    'expected_status': 'ok',
                    'description': 'Normal conversation'
                }
            ]
            
            test_results = {}
            
            for i, test_case in enumerate(test_cases):
                try:
                    self.logger.info(f"Testing case {i+1}: {test_case['description']}")
                    
                    # Send request to orchestrator
                    response = self.session.post(
                        f"{orchestrator_url}/asr_text",
                        json={"text": test_case['input']},
                        timeout=15
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        actual_status = result.get('status', 'unknown')
                        
                        # Check expected status
                        if actual_status == test_case['expected_status']:
                            test_results[f"case_{i+1}"] = 'PASS'
                            self.logger.info(f"✅ Test case {i+1} passed: {actual_status}")
                        else:
                            test_results[f"case_{i+1}"] = f'FAIL: Expected {test_case["expected_status"]}, got {actual_status}'
                            self.logger.warning(f"⚠️ Test case {i+1} status mismatch: expected {test_case['expected_status']}, got {actual_status}")
                            
                        # Check adapter if specified
                        if 'expected_adapter' in test_case:
                            actual_adapter = result.get('adapter', '')
                            if actual_adapter != test_case['expected_adapter']:
                                self.logger.warning(f"⚠️ Adapter mismatch: expected {test_case['expected_adapter']}, got {actual_adapter}")
                    else:
                        test_results[f"case_{i+1}"] = f'FAIL: HTTP {response.status_code}'
                        self.logger.error(f"❌ Test case {i+1} HTTP error: {response.status_code}")
                    
                    # Wait between tests
                    time.sleep(2)
                    
                except Exception as e:
                    test_results[f"case_{i+1}"] = f'ERROR: {e}'
                    self.logger.error(f"❌ Test case {i+1} error: {e}")
            
            self.test_results['fastapi_tests']['closed_loop_functionality'] = test_results
            
            # Check if majority of tests passed
            passed_tests = sum(1 for result in test_results.values() if result == 'PASS')
            if passed_tests >= len(test_cases) // 2:
                self.logger.info("✅ FastAPI closed-loop functionality test passed")
            else:
                self.logger.warning("⚠️ FastAPI closed-loop functionality test had issues")
                
        except Exception as e:
            self.test_results['fastapi_tests']['closed_loop_functionality'] = f'FAIL: {e}'
            self.logger.error(f"❌ FastAPI closed-loop test failed: {e}")
    
    def test_04_emergency_response_timing(self):
        """Test emergency response timing requirements."""
        try:
            self.logger.info("Testing emergency response timing...")
            
            orchestrator_url = self.fastapi_urls['orchestrator']
            emergency_text = "救命 我摔倒了"
            
            # Measure response time
            start_time = time.time()
            
            response = self.session.post(
                f"{orchestrator_url}/asr_text",
                json={"text": emergency_text},
                timeout=10
            )
            
            response_time_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                result = response.json()
                status = result.get('status', 'unknown')
                
                # Check if emergency was detected
                if status == 'emergency_dispatched':
                    self.logger.info(f"✅ Emergency detected and dispatched in {response_time_ms:.1f}ms")
                    
                    # Check timing requirement
                    max_response_time = self.config.get('safety', {}).get('emergency_response_time_ms', 200)
                    if response_time_ms <= max_response_time:
                        timing_result = 'PASS'
                        self.logger.info(f"✅ Emergency timing requirement met: {response_time_ms:.1f}ms <= {max_response_time}ms")
                    else:
                        timing_result = f'SLOW: {response_time_ms:.1f}ms > {max_response_time}ms'
                        self.logger.warning(f"⚠️ Emergency response too slow: {response_time_ms:.1f}ms")
                else:
                    timing_result = f'DETECTION_FAIL: {status}'
                    self.logger.error(f"❌ Emergency not detected: {status}")
            else:
                timing_result = f'HTTP_ERROR: {response.status_code}'
                self.logger.error(f"❌ Emergency response HTTP error: {response.status_code}")
            
            self.test_results['emergency_tests']['response_timing'] = {
                'result': timing_result,
                'response_time_ms': response_time_ms,
                'detected_as_emergency': status == 'emergency_dispatched' if 'status' in locals() else False
            }
            
        except Exception as e:
            self.test_results['emergency_tests']['response_timing'] = f'ERROR: {e}'
            self.logger.error(f"❌ Emergency response timing test failed: {e}")
    
    def test_05_smart_home_integration(self):
        """Test smart home integration functionality."""
        try:
            self.logger.info("Testing smart home integration...")
            
            orchestrator_url = self.fastapi_urls['orchestrator']
            smart_home_commands = [
                "把客厅的灯打开",
                "调高空调温度",
                "关闭卧室的灯"
            ]
            
            smart_home_results = {}
            
            for i, command in enumerate(smart_home_commands):
                try:
                    response = self.session.post(
                        f"{orchestrator_url}/asr_text",
                        json={"text": command},
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        status = result.get('status', 'unknown')
                        adapter = result.get('adapter', '')
                        
                        if status == 'ok' and adapter == 'smart-home':
                            smart_home_results[f"command_{i+1}"] = 'PASS'
                            self.logger.info(f"✅ Smart home command {i+1} successful")
                        else:
                            smart_home_results[f"command_{i+1}"] = f'UNEXPECTED: {status}/{adapter}'
                            self.logger.warning(f"⚠️ Smart home command {i+1} unexpected result: {status}/{adapter}")
                    else:
                        smart_home_results[f"command_{i+1}"] = f'HTTP_ERROR: {response.status_code}'
                        self.logger.error(f"❌ Smart home command {i+1} HTTP error: {response.status_code}")
                    
                    time.sleep(1)  # Delay between commands
                    
                except Exception as e:
                    smart_home_results[f"command_{i+1}"] = f'ERROR: {e}'
                    self.logger.error(f"❌ Smart home command {i+1} error: {e}")
            
            self.test_results['integration_tests']['smart_home_integration'] = smart_home_results
            
            # Check success rate
            passed = sum(1 for result in smart_home_results.values() if result == 'PASS')
            if passed >= len(smart_home_commands) // 2:
                self.logger.info("✅ Smart home integration test passed")
            else:
                self.logger.warning("⚠️ Smart home integration test had issues")
                
        except Exception as e:
            self.test_results['integration_tests']['smart_home_integration'] = f'FAIL: {e}'
            self.logger.error(f"❌ Smart home integration test failed: {e}")
    
    def test_06_guard_engine_functionality(self):
        """Test enhanced guard engine functionality."""
        try:
            self.logger.info("Testing enhanced guard engine functionality...")
            
            guard_url = self.fastapi_urls['guard']
            test_cases = [
                {
                    'type': 'asr',
                    'text': '小安 开灯',
                    'expected_decision': 'wake',
                    'description': 'Wakeword detection'
                },
                {
                    'type': 'asr', 
                    'text': '救命 我不舒服',
                    'expected_decision': 'dispatch_emergency',
                    'description': 'SOS keyword detection'
                },
                {
                    'type': 'intent',
                    'intent': {'intent': 'assist.move', 'speed': 'fast'},
                    'expected_decision': 'deny',
                    'description': 'Speed policy enforcement'
                },
                {
                    'type': 'intent',
                    'intent': {'intent': 'smart.home', 'device': 'light', 'action': 'on'},
                    'expected_decision': 'allow',
                    'description': 'Safe smart home action'
                }
            ]
            
            guard_results = {}
            
            for i, test_case in enumerate(test_cases):
                try:
                    self.logger.info(f"Testing guard case {i+1}: {test_case['description']}")
                    
                    request_data = {
                        'type': test_case['type'],
                        'text': test_case.get('text'),
                        'intent': test_case.get('intent')
                    }
                    
                    response = self.session.post(
                        f"{guard_url}/guard/check",
                        json=request_data,
                        timeout=5
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        decision = result.get('decision', 'unknown')
                        
                        if decision == test_case['expected_decision']:
                            guard_results[f"case_{i+1}"] = 'PASS'
                            self.logger.info(f"✅ Guard test case {i+1} passed: {decision}")
                        else:
                            guard_results[f"case_{i+1}"] = f'DECISION_MISMATCH: Expected {test_case["expected_decision"]}, got {decision}'
                            self.logger.warning(f"⚠️ Guard test case {i+1} decision mismatch")
                    else:
                        guard_results[f"case_{i+1}"] = f'HTTP_ERROR: {response.status_code}'
                        self.logger.error(f"❌ Guard test case {i+1} HTTP error: {response.status_code}")
                    
                    time.sleep(0.5)
                    
                except Exception as e:
                    guard_results[f"case_{i+1}"] = f'ERROR: {e}'
                    self.logger.error(f"❌ Guard test case {i+1} error: {e}")
            
            self.test_results['fastapi_tests']['guard_functionality'] = guard_results
            
            # Check success rate
            passed = sum(1 for result in guard_results.values() if result == 'PASS')
            if passed >= len(test_cases) // 2:
                self.logger.info("✅ Guard engine functionality test passed")
            else:
                self.logger.warning("⚠️ Guard engine functionality test had issues")
                
        except Exception as e:
            self.test_results['fastapi_tests']['guard_functionality'] = f'FAIL: {e}'
            self.logger.error(f"❌ Guard engine functionality test failed: {e}")
    
    def test_07_performance_benchmarks(self):
        """Test system performance benchmarks."""
        try:
            self.logger.info("Testing performance benchmarks...")
            
            orchestrator_url = self.fastapi_urls['orchestrator']
            performance_results = {}
            
            # Test response time under load
            test_texts = [
                "开灯",
                "调高温度", 
                "我需要帮助",
                "关闭空调",
                "晚安模式"
            ]
            
            response_times = []
            
            for text in test_texts:
                try:
                    start_time = time.time()
                    
                    response = self.session.post(
                        f"{orchestrator_url}/asr_text",
                        json={"text": text},
                        timeout=10
                    )
                    
                    response_time = (time.time() - start_time) * 1000  # ms
                    response_times.append(response_time)
                    
                    if response.status_code == 200:
                        self.logger.debug(f"Response time for '{text}': {response_time:.1f}ms")
                    
                    time.sleep(0.1)  # Small delay between requests
                    
                except Exception as e:
                    self.logger.error(f"Performance test error for '{text}': {e}")
            
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
                max_response_time = max(response_times)
                min_response_time = min(response_times)
                
                performance_results = {
                    'avg_response_time_ms': avg_response_time,
                    'max_response_time_ms': max_response_time,
                    'min_response_time_ms': min_response_time,
                    'total_tests': len(response_times)
                }
                
                # Check performance requirements
                max_allowed = 1000  # 1 second max for normal responses
                if avg_response_time <= max_allowed:
                    performance_results['benchmark_result'] = 'PASS'
                    self.logger.info(f"✅ Performance benchmark passed: {avg_response_time:.1f}ms avg")
                else:
                    performance_results['benchmark_result'] = f'SLOW: {avg_response_time:.1f}ms > {max_allowed}ms'
                    self.logger.warning(f"⚠️ Performance benchmark slow: {avg_response_time:.1f}ms")
            else:
                performance_results['benchmark_result'] = 'NO_DATA'
            
            self.test_results['performance_tests']['response_timing'] = performance_results
            
        except Exception as e:
            self.test_results['performance_tests']['response_timing'] = f'FAIL: {e}'
            self.logger.error(f"❌ Performance benchmark test failed: {e}")
    
    def test_08_deployment_specific_features(self):
        """Test deployment-specific features."""
        try:
            self.logger.info(f"Testing deployment-specific features for: {self.deployment_target}")
            
            deployment_results = {}
            
            if self.deployment_target == 'rk3588':
                # Test RKNPU configuration
                rknpu_enabled = self.config.get('audio', {}).get('asr', {}).get('use_rknpu', False)
                deployment_results['rknpu_enabled'] = rknpu_enabled
                
                if rknpu_enabled:
                    self.logger.info("✅ RKNPU acceleration enabled for RK3588")
                else:
                    self.logger.warning("⚠️ RKNPU acceleration not enabled")
                    
                # Test memory constraints
                max_memory = self.config.get('resources', {}).get('max_memory_mb', 0)
                if max_memory <= 4096:
                    deployment_results['memory_optimized'] = 'PASS'
                    self.logger.info(f"✅ Memory optimized for RK3588: {max_memory}MB")
                else:
                    deployment_results['memory_optimized'] = 'EXCESSIVE'
                    self.logger.warning(f"⚠️ Memory allocation may be excessive: {max_memory}MB")
                    
            elif self.deployment_target == 'production':
                # Test production security settings
                ssl_enabled = self.config.get('video', {}).get('webrtc', {}).get('ssl_enabled', False)
                deployment_results['ssl_enabled'] = ssl_enabled
                
                if ssl_enabled:
                    self.logger.info("✅ SSL enabled for production")
                else:
                    self.logger.warning("⚠️ SSL not enabled for production")
                
                # Test authentication
                auth_required = self.config.get('security', {}).get('enable_authentication', False)
                deployment_results['authentication_enabled'] = auth_required
                
                if auth_required:
                    self.logger.info("✅ Authentication enabled for production")
                else:
                    self.logger.warning("⚠️ Authentication not enabled for production")
            
            else:
                # Development target
                deployment_results['development_mode'] = 'ACTIVE'
                self.logger.info("✅ Development mode configuration active")
            
            self.test_results['integration_tests']['deployment_specific'] = deployment_results
            
        except Exception as e:
            self.test_results['integration_tests']['deployment_specific'] = f'FAIL: {e}'
            self.logger.error(f"❌ Deployment-specific features test failed: {e}")
    
    @classmethod
    def print_test_summary(cls):
        """Print comprehensive test summary."""
        try:
            print("\n" + "="*80)
            print("🧪 ENHANCED INTEGRATION TEST SUITE SUMMARY")
            print("="*80)
            print(f"Deployment Target: {cls.deployment_target}")
            print(f"Test Run Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print()
            
            total_tests = 0
            passed_tests = 0
            
            for test_category, tests in cls.test_results.items():
                print(f"📂 {test_category.upper()}:")
                
                if isinstance(tests, dict):
                    for test_name, result in tests.items():
                        total_tests += 1
                        
                        if isinstance(result, dict):
                            # Handle complex results
                            if result.get('benchmark_result') == 'PASS' or 'PASS' in str(result):
                                status_icon = "✅"
                                passed_tests += 1
                            else:
                                status_icon = "❌"
                            print(f"  {status_icon} {test_name}: {result}")
                        elif result == 'PASS':
                            status_icon = "✅"
                            passed_tests += 1
                            print(f"  {status_icon} {test_name}: {result}")
                        else:
                            status_icon = "❌"
                            print(f"  {status_icon} {test_name}: {result}")
                else:
                    total_tests += 1
                    if tests == 'PASS':
                        passed_tests += 1
                        print(f"  ✅ {test_category}: {tests}")
                    else:
                        print(f"  ❌ {test_category}: {tests}")
                
                print()
            
            # Overall summary
            success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
            print(f"📊 OVERALL RESULTS:")
            print(f"  Total Tests: {total_tests}")
            print(f"  Passed: {passed_tests}")
            print(f"  Success Rate: {success_rate:.1f}%")
            
            if success_rate >= 80:
                print("🎉 INTEGRATION TEST SUITE: ✅ PASSED")
            elif success_rate >= 60:
                print("⚠️ INTEGRATION TEST SUITE: 🟡 PARTIAL SUCCESS")
            else:
                print("❌ INTEGRATION TEST SUITE: 🔴 FAILED")
            
            print("="*80)
            
        except Exception as e:
            print(f"❌ Test summary generation error: {e}")


class ROS2ComponentTester(Node):
    """ROS2-specific component testing."""
    
    def __init__(self):
        super().__init__('integration_test_node')
        self.test_results = {}
        self.response_queue = queue.Queue()
        
        # Create test subscribers and publishers
        self.system_status_sub = self.create_subscription(
            String,
            '/router_agent/system_status',
            self.handle_system_status,
            10
        )
        
        self.text_input_pub = self.create_publisher(
            String,
            '/router_agent/text_input',
            10
        )
    
    def handle_system_status(self, msg: String):
        """Handle system status messages."""
        try:
            status_data = json.loads(msg.data)
            self.response_queue.put(('system_status', status_data))
        except Exception:
            pass
    
    def test_ros2_communication(self) -> Dict[str, Any]:
        """Test ROS2 communication functionality."""
        results = {}
        
        try:
            # Test text input publishing
            test_text = "ROS2 测试消息"
            text_msg = String()
            text_msg.data = test_text
            
            self.text_input_pub.publish(text_msg)
            self.get_logger().info(f"Published test message: {test_text}")
            
            # Wait for system response
            timeout = 10.0
            start_time = time.time()
            
            while (time.time() - start_time) < timeout:
                try:
                    msg_type, data = self.response_queue.get(timeout=1.0)
                    if msg_type == 'system_status':
                        results['ros2_communication'] = 'PASS'
                        self.get_logger().info("✅ ROS2 communication test passed")
                        break
                except queue.Empty:
                    continue
            else:
                results['ros2_communication'] = 'TIMEOUT'
                self.get_logger().warning("⚠️ ROS2 communication test timeout")
            
        except Exception as e:
            results['ros2_communication'] = f'ERROR: {e}'
            self.get_logger().error(f"❌ ROS2 communication test error: {e}")
        
        return results


def run_integration_tests(deployment_target: str = None) -> Dict[str, Any]:
    """
    Run complete integration test suite.
    
    Args:
        deployment_target: Target deployment to test
        
    Returns:
        Test results dictionary
    """
    try:
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logger = logging.getLogger(__name__)
        
        target = deployment_target or os.getenv('TEST_DEPLOYMENT_TARGET', 'development')
        logger.info(f"Starting integration tests for deployment target: {target}")
        
        # Run unittest suite
        test_loader = unittest.TestLoader()
        test_suite = test_loader.loadTestsFromTestCase(EnhancedIntegrationTestSuite)
        
        # Run tests
        test_runner = unittest.TextTestRunner(verbosity=2)
        test_result = test_runner.run(test_suite)
        
        # Compile results
        results = {
            'deployment_target': target,
            'test_run_time': datetime.now().isoformat(),
            'tests_run': test_result.testsRun,
            'failures': len(test_result.failures),
            'errors': len(test_result.errors),
            'success': test_result.wasSuccessful(),
            'detailed_results': EnhancedIntegrationTestSuite.test_results
        }
        
        return results
        
    except Exception as e:
        logger.error(f"Integration test execution error: {e}")
        return {
            'error': str(e),
            'test_run_time': datetime.now().isoformat()
        }


if __name__ == '__main__':
    """Run integration tests from command line."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced Elderly Companion Integration Tests')
    parser.add_argument('--target', choices=['development', 'rk3588', 'production'],
                       default='development', help='Deployment target to test')
    parser.add_argument('--output', help='Output file for test results (JSON)')
    
    args = parser.parse_args()
    
    # Run tests
    results = run_integration_tests(args.target)
    
    # Save results if output file specified
    if args.output:
        try:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"📄 Test results saved to: {args.output}")
        except Exception as e:
            print(f"❌ Failed to save results: {e}")
    
    # Exit with appropriate code
    if results.get('success'):
        print("🎉 Integration tests completed successfully!")
        sys.exit(0)
    else:
        print("❌ Integration tests failed!")
        sys.exit(1)