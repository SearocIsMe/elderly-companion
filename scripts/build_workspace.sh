#!/bin/bash

# Elderly Companion Robdog - Workspace Build Script
# Builds the complete ROS2 workspace with all packages

set -e

echo "🔨 Building Elderly Companion Robdog Workspace"
echo "==============================================="

# Source ROS2 environment
source /opt/ros/humble/setup.bash

# Check if we're in the right directory
if [ ! -f "package.xml" ] && [ ! -d "src" ]; then
    echo "❌ Error: Not in a ROS2 workspace root directory"
    echo "Please run this script from the project root"
    exit 1
fi

# Install dependencies
echo "📦 Installing ROS2 dependencies..."
rosdep update
rosdep install --from-paths src --ignore-src -r -y

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf build/ install/ log/

# Build the workspace
echo "🔨 Building ROS2 packages..."
colcon build \
    --cmake-args -DCMAKE_BUILD_TYPE=Release \
    --parallel-workers $(nproc) \
    --event-handlers console_direct+

# Source the workspace
echo "✅ Build complete! Sourcing workspace..."
source install/setup.bash

# Run basic tests
echo "🧪 Running basic package tests..."
colcon test --parallel-workers $(nproc)
colcon test-result --verbose

echo "✅ Workspace build and test complete!"
echo ""
echo "To use the workspace:"
echo "  source install/setup.bash"
echo ""
echo "Available packages:"
colcon list --packages-only