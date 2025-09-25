cmake_minimum_required(VERSION 3.10)
project(router_agent)

# Default to C++17
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclpy REQUIRED)
find_package(std_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)

# Install Python modules
ament_python_install_package(${PROJECT_NAME})

# Install Python executables
install(PROGRAMS
  nodes/audio_processor_node.py
  nodes/speech_recognition_node.py
  nodes/emotion_analyzer_node.py
  nodes/safety_guard_node.py
  nodes/dialog_manager_node.py
  nodes/mqtt_adapter_node.py
  nodes/sip_voip_adapter_node.py
  DESTINATION lib/${PROJECT_NAME}
)

# Install launch files
install(DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch
  FILES_MATCHING PATTERN "*.launch.py"
)

# Install config files
install(DIRECTORY config/
  DESTINATION share/${PROJECT_NAME}/config
  FILES_MATCHING PATTERN "*.yaml" PATTERN "*.yml" PATTERN "*.json"
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_cmake_pytest REQUIRED)
  
  # Linting
  ament_lint_auto_find_test_dependencies()
  
  # Python tests (commented out until test files are created)
  # ament_add_pytest_test(test_audio_processor test/test_audio_processor.py)
  # ament_add_pytest_test(test_speech_recognition test/test_speech_recognition.py)
  # ament_add_pytest_test(test_emotion_analyzer test/test_emotion_analyzer.py)
endif()

ament_package()