#!/bin/bash
set -e

# Source ROS2 environment
source /opt/ros/humble/setup.bash
source /workspace/install/setup.bash

# Execute the command
exec "$@"
