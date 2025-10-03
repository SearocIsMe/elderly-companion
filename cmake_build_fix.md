# 🔧 CMake Build Configuration Fix

## Problem Analysis

The `scripts/cleanup_obsolete_files.sh` deleted several obsolete node files, but the main [`CMakeLists.txt`](CMakeLists.txt) still references these deleted files, causing build errors.

### Files Deleted by Cleanup Script:
1. `src/router_agent/nodes/router_agent_coordinator.py` (replaced by `enhanced_router_coordinator.py`)
2. `src/router_agent/nodes/tts_engine_node.py` (replaced by `enhanced_tts_engine_node.py`)
3. `src/router_agent/nodes/guard_integration_node.py` (replaced by `guard_fastapi_bridge_node.py`)

### Current Error:
```
CMake Error at cmake_install.cmake:468 (file):
  file INSTALL cannot find
  "/mnt/c/Users/haipeng/Documents/00-code/02-RobDog/elderly-companion/src/router_agent/nodes/router_agent_coordinator.py":
  No such file or directory.
```

## Solution: Update CMakeLists.txt

### Current Problematic Lines (53-63):
```cmake
install(PROGRAMS
  # Original router agent nodes
  src/router_agent/nodes/router_agent_coordinator.py        # ❌ DELETED
  src/router_agent/nodes/dialog_manager_node.py
  src/router_agent/nodes/speech_recognition_node.py
  src/router_agent/nodes/audio_processor_node.py
  src/router_agent/nodes/emotion_analyzer_node.py
  src/router_agent/nodes/safety_guard_node.py
  src/router_agent/nodes/tts_engine_node.py               # ❌ DELETED
  src/router_agent/nodes/mqtt_adapter_node.py
  src/router_agent/nodes/enhanced_guard_engine.py
  src/router_agent/nodes/guard_integration_node.py        # ❌ DELETED
  src/router_agent/nodes/sip_voip_adapter_node.py
```

### Fixed Configuration:
```cmake
install(PROGRAMS
  # Core router agent nodes (existing)
  src/router_agent/nodes/dialog_manager_node.py
  src/router_agent/nodes/speech_recognition_node.py
  src/router_agent/nodes/audio_processor_node.py
  src/router_agent/nodes/emotion_analyzer_node.py
  src/router_agent/nodes/safety_guard_node.py
  src/router_agent/nodes/mqtt_adapter_node.py
  src/router_agent/nodes/enhanced_guard_engine.py
  src/router_agent/nodes/sip_voip_adapter_node.py
  
  # Enhanced integration nodes (existing)
  src/router_agent/nodes/enhanced_router_coordinator.py    # ✅ REPLACEMENT
  src/router_agent/nodes/enhanced_tts_engine_node.py       # ✅ REPLACEMENT  
  src/router_agent/nodes/guard_fastapi_bridge_node.py     # ✅ REPLACEMENT
  src/router_agent/nodes/fastapi_bridge_node.py
  src/router_agent/nodes/silero_vad_node.py
  src/router_agent/nodes/smart_home_backend_node.py
  src/router_agent/nodes/webrtc_uplink_node.py
  
  DESTINATION lib/${PROJECT_NAME}
)
```

## Implementation Steps:

1. **Remove deleted file references**: Lines 53, 59, 62 in [`CMakeLists.txt`](CMakeLists.txt)
2. **Update with correct enhanced replacements**
3. **Verify all existing node files are included**
4. **Test build process**

## Files to Modify:
- [`CMakeLists.txt`](CMakeLists.txt:51-75) - Update install(PROGRAMS) section

## Exact Code Changes Required:

### Replace lines 51-75 in [`CMakeLists.txt`](CMakeLists.txt):

```cmake
# Install Python nodes for Router Agent architecture - Enhanced Integration
install(PROGRAMS
  # Core router agent nodes (existing)
  src/router_agent/nodes/dialog_manager_node.py
  src/router_agent/nodes/speech_recognition_node.py
  src/router_agent/nodes/audio_processor_node.py
  src/router_agent/nodes/emotion_analyzer_node.py
  src/router_agent/nodes/safety_guard_node.py
  src/router_agent/nodes/mqtt_adapter_node.py
  src/router_agent/nodes/enhanced_guard_engine.py
  src/router_agent/nodes/sip_voip_adapter_node.py
  
  # Enhanced integration nodes (existing)
  src/router_agent/nodes/enhanced_router_coordinator.py
  src/router_agent/nodes/enhanced_tts_engine_node.py
  src/router_agent/nodes/guard_fastapi_bridge_node.py
  src/router_agent/nodes/fastapi_bridge_node.py
  src/router_agent/nodes/silero_vad_node.py
  src/router_agent/nodes/smart_home_backend_node.py
  src/router_agent/nodes/webrtc_uplink_node.py
  
  DESTINATION lib/${PROJECT_NAME}
)
```

### Files Removed (these 3 lines must be deleted):
- Line 53: `src/router_agent/nodes/router_agent_coordinator.py` ❌ DELETED
- Line 59: `src/router_agent/nodes/tts_engine_node.py` ❌ DELETED
- Line 62: `src/router_agent/nodes/guard_integration_node.py` ❌ DELETED

### Files Added (these enhanced versions replace the deleted ones):
- `src/router_agent/nodes/enhanced_router_coordinator.py` ✅ REPLACEMENT for router_agent_coordinator.py
- `src/router_agent/nodes/enhanced_tts_engine_node.py` ✅ REPLACEMENT for tts_engine_node.py
- `src/router_agent/nodes/guard_fastapi_bridge_node.py` ✅ REPLACEMENT for guard_integration_node.py

## Verification:
After fix, all 15 existing node files should be properly installed:
- ✅ audio_processor_node.py
- ✅ dialog_manager_node.py  
- ✅ emotion_analyzer_node.py
- ✅ enhanced_guard_engine.py
- ✅ enhanced_router_coordinator.py
- ✅ enhanced_tts_engine_node.py
- ✅ fastapi_bridge_node.py
- ✅ guard_fastapi_bridge_node.py
- ✅ mqtt_adapter_node.py
- ✅ safety_guard_node.py
- ✅ silero_vad_node.py
- ✅ sip_voip_adapter_node.py
- ✅ smart_home_backend_node.py
- ✅ speech_recognition_node.py
- ✅ webrtc_uplink_node.py