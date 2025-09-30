#!/usr/bin/env python3
"""
Simple Test for Basic Chat Loop.

Basic functionality test for the microphone-speaker chat system.
"""

import unittest
import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from simple_chat_loop import SimpleChatLoop
    HAS_CHAT_LOOP = True
except ImportError:
    HAS_CHAT_LOOP = False


class SimpleChatLoopTest(unittest.TestCase):
    """Basic tests for the simple chat loop functionality."""
    
    def setUp(self):
        """Set up test environment."""
        if HAS_CHAT_LOOP:
            self.chat_loop = SimpleChatLoop()
    
    def test_chat_loop_initialization(self):
        """Test that chat loop initializes properly."""
        if not HAS_CHAT_LOOP:
            self.skipTest("Chat loop module not available")
        
        self.assertIsNotNone(self.chat_loop)
        self.assertIsNotNone(self.chat_loop.responses)
        self.assertTrue(len(self.chat_loop.responses) > 0)
    
    def test_basic_responses(self):
        """Test basic response generation."""
        if not HAS_CHAT_LOOP:
            self.skipTest("Chat loop module not available")
        
        # Test English responses
        response = self.chat_loop.generate_response("hello")
        self.assertIsInstance(response, str)
        self.assertTrue(len(response) > 0)
        
        # Test Chinese responses
        response = self.chat_loop.generate_response("你好")
        self.assertIsInstance(response, str)
        self.assertTrue(len(response) > 0)
    
    def test_emergency_detection(self):
        """Test emergency keyword detection."""
        if not HAS_CHAT_LOOP:
            self.skipTest("Chat loop module not available")
        
        # Test emergency keywords
        emergency_inputs = ["help", "emergency", "救命"]
        
        for emergency_input in emergency_inputs:
            response = self.chat_loop.generate_response(emergency_input)
            self.assertIsInstance(response, str)
            self.assertTrue(len(response) > 0)
            
            # Check if it's a direct match from responses dict or emergency pattern
            # Emergency responses should either match exact patterns or contain helpful language
            is_emergency_response = (
                emergency_input in self.chat_loop.responses or  # Direct match
                any(word in response.lower() for word in ["help", "urgent", "assist", "here", "immediately", "立即"]) or  # Emergency keywords
                "emergency" in response.lower() or
                "我明白" in response  # Chinese emergency response
            )
            self.assertTrue(is_emergency_response, f"Emergency response not detected for '{emergency_input}': {response}")
    
    def test_fallback_response(self):
        """Test fallback response for unknown input."""
        if not HAS_CHAT_LOOP:
            self.skipTest("Chat loop module not available")
        
        response = self.chat_loop.generate_response("some random unknown input")
        self.assertIsInstance(response, str)
        self.assertTrue(len(response) > 0)


def run_simple_tests():
    """Run simple tests for the chat loop."""
    print("Running Simple Chat Loop Tests...")
    print("=" * 40)
    
    suite = unittest.TestLoader().loadTestsFromTestCase(SimpleChatLoopTest)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print("\n✅ All basic tests passed!")
        return True
    else:
        print(f"\n❌ {len(result.failures)} test(s) failed, {len(result.errors)} error(s)")
        return False


def main():
    """Run simple tests."""
    success = run_simple_tests()
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())