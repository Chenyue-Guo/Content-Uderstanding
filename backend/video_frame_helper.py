from __future__ import annotations

import io
import re
from datetime import datetime
from typing import Optional, Tuple, List


class VideoFrameHelper:
    """
    负责选帧、抽帧、时间格式化等逻辑的工具类。

    **新增功能** ``extract_timestamp`` —— 使用 easyOCR 进行文字识别。

    示例::
        vf = VideoFrameHelper(
            key_times=contents["KeyFrameTimesMs"],
            content_client=content_client,
            operation_id=result["id"],
            video_path=tmp_path,
        )
        bbox = (1620, 900, 1910, 1000)  # 时间标签所在矩形区域
        dt = vf.extract_timestamp(time_ms=15_000, bbox=bbox)
        print(dt)  # datetime(2025, 1, 30, 15, 21)
    """

    # ---------------------------------------------------------
    # 初始化
    # ---------------------------------------------------------
    def __init__(
        self,
        *,
        key_times,
        content_client,
        operation_id: str,
        video_path: str,
    ) -> None:
        self.key_times = key_times
        self.client = content_client  # 仍用于获取帧，不再用于 OCR
        self.operation_id = operation_id
        self.video_path = video_path

        # ---------- 依赖检测 ----------
        try:
            import cv2  # type: ignore

            self.cv2 = cv2
        except ImportError:
            self.cv2 = None

        try:
            import easyocr  # type: ignore
            from PIL import Image  # type: ignore

            self.easyocr = easyocr
            self.Image = Image
            # 初始化 easyOCR reader，支持中文和英文
            self.reader = easyocr.Reader(['ch_sim', 'en'])
        except ImportError:
            self.easyocr = None
            self.Image = None
            self.reader = None

    # ---------------------------------------------------------
    # 公共 API
    # ---------------------------------------------------------
    def get_segment_preview(self, start_ms: int, end_ms: int) -> Optional[bytes]:
        """给一个段落区间，返回一张代表帧（jpg bytes）。"""
        t = self._pick_key_time(start_ms, end_ms)
        return self._fetch_frame(t)

    def ts(self, ms: int) -> str:
        """毫秒 → 00:00.000 字符串（方便别处调用）"""
        return self._ms_to_ts(ms)

    def extract_text_from_frame(
        self,
        *,
        time_ms: int,
        bbox: Optional[Tuple[int, int, int, int]] = None,
    ) -> List[str]:
        """从指定时间点的帧中提取文字信息。

        参数
        ----
        time_ms : int
            帧的毫秒时间戳。
        bbox : (x1, y1, x2, y2) | None
            需要裁剪的矩形区域，如果为None则处理整个帧。

        返回
        ----
        List[str]
            识别到的文字列表
        """
        if not (self.easyocr and self.Image and self.reader):
            # 未安装 easyOCR 依赖
            return []

        # 1. 获取帧
        img_bytes = self._fetch_frame(time_ms)
        if not img_bytes:
            return []

        # 2. 转换为PIL图像
        img = self.Image.open(io.BytesIO(img_bytes))
        
        # 3. 裁剪到指定区域（如果提供）
        if bbox:
            x1, y1, x2, y2 = bbox
            img = img.crop((x1, y1, x2, y2))

        # 4. 转换为numpy数组
        import numpy as np
        img_array = np.array(img)

        # 5. easyOCR 识别
        try:
            results = self.reader.readtext(img_array)
            # 提取文字内容
            texts = [text[1] for text in results]
            return texts
        except Exception as e:
            print(f"OCR识别出错: {e}")
            return []

    def extract_timestamp(
        self,
        *,
        time_ms: int,
        bbox: Tuple[int, int, int, int],
    ) -> Optional[datetime]:
        """从指定时间点、指定像素区域提取"YYYY年M月D日 HH:MM(:SS)"时间标签。

        参数
        ----
        time_ms : int
            帧的毫秒时间戳。
        bbox : (x1, y1, x2, y2)
            需要裁剪的矩形区域。

        返回
        ----
        datetime | None
        """
        texts = self.extract_text_from_frame(time_ms=time_ms, bbox=bbox)
        if not texts:
            return None

        # 合并所有识别到的文字
        full_text = " ".join(texts)
        
        # 解析时间标签
        return self._parse_timestamp(full_text)

    def extract_datetime_info(
        self,
        *,
        time_ms: int,
        bbox: Tuple[int, int, int, int],
    ) -> Optional[datetime]:
        """从指定时间点、指定像素区域提取"YYYY-MM-DD HH:MM:SS"格式的时间信息。

        参数
        ----
        time_ms : int
            帧的毫秒时间戳。
        bbox : (x1, y1, x2, y2)
            需要裁剪的矩形区域。

        返回
        ----
        datetime | None
        """
        texts = self.extract_text_from_frame(time_ms=time_ms, bbox=bbox)
        if not texts:
            return None

        # 合并所有识别到的文字
        full_text = " ".join(texts)
        
        # 解析时间信息
        return self._parse_datetime_info(full_text)

    # ---------------------------------------------------------
    # 私有工具方法
    # ---------------------------------------------------------
    def _pick_key_time(self, start: int, end: int) -> int:
        in_seg = [t for t in self.key_times if start <= t <= end]
        return in_seg[0] if in_seg else (start + end) // 2

    def _fetch_frame(self, time_ms: int) -> Optional[bytes]:
        """先尝试 Azure Content Safety 抽帧，再回退 OpenCV。"""
        # 1. Azure API
        try:
            data = self.client.get_frame(
                operation_id=self.operation_id,
                time_ms=time_ms,
            )
            if isinstance(data, dict) and "data" in data:
                import base64

                return base64.b64decode(data["data"])
        except Exception:
            pass

        # 2. OpenCV 回退
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

    # ---------------------------------------------------------
    # 时间标签解析
    # ---------------------------------------------------------
    @staticmethod
    def _parse_timestamp(text: str) -> Optional[datetime]:
        text = text.strip().replace("\n", " ")
        pattern = (
            r"(?P<year>\d{4})年\s*"
            r"(?P<month>\d{1,2})月\s*"
            r"(?P<day>\d{1,2})日\s*"
            r"(?P<hour>\d{1,2})[：:]"
            r"(?P<minute>\d{1,2})"
            r"(?:[：:](?P<second>\d{1,2}))?"
        )
        m = re.search(pattern, text)
        if not m:
            return None

        gd = m.groupdict(default="0")
        try:
            return datetime(
                int(gd["year"]),
                int(gd["month"]),
                int(gd["day"]),
                int(gd["hour"]),
                int(gd["minute"]),
                int(gd["second"]),
            )
        except ValueError:
            return None

    @staticmethod
    def _parse_datetime_info(text: str) -> Optional[datetime]:
        """解析"YYYY-MM-DD HH:MM:SS"格式的时间信息。"""
        text = text.strip().replace("\n", " ")
        
        # 支持多种格式的正则表达式
        patterns = [
            # YYYY-MM-DD HH:MM:SS
            r"(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})\s+(?P<hour>\d{1,2}):(?P<minute>\d{1,2}):(?P<second>\d{1,2})",
            # YYYY-MM-DD HH:MM
            r"(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})\s+(?P<hour>\d{1,2}):(?P<minute>\d{1,2})",
            # YYYY/MM/DD HH:MM:SS
            r"(?P<year>\d{4})/(?P<month>\d{1,2})/(?P<day>\d{1,2})\s+(?P<hour>\d{1,2}):(?P<minute>\d{1,2}):(?P<second>\d{1,2})",
            # YYYY/MM/DD HH:MM
            r"(?P<year>\d{4})/(?P<month>\d{1,2})/(?P<day>\d{1,2})\s+(?P<hour>\d{1,2}):(?P<minute>\d{1,2})",
        ]
        
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                gd = m.groupdict(default="0")
                try:
                    return datetime(
                        int(gd["year"]),
                        int(gd["month"]),
                        int(gd["day"]),
                        int(gd["hour"]),
                        int(gd["minute"]),
                        int(gd.get("second", "0")),
                    )
                except ValueError:
                    continue
        
        return None
