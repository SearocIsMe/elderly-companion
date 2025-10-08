#!/usr/bin/env bash
set -euo pipefail

# ============ 参数 ============
MODELS_DIR="${MODELS_DIR:-$(pwd)/models}"
ASR_BACKEND="${ASR_BACKEND:-zipformer}"   # zipformer | paraformer
LANGSET="${LANGSET:-zh-en}"               # zh-en | zh-yue-en
USE_VAD="${USE_VAD:-1}"                   # 1=use silero vad, 0=disable
RATE="${RATE:-16000}"
BUFFER_FRAMES="${BUFFER_FRAMES:-8}"       # 5~10 低延迟；增大更稳
MAX_ACTIVE="${MAX_ACTIVE:-8000}"          # 端侧算力可降
DEVICE_HINT="${DEVICE_HINT:-auto}"        # auto | rk3588 | pc（可用于你在上层做分支日志）

echo "[+] MODELS_DIR=${MODELS_DIR}"
echo "[+] ASR_BACKEND=${ASR_BACKEND}, LANGSET=${LANGSET}, USE_VAD=${USE_VAD}"
echo "[+] RATE=${RATE}, BUFFER_FRAMES=${BUFFER_FRAMES}, MAX_ACTIVE=${MAX_ACTIVE}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "[-] need $1"; exit 1; }; }
# sherpa-onnx 提供多个 CLI，这里使用 microphone 入口（v1.12.14 支持）
need sherpa-onnx-microphone

# ============ 选择模型路径 ============
TOKENS=""
ARG_MODEL1=""
ARG_MODEL2=""
if [ "${ASR_BACKEND}" = "zipformer" ]; then
  if [ "${LANGSET}" = "zh-en" ]; then
    TOKENS="${MODELS_DIR}/asr-zip-zh-en/tokens.txt"
    ARG_MODEL1="--zipformer2-ctc=${MODELS_DIR}/asr-zip-zh-en/model.onnx"
  else
    echo "[-] zipformer currently prepared for zh-en in this script."
    exit 1
  fi
elif [ "${ASR_BACKEND}" = "paraformer" ]; then
  if [ "${LANGSET}" = "zh-en" ]; then
    TOKENS="${MODELS_DIR}/asr-para-zh-en/tokens.txt"
    ARG_MODEL1="--paraformer-encoder=${MODELS_DIR}/asr-para-zh-en/encoder.onnx"
    ARG_MODEL2="--paraformer-decoder=${MODELS_DIR}/asr-para-zh-en/decoder.onnx"
  elif [ "${LANGSET}" = "zh-yue-en" ]; then
    TOKENS="${MODELS_DIR}/asr-para-zh-yue-en/tokens.txt"
    ARG_MODEL1="--paraformer-encoder=${MODELS_DIR}/asr-para-zh-yue-en/encoder.onnx"
    ARG_MODEL2="--paraformer-decoder=${MODELS_DIR}/asr-para-zh-yue-en/decoder.onnx"
  else
    echo "[-] unsupported LANGSET=${LANGSET} for paraformer"
    exit 1
  fi
else
  echo "[-] unknown ASR_BACKEND=${ASR_BACKEND}"
  exit 1
fi

# VAD
VAD_ARGS=()
if [ "${USE_VAD}" = "1" ]; then
  if [ -f "${MODELS_DIR}/vad/silero_vad.onnx" ]; then
    VAD_ARGS+=( "--vad-model=${MODELS_DIR}/vad/silero_vad.onnx" )
  else
    echo "[!] VAD requested but file not found: ${MODELS_DIR}/vad/silero_vad.onnx (continue without VAD)"
  fi
fi

# ============ 运行 ============
echo "[+] Starting streaming microphone ASR..."
set -x
sherpa-onnx-microphone \
  --tokens="${TOKENS}" \
  ${ARG_MODEL1} \
  ${ARG_MODEL2:-} \
  "${VAD_ARGS[@]}" \
  --sample-rate="${RATE}" \
  --buffer-frames="${BUFFER_FRAMES}" \
  --max-active="${MAX_ACTIVE}"
