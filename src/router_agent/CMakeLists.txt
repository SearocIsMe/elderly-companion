# This CMakeLists.txt is DISABLED to avoid package conflicts
# All router_agent functionality is now built through the main elderly_companion package
# See ../CMakeLists.txt for the complete build configuration

cmake_minimum_required(VERSION 3.10)
project(router_agent_disabled)

# This package is intentionally disabled
# All nodes and resources are installed via the elderly_companion package
message(STATUS "router_agent package disabled - using elderly_companion package")

# Minimal package to satisfy colcon
find_package(ament_cmake REQUIRED)
ament_package()