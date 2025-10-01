#!/bin/bash
"""
Enhanced Router Agent Setup Script

This script ensures the router_agent package is properly built and configured
for the Enhanced Elderly Companion system.
"""

set -e  # Exit on any error

echo "🚀 Setting up Enhanced Router Agent System..."

# Check if we're in the right directory
if [ ! -f "src/router_agent/package.xml" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    echo "   Expected to find: src/router_agent/package.xml"
    exit 1
fi

echo "✅ Project directory verified"

# Source ROS2 environment
echo "📦 Sourcing ROS2 Humble environment..."
if [ -f "/opt/ros/humble/setup.bash" ]; then
    source /opt/ros/humble/setup.bash
    echo "✅ ROS2 Humble sourced"
else
    echo "❌ Error: ROS2 Humble not found. Please install ROS2 Humble first."
    echo "   sudo apt install ros-humble-desktop"
    exit 1
fi

# Make sure all Python nodes are executable
echo "🔧 Making Python nodes executable..."
chmod +x src/router_agent/nodes/*.py
chmod +x src/router_agent/launch/*.py
chmod +x src/router_agent/config/*.py
chmod +x src/router_agent/tests/*.py
echo "✅ Python files made executable"

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf build/ install/ log/
echo "✅ Previous builds cleaned"

# Build the workspace
echo "🔨 Building ROS2 workspace..."
if [ -f "scripts/build_workspace.sh" ]; then
    chmod +x scripts/build_workspace.sh
    ./scripts/build_workspace.sh
else
    # Manual build if script doesn't exist
    colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release
fi

if [ $? -eq 0 ]; then
    echo "✅ Workspace built successfully"
else
    echo "❌ Workspace build failed"
    exit 1
fi

# Source the built workspace
echo "📋 Sourcing built workspace..."
if [ -f "install/setup.bash" ]; then
    source install/setup.bash
    echo "✅ Workspace sourced"
else
    echo "❌ Error: install/setup.bash not found. Build may have failed."
    exit 1
fi

# Verify package is available
echo "🔍 Verifying elderly_companion package..."
if ros2 pkg list | grep -q "elderly_companion"; then
    echo "✅ elderly_companion package found"
else
    echo "❌ Error: elderly_companion package not found after build"
    echo "   This suggests a build configuration issue"
    exit 1
fi

# Verify executables are available
echo "🔍 Verifying enhanced nodes are available..."
EXECUTABLES=$(ros2 pkg executables elderly_companion)
if echo "$EXECUTABLES" | grep -q "enhanced_router_coordinator.py"; then
    echo "✅ Enhanced nodes found:"
    echo "$EXECUTABLES"
else
    echo "⚠️ Warning: Enhanced nodes not found in package executables"
    echo "Available executables:"
    echo "$EXECUTABLES"
fi

# Verify launch files are available
echo "🔍 Verifying launch files..."
if [ -f "install/elderly_companion/share/elderly_companion/launch/enhanced_elderly_companion.launch.py" ]; then
    echo "✅ Enhanced launch file installed"
else
    echo "❌ Error: Enhanced launch file not installed"
    echo "   Check if launch file exists in launch/"
    ls -la launch/
    exit 1
fi

# Test launch file syntax
echo "🔍 Testing launch file syntax..."
python3 -m py_compile install/elderly_companion/share/elderly_companion/launch/enhanced_elderly_companion.launch.py
if [ $? -eq 0 ]; then
    echo "✅ Launch file syntax verified"
else
    echo "❌ Error: Launch file has syntax errors"
    exit 1
fi

echo ""
echo "🎉 Enhanced Router Agent Setup Complete!"
echo ""
echo "📋 Next steps:"
echo "1. Start FastAPI services:"
echo "   cd src/router_agent/router_agent/docker"
echo "   docker compose -f docker-compose.pc.yml up -d"
echo ""
echo "2. Launch the enhanced system:"
echo "   cd ../../../"
echo "   source install/setup.bash  # Always source before launch"
echo "   ros2 launch elderly_companion enhanced_elderly_companion.launch.py mode:=hybrid"
echo ""
echo "3. If you still get 'Package not found' error:"
echo "   - Ensure you're in the project root directory"
echo "   - Run: source install/setup.bash"
echo "   - Check: ros2 pkg list | grep elderly_companion"
echo ""