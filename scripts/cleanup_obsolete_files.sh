#!/bin/bash
# 清理多余和过时的代码文件

echo "🧹 清理多余和过时的代码文件..."
echo "=================================="

# 要删除的过时文档文件
OBSOLETE_DOCS=(
    "design-routeragent.md"
    "INDUSTRIAL_DEPLOYMENT_GUIDE.md"
)

# 要删除的过时demo和测试文件  
OBSOLETE_DEMOS=(
    "enhanced_guard_demo.py"
    "enhanced_guard_standalone_demo.py"
    "industrial_guard_llm_demo.py"
    "router_agent_chat_loop.py"
    "router_agent_chat_test.py"
    "test_simple_chat.py"
)

# 要删除的重复配置文件
OBSOLETE_CONFIGS=(
    "docker-compose.yml"
    "fix-env-repo.sh"
)

# 要删除的重复launch文件
OBSOLETE_LAUNCH=(
    "src/router_agent/launch/enhanced_elderly_companion.launch.py"
    "src/router_agent/launch/audio_pipeline.launch.py"
    "src/router_agent/launch/enhanced_guard.launch.py"
    "src/router_agent/launch/router_agent_complete.launch.py"
)

# 要删除的空或重复目录/文件
OBSOLETE_DIRS=(
    "src/router_agent/action/"
    "src/router_agent/msg/"
    "src/router_agent/srv/"
    "src/router_agent/router_agent/nodes/"
    "data/configs/"
)

# 要删除的重复nodes文件（已经有enhanced版本）
OBSOLETE_NODES=(
    "src/router_agent/nodes/router_agent_coordinator.py"
    "src/router_agent/nodes/tts_engine_node.py"
    "src/router_agent/nodes/guard_integration_node.py"
)

echo "📋 以下文件将被删除："
echo ""

echo "1. 过时文档文件："
for file in "${OBSOLETE_DOCS[@]}"; do
    if [ -f "$file" ]; then
        echo "   ✓ $file"
    fi
done

echo ""
echo "2. 过时demo和测试文件："
for file in "${OBSOLETE_DEMOS[@]}"; do
    if [ -f "$file" ]; then
        echo "   ✓ $file"
    fi
done

echo ""
echo "3. 重复配置文件："
for file in "${OBSOLETE_CONFIGS[@]}"; do
    if [ -f "$file" ]; then
        echo "   ✓ $file"
    fi
done

echo ""
echo "4. 重复launch文件："
for file in "${OBSOLETE_LAUNCH[@]}"; do
    if [ -f "$file" ]; then
        echo "   ✓ $file"
    fi
done

echo ""
echo "5. 重复或过时的nodes文件："
for file in "${OBSOLETE_NODES[@]}"; do
    if [ -f "$file" ]; then
        echo "   ✓ $file"
    fi
done

echo ""
echo "6. 空或重复目录："
for dir in "${OBSOLETE_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        # 检查目录是否为空或只有基本文件
        if [ -z "$(find "$dir" -name '*.py' -o -name '*.cpp' -o -name '*.hpp' -o -name '*.yaml' -o -name '*.json' 2>/dev/null)" ]; then
            echo "   ✓ $dir (空目录)"
        fi
    fi
done

echo ""
read -p "是否继续删除这些文件? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🗑️ 开始删除过时文件..."
    
    # 删除过时文档
    for file in "${OBSOLETE_DOCS[@]}"; do
        if [ -f "$file" ]; then
            rm -f "$file"
            echo "   删除: $file"
        fi
    done
    
    # 删除过时demo
    for file in "${OBSOLETE_DEMOS[@]}"; do
        if [ -f "$file" ]; then
            rm -f "$file"
            echo "   删除: $file"
        fi
    done
    
    # 删除重复配置
    for file in "${OBSOLETE_CONFIGS[@]}"; do
        if [ -f "$file" ]; then
            rm -f "$file"
            echo "   删除: $file"
        fi
    done
    
    # 删除重复launch文件
    for file in "${OBSOLETE_LAUNCH[@]}"; do
        if [ -f "$file" ]; then
            rm -f "$file"
            echo "   删除: $file"
        fi
    done
    
    # 删除重复nodes
    for file in "${OBSOLETE_NODES[@]}"; do
        if [ -f "$file" ]; then
            rm -f "$file"
            echo "   删除: $file"
        fi
    done
    
    # 删除空目录
    for dir in "${OBSOLETE_DIRS[@]}"; do
        if [ -d "$dir" ]; then
            if [ -z "$(find "$dir" -name '*.py' -o -name '*.cpp' -o -name '*.hpp' -o -name '*.yaml' -o -name '*.json' 2>/dev/null)" ]; then
                rm -rf "$dir"
                echo "   删除目录: $dir"
            fi
        fi
    done
    
    echo ""
    echo "✅ 清理完成!"
    echo ""
    echo "📋 保留的核心文件："
    echo "   ✓ README.md - 主要文档"
    echo "   ✓ SIMPLE_SETUP.md - 安装指南"
    echo "   ✓ requirements.txt - Python依赖"
    echo "   ✓ simple_chat_loop.py - 简单测试脚本"
    echo "   ✓ scripts/build.sh - 构建脚本"
    echo "   ✓ scripts/launch.sh - 启动脚本"
    echo "   ✓ launch/enhanced_elderly_companion.launch.py - 主启动文件"
    echo "   ✓ src/router_agent/nodes/* - 增强版nodes"
    echo "   ✓ src/router_agent/router_agent/ - 核心FastAPI服务"
    echo ""
    echo "🎯 项目结构已优化，只保留核心功能文件"
    
else
    echo "取消删除操作"
fi