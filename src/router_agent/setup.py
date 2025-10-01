from setuptools import setup
import os
from glob import glob

package_name = 'router_agent'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # Install launch files
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        # Install config files
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yml')),
        (os.path.join('share', package_name, 'config'), glob('config/*.json')),
        (os.path.join('share', package_name, 'config'), glob('config/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Router Agent Team',
    maintainer_email='dev@elderly-companion.com',
    description='Router Agent for Elderly Companion Robdog',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'fastapi_bridge_node = router_agent.fastapi_bridge_node:main',
            'enhanced_router_coordinator = router_agent.enhanced_router_coordinator:main',
            'silero_vad_node = router_agent.silero_vad_node:main',
            'enhanced_tts_engine_node = router_agent.enhanced_tts_engine_node:main',
            'smart_home_backend_node = router_agent.smart_home_backend_node:main',
            'webrtc_uplink_node = router_agent.webrtc_uplink_node:main',
            'guard_fastapi_bridge_node = router_agent.guard_fastapi_bridge_node:main',
            'sip_voip_adapter_node = router_agent.sip_voip_adapter_node:main',
            'enhanced_guard_engine = router_agent.enhanced_guard_engine:main',
            'speech_recognition_node = router_agent.speech_recognition_node:main',
            'emotion_analyzer_node = router_agent.emotion_analyzer_node:main',
            'dialog_manager_node = router_agent.dialog_manager_node:main',
            'safety_guard_node = router_agent.safety_guard_node:main',
            'tts_engine_node = router_agent.tts_engine_node:main',
            'mqtt_adapter_node = router_agent.mqtt_adapter_node:main',
            'audio_processor_node = router_agent.audio_processor_node:main',
            'router_agent_coordinator = router_agent.router_agent_coordinator:main',
            'guard_integration_node = router_agent.guard_integration_node:main',
        ],
    },
)