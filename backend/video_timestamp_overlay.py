import cv2
import numpy as np
from datetime import datetime, timedelta
from typing import Tuple, Optional, Union
import os
from PIL import Image, ImageDraw, ImageFont


class VideoTimestampOverlay:
    """
    在视频中添加时间标签的工具类。
    
    功能：
    - 在视频的指定位置添加"XXXX年XX月XX日 XX:XX"格式的时间标签
    - 时间标签会随着视频时长递增
    - 支持自定义字体、颜色、位置等参数
    
    示例：
        overlay = VideoTimestampOverlay(
            start_datetime=datetime(2024, 1, 1, 10, 0, 0),
            position=(50, 50),
            font_size=2.0,
            font_color=(255, 255, 255),
            font_thickness=2
        )
        overlay.add_timestamps_to_video("input.mp4", "output.mp4")
    """
    
    def __init__(
        self,
        start_datetime: datetime,
        position: Tuple[int, int] = (50, 50),
        font_size: float = 2.0,
        font_color: Tuple[int, int, int] = (255, 255, 255),
        font_thickness: int = 2,
        background_color: Optional[Tuple[int, int, int]] = None,
        background_padding: int = 10,
        update_interval_seconds: int = 60
    ):
        """
        初始化时间标签叠加器。
        
        参数：
            start_datetime: 视频开始时间
            position: 时间标签在视频中的位置 (x, y)
            font_size: 字体大小
            font_color: 字体颜色 (B, G, R)
            font_thickness: 字体粗细
            background_color: 背景颜色，None表示无背景
            background_padding: 背景内边距
            update_interval_seconds: 时间标签更新间隔（秒）
        """
        self.start_datetime = start_datetime
        self.position = position
        self.font_size = font_size
        self.font_color = font_color
        self.font_thickness = font_thickness
        self.background_color = background_color
        self.background_padding = background_padding
        self.update_interval_seconds = update_interval_seconds
        
        # 字体设置
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        
    def _format_timestamp(self, dt: datetime) -> str:
        """
        格式化时间标签为"XXXX年XX月XX日 XX:XX"格式。
        """
        return dt.strftime("%Y年%m月%d日 %H:%M")
    
    def _calculate_current_time(self, video_time_seconds: float) -> datetime:
        """
        根据视频时间计算当前应该显示的时间。
        """
        # 计算时间间隔数
        interval_count = int(video_time_seconds // self.update_interval_seconds)
        # 计算当前时间
        current_time = self.start_datetime + timedelta(seconds=interval_count * self.update_interval_seconds)
        return current_time
    

    
    def _draw_text_with_background(
        self, 
        frame: np.ndarray, 
        text: str, 
        position: Tuple[int, int]
    ) -> np.ndarray:
        """
        在帧上绘制带背景的文本。
        """
        frame_copy = frame.copy()
        
        # 将OpenCV的BGR格式转换为PIL的RGB格式
        frame_rgb = cv2.cvtColor(frame_copy, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(frame_rgb)
        draw = ImageDraw.Draw(pil_image)
        
        # 尝试加载中文字体，如果失败则使用默认字体
        try:
            # 尝试使用系统中文字体
            font = ImageFont.truetype("simhei.ttf", int(self.font_size * 20))  # 调整字体大小
        except:
            try:
                # 尝试其他中文字体
                font = ImageFont.truetype("msyh.ttc", int(self.font_size * 20))
            except:
                # 使用默认字体
                font = ImageFont.load_default()
        
        # 获取文本尺寸
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # 计算背景矩形
        x, y = position
        bg_x1 = x - self.background_padding
        bg_y1 = y - text_height - self.background_padding
        bg_x2 = x + text_width + self.background_padding
        bg_y2 = y + self.background_padding
        
        # 绘制背景
        if self.background_color:
            # 转换颜色格式从BGR到RGB
            bg_color_rgb = (self.background_color[2], self.background_color[1], self.background_color[0])
            draw.rectangle([bg_x1, bg_y1, bg_x2, bg_y2], fill=bg_color_rgb)
        
        # 绘制文本
        # 转换颜色格式从BGR到RGB
        text_color_rgb = (self.font_color[2], self.font_color[1], self.font_color[0])
        draw.text(position, text, fill=text_color_rgb, font=font)
        
        # 将PIL图像转换回OpenCV格式
        result_rgb = np.array(pil_image)
        result_bgr = cv2.cvtColor(result_rgb, cv2.COLOR_RGB2BGR)
        
        return result_bgr
    
    def add_timestamps_to_video(
        self, 
        input_path: str, 
        output_path: str,
        progress_callback: Optional[callable] = None
    ) -> bool:
        """
        为视频添加时间标签。
        
        参数：
            input_path: 输入视频路径
            output_path: 输出视频路径
            progress_callback: 进度回调函数，接收当前帧数和总帧数
            
        返回：
            bool: 是否成功
        """
        try:
            # 打开输入视频
            cap = cv2.VideoCapture(input_path)
            if not cap.isOpened():
                print(f"无法打开视频文件: {input_path}")
                return False
            
            # 获取视频属性
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # 创建视频写入器
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            
            frame_count = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # 计算当前视频时间（秒）
                current_time_seconds = frame_count / fps
                
                # 计算当前应该显示的时间标签
                current_datetime = self._calculate_current_time(current_time_seconds)
                current_timestamp = self._format_timestamp(current_datetime)
                
                # 绘制时间标签（每帧都绘制）
                frame = self._draw_text_with_background(frame, current_timestamp, self.position)
                
                # 写入帧
                out.write(frame)
                frame_count += 1
                
                # 调用进度回调
                if progress_callback:
                    progress_callback(frame_count, total_frames)
            
            # 释放资源
            cap.release()
            out.release()
            
            return True
            
        except Exception as e:
            print(f"处理视频时发生错误: {str(e)}")
            return False
    
    def add_timestamps_to_video_segment(
        self,
        input_path: str,
        output_path: str,
        start_time_seconds: float = 0,
        end_time_seconds: Optional[float] = None,
        progress_callback: Optional[callable] = None
    ) -> bool:
        """
        为视频片段添加时间标签。
        
        参数：
            input_path: 输入视频路径
            output_path: 输出视频路径
            start_time_seconds: 开始时间（秒）
            end_time_seconds: 结束时间（秒），None表示到视频结尾
            progress_callback: 进度回调函数
            
        返回：
            bool: 是否成功
        """
        try:
            # 打开输入视频
            cap = cv2.VideoCapture(input_path)
            if not cap.isOpened():
                print(f"无法打开视频文件: {input_path}")
                return False
            
            # 获取视频属性
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # 计算帧范围
            start_frame = int(start_time_seconds * fps)
            if end_time_seconds is None:
                end_frame = total_frames
            else:
                end_frame = int(end_time_seconds * fps)
            
            # 创建视频写入器
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            
            # 跳转到开始帧
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            
            frame_count = start_frame
            
            while frame_count < end_frame:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # 计算当前视频时间（秒）
                current_time_seconds = frame_count / fps
                
                # 计算当前应该显示的时间标签
                current_datetime = self._calculate_current_time(current_time_seconds)
                current_timestamp = self._format_timestamp(current_datetime)
                
                # 绘制时间标签（每帧都绘制）
                frame = self._draw_text_with_background(frame, current_timestamp, self.position)
                
                # 写入帧
                out.write(frame)
                frame_count += 1
                
                # 调用进度回调
                if progress_callback:
                    progress_callback(frame_count - start_frame, end_frame - start_frame)
            
            # 释放资源
            cap.release()
            out.release()
            
            return True
            
        except Exception as e:
            print(f"处理视频片段时发生错误: {str(e)}")
            return False
    
    def preview_timestamp_at_time(
        self, 
        input_path: str, 
        time_seconds: float,
        output_path: Optional[str] = None
    ) -> Optional[np.ndarray]:
        """
        预览指定时间点的时间标签效果。
        
        参数：
            input_path: 输入视频路径
            time_seconds: 预览时间点（秒）
            output_path: 输出图片路径，None表示不保存
            
        返回：
            np.ndarray: 带时间标签的帧图像
        """
        try:
            cap = cv2.VideoCapture(input_path)
            if not cap.isOpened():
                print(f"无法打开视频文件: {input_path}")
                return None
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            target_frame = int(time_seconds * fps)
            
            # 确保目标帧在有效范围内
            if target_frame >= total_frames:
                target_frame = total_frames - 1
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                print(f"无法读取指定时间点的帧")
                return None
            
            # 计算当前时间标签
            current_datetime = self._calculate_current_time(time_seconds)
            current_timestamp = self._format_timestamp(current_datetime)
            
            # 添加时间标签
            result_frame = self._draw_text_with_background(frame, current_timestamp, self.position)
            
            # 保存图片（如果指定了输出路径）
            if output_path:
                cv2.imwrite(output_path, result_frame)
            
            return result_frame
            
        except Exception as e:
            print(f"预览时间标签时发生错误: {str(e)}")
            return None 