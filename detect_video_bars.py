import cv2
import numpy as np
import os
import sys

class VideoBarDetector:
    @staticmethod
    def get_frames(video_path, times):
        cap = cv2.VideoCapture(video_path)
        frames = []
        for t in times:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ret, frame = cap.read()
            if not ret:
                continue
            frames.append(frame)
        cap.release()
        return frames

    @staticmethod
    def compute_static_mask(frames, diff_threshold=10):
        if not frames or len(frames) < 2:
            return None
        h, w, _ = frames[0].shape
        static_mask = np.ones((h, w), dtype=bool)
        for i in range(1, len(frames)):
            diff = cv2.absdiff(frames[i], frames[i-1])
            gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            mask_change = gray > diff_threshold
            static_mask = static_mask & (~mask_change)
        return static_mask

    @staticmethod
    def detect_bar_from_mask(mask, min_static_ratio_row=0.99):
        if mask is None:
            return {"y_top": None, "y_bottom": None}
        h, w = mask.shape
        y_top = 0
        for y in range(h):
            row = mask[y, :]
            if np.sum(row) / w < min_static_ratio_row:
                y_top = y
                break
        y_bottom = 0
        for y in range(h-1, -1, -1):
            row = mask[y, :]
            if np.sum(row) / w < min_static_ratio_row:
                y_bottom = h - 1 - y
                break
        return {"y_top": y_top, "y_bottom": y_bottom}

    @staticmethod
    def main(video_path):
        result = {}
        if not os.path.exists(video_path):
            result["error"] = f"Video file does not exist: {video_path}"
            return result

        cap0 = cv2.VideoCapture(video_path)
        if not cap0.isOpened():
            result["error"] = f"Cannot open video: {video_path}"
            return result

        width = int(cap0.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap0.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap0.release()

        frames = VideoBarDetector.get_frames(video_path, [0, 1, 2])
        if len(frames) < 2:
            result["error"] = "Not enough frames to detect."
            result["width"] = width
            result["height"] = height
            return result

        mask_static = VideoBarDetector.compute_static_mask(frames, diff_threshold=20)
        bar = VideoBarDetector.detect_bar_from_mask(mask_static)
        suggested_crop_height = height - bar["y_top"] - bar["y_bottom"] if bar["y_top"] is not None else None

        result.update({
            "video_path": video_path,
            "width": width,
            "height": height,
            "y_top": bar["y_top"],
            "y_bottom": bar["y_bottom"],
            "suggested_crop_height": suggested_crop_height
        })
        return result
