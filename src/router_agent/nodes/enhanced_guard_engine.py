#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from typing import List
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from std_msgs.msg import String

# 你的 ASR 结果消息（与 SpeechRecognitionNode 对齐）
# 如果你的包名/消息名不同，请在此处调整
from elderly_companion.msg import SpeechResult


class EnhancedGuardEngine(Node):
    """
    Guard（前置）引擎：
    - 订阅 /speech/recognized (SpeechResult)
    - 发布 /guard/events (String JSON)
    - 负责唤醒词、SOS、（占位）地理围栏等前置规则
    """

    def __init__(self):
        super().__init__("enhanced_guard_engine")

        # ---- 参数 ----
        self.declare_parameter("guard.wakewords", ["小安", "小安小安", "hey buddy"])
        self.declare_parameter("guard.sos_keywords", ["救命", "不舒服", "急救", "help", "emergency"])
        self.declare_parameter("guard.geofence.enabled", False)
        self.declare_parameter("guard.geofence.allowed", [])  # 占位：允许的区域 ID 列表

        self.wakewords: List[str] = [str(x).lower() for x in self.get_parameter("guard.wakewords").value]
        self.sos_keywords: List[str] = [str(x).lower() for x in self.get_parameter("guard.sos_keywords").value]
        self.geofence_enabled: bool = bool(self.get_parameter("guard.geofence.enabled").value)
        self.geofence_allowed: List[str] = [str(x) for x in self.get_parameter("guard.geofence.allowed").value]

        # ---- QoS ----
        reliable_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=20,
        )

        # ---- 话题 ----
        self.sub_asr = self.create_subscription(
            SpeechResult, "/speech/recognized", self.on_asr, reliable_qos
        )
        self.pub_guard = self.create_publisher(
            String, "/guard/events", reliable_qos
        )

        self.get_logger().info(
            f"EnhancedGuardEngine ready: wakewords={self.wakewords}, sos={self.sos_keywords}, geofence={self.geofence_enabled}"
        )

    # ---------- 主回调 ----------
    def on_asr(self, msg: SpeechResult):
        try:
            text = (msg.text or "").strip()
            text_lower = text.lower()

            matches = {
                "wakeword": self._matched_any(text_lower, self.wakewords),
                "sos": self._matched_any(text_lower, self.sos_keywords),
                # 地理围栏占位（需要从定位/地图节点取位置信息，这里先返回 False）
                "geofence_violation": False,
            }

            event_type = None
            if matches["sos"]:
                event_type = "sos"
            elif matches["wakeword"]:
                event_type = "wake"
            elif matches["geofence_violation"]:
                event_type = "geofence"

            payload = {
                "type": event_type or "none",
                "matches": matches,
                "text": text,
                "language": getattr(msg, "language", ""),
                "confidence": float(getattr(msg, "confidence", 0.0)),
                "sample_rate": int(getattr(msg, "sample_rate", 16000)),
                "voice_activity_detected": bool(getattr(msg, "voice_activity_detected", False)),
                "ts": self.get_clock().now().nanoseconds / 1e9,
            }
            self.pub_guard.publish(String(data=json.dumps(payload, ensure_ascii=False)))

            # 关键事件在日志标注
            if event_type == "sos":
                self.get_logger().warning(f"[GUARD] SOS detected: {text}")
            elif event_type == "wake":
                self.get_logger().info(f"[GUARD] Wakeword: {text}")
            elif event_type == "geofence":
                self.get_logger().warning(f"[GUARD] Geofence violation (placeholder): {text}")

        except Exception as e:
            self.get_logger().error(f"on_asr error: {e}")

    # ---------- 工具 ----------
    @staticmethod
    def _matched_any(text_lower: str, keywords: List[str]) -> bool:
        for k in keywords:
            if not k:
                continue
            if k.lower() in text_lower:
                return True
        return False


def main(args=None):
    rclpy.init(args=args)
    node = EnhancedGuardEngine()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
