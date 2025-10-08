#!/usr/bin/env bash
set -euo pipefail

# ============ 参数 ============
# 可通过环境变量覆盖：
# MODELS_DIR: 模型存放根目录
# LID_SIZE: whisper LID 尺寸（tiny/base/small）— 默认 tiny
MODELS_DIR="${MODELS_DIR:-$(pwd)/models}"
LID_SIZE="${LID_SIZE:-tiny}"

mkdir -p "${MODELS_DIR}"
echo "[+] Models root: ${MODELS_DIR}"

# -------- 依赖检查 --------
need() { command -v "$1" >/dev/null 2>&1 || { echo "[-] need $1"; exit 1; }; }
# wget / curl 二选一
if command -v wget >/dev/null 2>&1; then DL="wget -q --show-progress -O"; elif command -v curl >/dev/null 2>&1; then DL="curl -L --progress-bar -o"; else echo "[-] need wget or curl"; exit 1; fi
need tar
need git

# -------- Whisper LID（多语） --------
LID_DIR="${MODELS_DIR}/lid"
mkdir -p "${LID_DIR}"
echo "[+] Download LID (whisper-${LID_SIZE})"
case "${LID_SIZE}" in
  tiny)  LID_TARBALL="sherpa-onnx-whisper-tiny.tar.bz2" ;;
  base)  LID_TARBALL="sherpa-onnx-whisper-base.tar.bz2" ;;
  small) LID_TARBALL="sherpa-onnx-whisper-small.tar.bz2" ;;
  *) echo "[-] invalid LID_SIZE=${LID_SIZE}"; exit 1;;
esac
${DL} "${LID_DIR}/${LID_TARBALL}" "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/${LID_TARBALL}"
tar xf "${LID_DIR}/${LID_TARBALL}" -C "${LID_DIR}" && rm -f "${LID_DIR}/${LID_TARBALL}"

# -------- Streaming Zipformer zh-en --------
if [ ! -d "${MODELS_DIR}/asr-zip-zh-en" ]; then
  echo "[+] Clone streaming zipformer zh-en"
  git clone https://huggingface.co/csukuangfj/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20 \
    "${MODELS_DIR}/asr-zip-zh-en"
else
  echo "[=] asr-zip-zh-en exists. Skipping."
fi

# -------- Streaming Paraformer zh-en --------
if [ ! -d "${MODELS_DIR}/asr-para-zh-en" ]; then
  echo "[+] Clone streaming paraformer zh-en"
  git clone https://huggingface.co/csukuangfj/sherpa-onnx-streaming-paraformer-bilingual-zh-en \
    "${MODELS_DIR}/asr-para-zh-en"
else
  echo "[=] asr-para-zh-en exists. Skipping."
fi

# -------- Streaming Paraformer zh + Cantonese + en --------
if [ ! -d "${MODELS_DIR}/asr-para-zh-yue-en" ]; then
  echo "[+] Clone streaming paraformer zh-yue-en"
  git clone https://huggingface.co/csukuangfj/sherpa-onnx-streaming-paraformer-trilingual-zh-cantonese-en \
    "${MODELS_DIR}/asr-para-zh-yue-en"
else
  echo "[=] asr-para-zh-yue-en exists. Skipping."
fi

# -------- Silero VAD --------
VAD_DIR="${MODELS_DIR}/vad"
mkdir -p "${VAD_DIR}"
# 多渠道会提供 silero_vad.onnx；这里给出常用命名，若已存在就不覆盖
if [ ! -f "${VAD_DIR}/silero_vad.onnx" ]; then
  echo "[+] Download silero_vad.onnx (example mirror)"
  ${DL} "${VAD_DIR}/silero_vad.onnx" "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad.onnx" || true
  if [ ! -f "${VAD_DIR}/silero_vad.onnx" ]; then
    echo "[!] Could not auto-download silero_vad.onnx. Place it under ${VAD_DIR}/silero_vad.onnx manually."
  fi
else
  echo "[=] vad/silero_vad.onnx exists. Skipping."
fi

echo "[✓] All downloads prepared in ${MODELS_DIR}"
