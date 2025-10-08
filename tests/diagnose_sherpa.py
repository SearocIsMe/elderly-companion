# 创建诊断脚本 diagnose_sherpa.py
#!/usr/bin/env python3

import sherpa_onnx
import inspect

print("=== Sherpa-onnx API Diagnosis ===")
print(f"Sherpa-onnx version: {getattr(sherpa_onnx, '__version__', 'Unknown')}")

# 显示所有可用的类和函数
print("\n=== Available classes and functions ===")
for item in dir(sherpa_onnx):
    if not item.startswith('_'):
        obj = getattr(sherpa_onnx, item)
        if inspect.isclass(obj) or inspect.isfunction(obj):
            print(f"  {item}: {type(obj)}")

# 检查OnlineRecognizer
print("\n=== OnlineRecognizer Analysis ===")
if hasattr(sherpa_onnx, 'OnlineRecognizer'):
    recognizer_class = sherpa_onnx.OnlineRecognizer
    print(f"OnlineRecognizer type: {type(recognizer_class)}")
    
    # 检查构造函数
    if hasattr(recognizer_class, '__init__'):
        init_sig = inspect.signature(recognizer_class.__init__)
        print(f"Constructor signature: {init_sig}")
        
    # 检查类方法
    class_methods = [method for method in dir(recognizer_class) if not method.startswith('_')]
    print(f"Class methods: {class_methods}")
else:
    print("OnlineRecognizer not found!")

# 检查相关配置类
config_classes = ['OnlineRecognizerConfig', 'OnlineModelConfig', 'FeatureConfig', 'OnlineTransducerModelConfig']
print(f"\n=== Configuration Classes Check ===")
for cls_name in config_classes:
    if hasattr(sherpa_onnx, cls_name):
        print(f"✓ {cls_name} found")
        cls_obj = getattr(sherpa_onnx, cls_name)
        if hasattr(cls_obj, '__init__'):
            sig = inspect.signature(cls_obj.__init__)
            print(f"  Constructor: {sig}")
    else:
        print(f"✗ {cls_name} not found")
