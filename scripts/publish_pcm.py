#!/usr/bin/env python3
import sys
import time
import numpy as np
import rclpy
from rclpy.node import Node
from std_msgs.msg import ByteMultiArray

try:
    import soundfile as sf
except Exception:
    sf = None

class PcmPublisher(Node):
    def __init__(self, wav_path=None, sr=16000):
        super().__init__('pcm_publisher')
        self.pub = self.create_publisher(ByteMultiArray, '/audio/raw_stream_in', 10)
        self.timer = None
        self.sr = sr
        self.wav = None
        self.pos = 0
        self.chunk = int(sr * 0.02)  # 20ms per publish

        if wav_path and sf is not None:
            data, wsr = sf.read(wav_path, dtype='float32', always_2d=False)
            if data.ndim > 1:
                data = data.mean(axis=1)
            if wsr != sr:
                # 简单重采样（线性），仅测试用途
                x = np.linspace(0, 1, num=data.size, endpoint=False)
                y = np.linspace(0, 1, num=int(data.size * sr / wsr), endpoint=False)
                data = np.interp(y, x, data).astype(np.float32, copy=False)
            self.wav = data
            self.get_logger().info(f'Loaded wav: {wav_path} (sr={sr}, samples={self.wav.size})')
        else:
            self.get_logger().warn('No wav provided; generating 440Hz sine test')
            t = np.arange(0, 5 * sr) / sr
            self.wav = (0.1 * np.sin(2*np.pi*440*t)).astype(np.float32)

        self.timer = self.create_timer(0.02, self.tick)

    def tick(self):
        if self.pos >= self.wav.size:
            self.get_logger().info('Done.')
            rclpy.shutdown()
            return
        end = min(self.pos + self.chunk, self.wav.size)
        x = self.wav[self.pos:end]
        self.pos = end
        msg = ByteMultiArray()
        msg.data = bytearray(x.tobytes())
        self.pub.publish(msg)

def main():
    rclpy.init()
    wav = sys.argv[1] if len(sys.argv) > 1 else None
    node = PcmPublisher(wav_path=wav)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()

if __name__ == '__main__':
    main()
