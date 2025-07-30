

class VideoFrameHelper:
    """
    负责选帧、抽帧、时间格式化等逻辑的工具类。
    用法：
        vf = VideoFrameHelper(
            key_times=contents["KeyFrameTimesMs"],
            content_client=content_client,
            operation_id=result["id"],
            video_path=tmp_path
        )
        img_bytes = vf.get_segment_preview(start_ms, end_ms)
    """

    def __init__(self, *, key_times, content_client,
                 operation_id: str, video_path: str):
        self.key_times = key_times
        self.client = content_client
        self.operation_id = operation_id
        self.video_path = video_path
        try:
            import cv2
            self.cv2 = cv2            # 若本地有安装 OpenCV
        except ImportError:
            self.cv2 = None

    # ---------- 公共 API ----------
    def get_segment_preview(self, start_ms: int, end_ms: int) -> bytes | None:
        """给一个段落区间，返回一张代表帧（jpg bytes）。"""
        t = self._pick_key_time(start_ms, end_ms)
        return self._fetch_frame(t)

    def ts(self, ms: int) -> str:
        """毫秒 → 00:00.000 字符串（方便别处调用）"""
        return self._ms_to_ts(ms)

    # ---------- 私有方法 ----------
    def _pick_key_time(self, start: int, end: int) -> int:
        in_seg = [t for t in self.key_times if start <= t <= end]
        return in_seg[0] if in_seg else (start + end) // 2

    def _fetch_frame(self, time_ms: int) -> bytes | None:
        # 1. Azure API
        try:
            data = self.client.get_frame(
                operation_id=self.operation_id,
                time_ms=time_ms
            )
            if isinstance(data, dict) and "data" in data:
                import base64
                return base64.b64decode(data["data"])
        except Exception:
            pass

        # 2. Fallback: OpenCV
        if not self.cv2:
            return None
        try:
            cap = self.cv2.VideoCapture(self.video_path)
            cap.set(self.cv2.CAP_PROP_POS_MSEC, time_ms)
            ok, frame = cap.read()
            cap.release()
            if ok and frame is not None:
                _, buf = self.cv2.imencode(".jpg", frame)
                return buf.tobytes()
        except Exception:
            pass
        return None

    @staticmethod
    def _ms_to_ts(ms: int) -> str:
        s, ms = divmod(ms, 1000)
        m, s = divmod(s, 60)
        return f"{m:02d}:{s:02d}.{ms:03d}"