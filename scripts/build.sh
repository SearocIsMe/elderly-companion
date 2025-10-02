#!/bin/bash
# Enhanced Elderly Companion - Build Script
# Builds the complete ROS2 workspace with all components

set -e

echo "🔨 BUILDING ENHANCED ELDERLY COMPANION SYSTEM"
echo "=============================================="

# 1. Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf build/ install/ log/ .colcon_build

# 2. Create missing service definitions (if not exists)
echo "📝 Ensuring service definitions exist..."
mkdir -p srv

if [ ! -f "srv/ValidateIntent.srv" ]; then
    cat > srv/ValidateIntent.srv << 'EOF'
string intent_type
string text
---
bool validation_passed
string validation_reason
EOF
fi

if [ ! -f "srv/ExecuteAction.srv" ]; then
    cat > srv/ExecuteAction.srv << 'EOF'
string action_type
string parameters
---
bool execution_successful
string result_message
EOF
fi

if [ ! -f "srv/EmergencyDispatch.srv" ]; then
    cat > srv/EmergencyDispatch.srv << 'EOF'
string emergency_type
int32 severity_level
---
bool dispatch_successful
string reference_id
EOF
fi

# 3. Update CMakeLists.txt if needed
if ! grep -q "ValidateIntent.srv" CMakeLists.txt; then
    echo "📋 Updating CMakeLists.txt with missing services..."
    sed -i '/srv\/ProcessSpeech.srv/a\
  "srv/ValidateIntent.srv"\
  "srv/ExecuteAction.srv"\
  "srv/EmergencyDispatch.srv"' CMakeLists.txt
fi

# 4. Fix line endings (critical for WSL)
echo "🔧 Fixing line endings..."
if command -v dos2unix &> /dev/null; then
    find src/router_agent/nodes -name "*.py" -type f -exec dos2unix {} \; 2>/dev/null || true
    find launch -name "*.py" -type f -exec dos2unix {} \; 2>/dev/null || true
else
    echo "⚠️ dos2unix not available, skipping line ending fixes"
fi

# 5. Build the workspace
echo "🔨 Building ROS2 workspace..."
colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release

if [ $? -eq 0 ]; then
    echo "✅ Build completed successfully!"
    echo ""
    echo "📋 Next steps:"
    echo "1. Source the workspace: source install/setup.bash"
    echo "2. Launch system: ./scripts/launch.sh"
else
    echo "❌ Build failed!"
    exit 1
fi