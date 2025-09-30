#!/bin/bash
# Fix CMake Path Issues for ROS2 Build
# Handles conda environment conflicts and broken pip installations

echo "🔧 Fixing CMake path issues..."

# Check current environment
echo "Current environment:"
echo "  Conda env: $CONDA_DEFAULT_ENV"
echo "  Python: $(which python)"
echo "  User: $USER"

# Check current cmake status and diagnose issues
echo ""
echo "Diagnosing cmake issues..."
if command -v cmake >/dev/null 2>&1; then
    CMAKE_PATH=$(which cmake)
    echo "✅ cmake found in PATH at: $CMAKE_PATH"
    
    # Test if cmake actually works
    if cmake --version >/dev/null 2>&1; then
        echo "✅ cmake is working properly"
        CMAKE_VERSION=$(cmake --version | head -n1)
        echo "✅ CMake version: $CMAKE_VERSION"
        exit 0
    else
        echo "❌ cmake found but not working"
        
        # Check if it's a conda/pip shebang issue
        if [ -f "$CMAKE_PATH" ]; then
            SHEBANG=$(head -n1 "$CMAKE_PATH")
            echo "  Shebang: $SHEBANG"
            
            if [[ "$SHEBANG" == *"python"* ]]; then
                PYTHON_PATH=$(echo "$SHEBANG" | sed 's/#!//' | awk '{print $1}')
                echo "  Points to Python: $PYTHON_PATH"
                
                if [ ! -f "$PYTHON_PATH" ]; then
                    echo "❌ Python interpreter not found (conda environment issue)"
                    echo "  This cmake was installed in a different conda environment"
                    NEEDS_REINSTALL=true
                fi
            fi
        fi
    fi
else
    echo "❌ cmake not found in PATH"
    NEEDS_REINSTALL=true
fi

# Function to install cmake properly
install_cmake_system() {
    echo ""
    echo "📦 Installing cmake via system package manager..."
    
    if command -v apt-get >/dev/null 2>&1; then
        echo "Installing cmake via apt-get (recommended)..."
        sudo apt-get update
        sudo apt-get install -y cmake
    elif command -v yum >/dev/null 2>&1; then
        echo "Installing cmake via yum..."
        sudo yum install -y cmake
    elif command -v dnf >/dev/null 2>&1; then
        echo "Installing cmake via dnf..."
        sudo dnf install -y cmake
    elif command -v pacman >/dev/null 2>&1; then
        echo "Installing cmake via pacman..."
        sudo pacman -S cmake
    else
        echo "❌ No system package manager found"
        return 1
    fi
}

install_cmake_conda() {
    echo ""
    echo "📦 Installing cmake via conda (current environment)..."
    
    if command -v conda >/dev/null 2>&1; then
        conda install -y cmake
    elif command -v mamba >/dev/null 2>&1; then
        mamba install -y cmake
    else
        echo "❌ Conda not available"
        return 1
    fi
}

install_cmake_pip() {
    echo ""
    echo "📦 Installing cmake via pip (current environment)..."
    
    # Remove broken cmake first
    if [ -f "$HOME/.local/bin/cmake" ]; then
        echo "Removing broken cmake..."
        rm -f "$HOME/.local/bin/cmake"
    fi
    
    # Install with current Python
    pip install --user --force-reinstall cmake
    export PATH="$HOME/.local/bin:$PATH"
}

# If cmake needs reinstalling or fixing
if [ "$NEEDS_REINSTALL" = true ]; then
    echo ""
    echo "🛠️ CMake needs to be reinstalled/fixed"
    echo ""
    echo "Available options:"
    echo "1. Install via system package manager (recommended)"
    echo "2. Install via conda (current environment)"
    echo "3. Install via pip (current environment)"
    echo "4. Manual fix"
    echo ""
    
    read -p "Choose option (1-4, default 1): " choice
    choice=${choice:-1}
    
    case $choice in
        1)
            if install_cmake_system; then
                echo "✅ System cmake installed"
            else
                echo "❌ System installation failed, trying conda..."
                install_cmake_conda
            fi
            ;;
        2)
            install_cmake_conda
            ;;
        3)
            install_cmake_pip
            ;;
        4)
            echo ""
            echo "Manual fix instructions:"
            echo "1. Remove broken cmake: rm -f ~/.local/bin/cmake"
            echo "2. Install system cmake: sudo apt-get install cmake"
            echo "3. Or install in current conda env: conda install cmake"
            echo "4. Or reinstall with pip: pip install --user --force-reinstall cmake"
            exit 1
            ;;
        *)
            echo "Invalid choice, defaulting to system installation"
            install_cmake_system
            ;;
    esac
fi

# Verify final installation
echo ""
echo "🧪 Verifying cmake installation:"
if command -v cmake >/dev/null 2>&1; then
    if cmake --version >/dev/null 2>&1; then
        CMAKE_VERSION=$(cmake --version | head -n1)
        CMAKE_PATH=$(which cmake)
        echo "✅ CMake is working: $CMAKE_VERSION"
        echo "✅ CMake path: $CMAKE_PATH"
        
        # Update PATH for current session
        if [[ "$CMAKE_PATH" == *"/.local/bin/"* ]]; then
            export PATH="$HOME/.local/bin:$PATH"
        fi
        
    else
        echo "❌ CMake still not working after installation"
        exit 1
    fi
else
    echo "❌ CMake still not found after installation"
    exit 1
fi

echo ""
echo "🎉 CMake is now working! You can run:"
echo "  ./scripts/build_workspace.sh"
echo ""
echo "💡 Note: If you're using conda, consider installing cmake via conda:"
echo "  conda install cmake"