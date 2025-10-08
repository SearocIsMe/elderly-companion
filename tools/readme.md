
## models related

project-root/
└─ models/
   ├─ lid/                                 # Whisper LID (tiny)
   ├─ asr-zip-zh-en/                       # Streaming Zipformer zh-en
   ├─ asr-para-zh-en/                      # Streaming Paraformer zh-en
   ├─ asr-para-zh-yue-en/                  # Streaming Paraformer zh + Cantonese + en
   └─ vad/                                 # Silero VAD
└─ tools/
   ├─ download_models.sh
   └─ run_streaming.sh


## Download the models

```
chmod +x tools/download_models.sh
# 默认下载到 ./models，LID = tiny
tools/download_models.sh

# 或自定义
MODELS_DIR=/mnt/data/models LID_SIZE=base tools/download_models.sh

# 创建软链接
sudo ln -s ./models/vad /models
sudo ln -s ./models/asr-zip-zh-en /models

```
RK3588 如需更小模型，Zipformer/Paraformer 目录里通常带有 INT8 变体（*-int8*.onnx），脚本不需要改，运行脚本时在 run_streaming.sh 里选择对应文件名即可。

## Verification

* 支持 两类流式 ASR：zipformer / paraformer
* 自动选择 zh-en 或 zh-yue-en（中文/粤语/英语三语）
* 支持 PC 与 RK3588（同一命令行参数）
* 集成 Silero-VAD（可通过 --no-vad 关闭）
* 预留 Whisper LID 路由：这里给出“先手动选模型”。若你要真正“自动路由”，可在你的 Router Agent 里先跑 LID，再调用本脚本的相应模型分支。


```
chmod +x tools/run_streaming.sh

# 1) 先下载模型
tools/download_models.sh
# 或自定义位置/尺寸
MODELS_DIR=/mnt/data/models LID_SIZE=base tools/download_models.sh

# 2) 运行流式 zh-en（Zipformer，延迟更低）
MODELS_DIR=./models ASR_BACKEND=zipformer LANGSET=zh-en tools/run_streaming.sh

# 3) 运行流式 zh-en（Paraformer，口音兼容好）
MODELS_DIR=./models ASR_BACKEND=paraformer LANGSET=zh-en tools/run_streaming.sh

# 4) 运行三语 zh + 粤 + en（Paraformer）
MODELS_DIR=./models ASR_BACKEND=paraformer LANGSET=zh-yue-en tools/run_streaming.sh

```


## Dependent lib

```
python3 -m pip install --upgrade pip
python3 -m pip install "sherpa-onnx==1.12.14"

```