#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
os.environ.setdefault("OMP_NUM_THREADS", "1")  # 减少 OpenMP 冲突

import math
import time
from typing import Optional, Deque
from collections import deque

import numpy as np

try:
    import scipy.signal as sps
    SCIPY_OK = True
except Exception:
    SCIPY_OK = False

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import ByteMultiArray, String


class SileroVADNode(Node):
    """
    稳定版 VAD 节点（无 torch/torchaudio 依赖）：
    - 订阅: /audio/raw_stream_in (ByteMultiArray) —— 载荷是 float32 PCM 的 bytes
    - 发布: /audio/processed_stream (ByteMultiArray) —— 可选降噪/重采样后 PCM bytes
            /audio/speech_segments (ByteMultiArray) —— 语音段落 PCM bytes
    """

    def __init__(self):
        super().__init__("silero_vad_node")

        # ---- 参数 ----
        self.declare_parameter("audio.sample_rate", 16000)
        self.declare_parameter("audio.channels", 1)
        self.declare_parameter("audio.encoding", "f32le")  # 浮点小端序列化
        self.declare_parameter("vad.frame_ms", 20)
        self.declare_parameter("vad.hop_ms", 10)
        self.declare_parameter("vad.threshold", 0.015)      # 能量阈值（均方根）
        self.declare_parameter("vad.min_speech_ms", 200)    # 起始最短语音
        self.declare_parameter("vad.max_sil_ms", 300)       # 判定说话结束的静音时长
        self.declare_parameter("resample.to_16k", True)     # 非 16k 采样率时尽量重采样
        self.declare_parameter("debug.log_energy", False)

        self.sr = int(self.get_parameter("audio.sample_rate").value)
        self.channels = int(self.get_parameter("audio.channels").value)
        self.encoding = str(self.get_parameter("audio.encoding").value)
        self.frame_ms = int(self.get_parameter("vad.frame_ms").value)
        self.hop_ms = int(self.get_parameter("vad.hop_ms").value)
        self.energy_th = float(self.get_parameter("vad.threshold").value)
        self.min_speech_ms = int(self.get_parameter("vad.min_speech_ms").value)
        self.max_sil_ms = int(self.get_parameter("vad.max_sil_ms").value)
        self.to_16k = bool(self.get_parameter("resample.to_16k").value)
        self.log_energy = bool(self.get_parameter("debug.log_energy").value)

        # ---- QoS ----
        reliable_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )
        realtime_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        # ---- 话题 ----
        self.sub_raw = self.create_subscription(
            ByteMultiArray, "/audio/raw_stream_in", self.on_audio, realtime_qos
        )
        self.pub_processed = self.create_publisher(
            ByteMultiArray, "/audio/processed_stream", realtime_qos
        )
        self.pub_segments = self.create_publisher(
            ByteMultiArray, "/audio/speech_segments", reliable_qos
        )
        self.pub_meta = self.create_publisher(
            String, "/audio/vad_meta", realtime_qos
        )

        # ---- 状态缓存 ----
        self._buf: Deque[np.ndarray] = deque()
        self._speech_buf: Deque[np.ndarray] = deque()
        self._in_speech = False
        self._last_speech_ts: Optional[float] = None
        self._last_voice_ts: Optional[float] = None

        # 预计算
        self.frame_len = max(1, int(self.sr * self.frame_ms / 1000))
        self.hop_len = max(1, int(self.sr * self.hop_ms / 1000))
        self.min_speech_frames = max(1, int(self.min_speech_ms / self.hop_ms))
        self.max_sil_frames = max(1, int(self.max_sil_ms / self.hop_ms))

        self.get_logger().info(
            f"SileroVADNode ready: sr={self.sr}, frame={self.frame_ms}ms, hop={self.hop_ms}ms, "
            f"th={self.energy_th}, min_speech={self.min_speech_ms}ms, max_sil={self.max_sil_ms}ms, "
            f"channels={self.channels}, encoding={self.encoding}, scipy={SCIPY_OK}"
        )

    # ---------- 工具 ----------
    def _bytes_to_f32(self, data: bytes) -> np.ndarray:
        arr = np.frombuffer(data, dtype=np.float32)
        # 仅处理单声道；多通道时取均值
        if self.channels > 1:
            arr = arr.reshape(-1, self.channels).mean(axis=1).astype(np.float32, copy=False)
        return arr

    def _f32_to_msg(self, x: np.ndarray) -> ByteMultiArray:
        msg = ByteMultiArray()
        msg.data = bytearray(x.astype(np.float32, copy=False).tobytes())
        return msg

    def _resample_to_16k(self, x: np.ndarray, sr: int) -> np.ndarray:
        if sr == 16000 or not self.to_16k:
            return x
        if not SCIPY_OK:
            return x  # 没 scipy 就不重采样
        g = math.gcd(sr, 16000)
        up, down = 16000 // g, sr // g
        y = sps.resample_poly(x, up, down).astype(np.float32, copy=False)
        return y

    def _frame_rms(self, x: np.ndarray) -> float:
        if x.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(x), dtype=np.float64)))

    # ---------- 主回调 ----------
    def on_audio(self, msg: ByteMultiArray):
        now = time.time()
        try:
            # 解码 float32 PCM
            x = self._bytes_to_f32(bytes(msg.data))
            # 重采样到 16k（可选）
            x = self._resample_to_16k(x, self.sr)

            # 直接回传“处理后”音频（当前未做降噪；留接口）
            self.pub_processed.publish(self._f32_to_msg(x))

            # 在线分帧 & VAD
            # 把新数据放入缓冲
            self._buf.append(x)
            buf = np.concatenate(list(self._buf), dtype=np.float32) if len(self._buf) > 1 else x

            # 至少要有一帧
            if buf.size < self.frame_len:
                return

            pos = 0
            voice_frames = 0
            silence_frames = 0

            while pos + self.frame_len <= buf.size:
                frame = buf[pos:pos + self.frame_len]
                pos += self.hop_len

                e = self._frame_rms(frame)
                if self.log_energy:
                    self.get_logger().info(f"rms={e:.4f}")

                voiced = e >= self.energy_th

                if voiced:
                    self._speech_buf.append(frame.copy())
                    voice_frames += 1
                    silence_frames = 0
                    self._last_voice_ts = now

                    # 进入说话态：达到最短语音门限
                    if not self._in_speech and voice_frames >= self.min_speech_frames:
                        self._in_speech = True
                        self._last_speech_ts = now
                        self._speech_buf.clear()  # 统一从此刻开始缓存
                        self._speech_buf.append(frame.copy())
                else:
                    if self._in_speech:
                        silence_frames += 1
                        if silence_frames >= self.max_sil_frames:
                            # 结束：发布语音段
                            seg = np.concatenate(list(self._speech_buf), dtype=np.float32) \
                                if len(self._speech_buf) > 1 else (self._speech_buf[0] if self._speech_buf else np.zeros(0, np.float32))
                            if seg.size > 0:
                                self.pub_segments.publish(self._f32_to_msg(seg))
                                meta = {
                                    "type": "speech_segment",
                                    "samples": int(seg.size),
                                    "sr": 16000 if self.to_16k else self.sr,
                                    "duration_sec": round(seg.size / (16000 if self.to_16k else self.sr), 3),
                                    "ts": now,
                                }
                                self.pub_meta.publish(String(data=str(meta)))
                            # reset
                            self._speech_buf.clear()
                            self._in_speech = False
                            voice_frames = 0
                            silence_frames = 0
                    else:
                        # 仍在静音态，滑窗推进
                        voice_frames = 0
                        silence_frames += 1

            # 丢弃已经滑过的部分，保留尾部用于下一回合拼接
            tail_start = max(0, buf.size - self.frame_len)
            tail = buf[tail_start:]
            self._buf.clear()
            if tail.size:
                self._buf.append(tail)

        except Exception as e:
            self.get_logger().error(f"on_audio error: {e}")


def main(args=None):
    rclpy.init(args=args)
    node = SileroVADNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
