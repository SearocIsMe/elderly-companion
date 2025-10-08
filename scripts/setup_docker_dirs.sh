#!/bin/bash

# =============================================================================
# Elderly Companion System - Docker Directory Setup Script (Relative Paths)
# =============================================================================

echo "🔧 Setting up Docker directories for Elderly Companion System..."
echo "=============================================================================="

# 获取当前工作目录（应该是elderly-companion目录）
CURRENT_DIR="$(pwd)"
echo "✅ Current working directory: $CURRENT_DIR"

# 项目根目录就是当前目录
PROJECT_ROOT="$CURRENT_DIR"
echo "✅ Project root directory: $PROJECT_ROOT"

# 1. 创建install目录下的docker目录
echo "📁 Creating docker directory in install folder..."
INSTALL_DOCKER_DIR="$PROJECT_ROOT/install/elderly_companion/docker"
mkdir -p "$INSTALL_DOCKER_DIR"

if [ $? -eq 0 ]; then
    echo "✅ Successfully created: $INSTALL_DOCKER_DIR"
else
    echo "❌ Failed to create directory: $INSTALL_DOCKER_DIR"
    exit 1
fi

# 2. 复制docker compose文件
echo "🔄 Copying Docker compose files..."
SOURCE_DOCKER_DIR="$PROJECT_ROOT/src/router_agent/docker"

if [ -d "$SOURCE_DOCKER_DIR" ]; then
    echo "🔍 Found source directory: $SOURCE_DOCKER_DIR"
    cp "$SOURCE_DOCKER_DIR"/* "$INSTALL_DOCKER_DIR/"
    
    if [ $? -eq 0 ]; then
        echo "✅ Successfully copied Docker compose files to: $INSTALL_DOCKER_DIR"
        
        # 列出复制的文件
        echo "📋 Copied files:"
        ls -la "$INSTALL_DOCKER_DIR"
    else
        echo "❌ Failed to copy Docker compose files"
        exit 1
    fi
else
    echo "❌ Error: Source Docker directory not found: $SOURCE_DOCKER_DIR"
    echo "💡 Please verify the directory structure exists."
    exit 1
fi

# 3. 验证文件是否正确复制
echo "🔍 Verifying copied files..."
if [ -f "$INSTALL_DOCKER_DIR/docker-compose.pc.yml" ] || 
   [ -f "$INSTALL_DOCKER_DIR/docker-compose.rk3588.yml" ] ||
   [ -f "$INSTALL_DOCKER_DIR/docker-compose.pc.gpu.yml" ]; then
    echo "✅ Verification successful - Docker compose files are present"
else
    echo "⚠️ Warning: No Docker compose files found in destination"
fi

# 4. 设置适当的权限
echo "🔐 Setting proper permissions..."
chmod -R 755 "$INSTALL_DOCKER_DIR"

if [ $? -eq 0 ]; then
    echo "✅ Permissions set successfully"
else
    echo "⚠️ Warning: Failed to set permissions"
fi

echo "=============================================================================="
echo "🎉 Docker directory setup completed successfully!"
echo ""
echo "💡 Next steps:"
echo "   1. Run: ./scripts/launch.sh to start the system"
echo "   2. Verify all components are running properly"
echo "   3. Test UC1 functionality: 聊天 + 智能家居控制"
echo "=============================================================================="

# 显示当前目录结构
echo ""
echo "📁 Current directory structure:"
find "$INSTALL_DOCKER_DIR" -type f -name "*.yml" | sort
