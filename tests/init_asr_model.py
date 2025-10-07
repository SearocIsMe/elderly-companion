# 创建测试脚本验证API

import sherpa_onnx
import inspect

# 获取OnlineRecognizer的构造函数信息
sig = inspect.signature(sherpa_onnx.OnlineRecognizer.__init__)
print('OnlineRecognizer构造函数参数:')
for name, param in sig.parameters.items():
    print(f'  {name}: {param}')

# 检查是否有from_config方法
if hasattr(sherpa_onnx.OnlineRecognizer, 'from_config'):
    print('\\n发现from_config方法，可能需要使用此方法')

# 获取OnlineRecognizerConfig的构造函数信息
sig = inspect.signature(sherpa_onnx.OfflineRecognizerConfig.__init__)
print('\\nOnlineRecognizerConfig构造函数参数:')
for name, param in sig.parameters.items():
    print(f'  {name}: {param}')

