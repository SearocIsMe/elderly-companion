cmake_minimum_required(VERSION 3.8)
project(elderly_companion)

# Default to C++17
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclpy REQUIRED)
find_package(std_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(action_msgs REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(rosidl_default_generators REQUIRED)

# Generate custom messages and services
set(msg_files
  "msg/SpeechResult.msg"
  "msg/EmotionData.msg"
  "msg/IntentResult.msg"
  "msg/HealthStatus.msg"
  "msg/EmergencyAlert.msg"
  "msg/SafetyConstraints.msg"
)

set(srv_files
  "srv/ValidateIntent.srv"
  "srv/EmergencyDispatch.srv"
  "srv/ProcessSpeech.srv"
  "srv/ExecuteAction.srv"
)

set(action_files
  "action/FollowPerson.action"
  "action/GoToLocation.action"
  "action/EmergencyResponse.action"
)

rosidl_generate_interfaces(${PROJECT_NAME}
  ${msg_files}
  ${srv_files}
  ${action_files}
  DEPENDENCIES builtin_interfaces std_msgs sensor_msgs geometry_msgs nav_msgs action_msgs
)

# Install Python modules
ament_python_install_package(${PROJECT_NAME})

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

# Install scripts
install(PROGRAMS
  scripts/setup_dev_env.sh
  scripts/build_workspace.sh
  DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_cmake_gtest REQUIRED)
  find_package(ament_cmake_pytest REQUIRED)
  
  # Linting
  ament_lint_auto_find_test_dependencies()
  
  # C++ tests
  ament_add_gtest(test_safety_guard test/test_safety_guard.cpp)
  if(TARGET test_safety_guard)
    target_link_libraries(test_safety_guard ${PROJECT_NAME})
  endif()
  
  # Python tests
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_router_agent test/test_router_agent.py)
endif()

ament_export_dependencies(rosidl_default_runtime)
ament_package()