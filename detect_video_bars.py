import cv2
import numpy as np
import os

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
    def detect_bar_with_fallback(frames, mask_static,
                             diff_threshold=20,
                             brightness_threshold=30,
                             static_ratio_threshold=0.99,
                             min_consecutive=3,
                             max_bar_ratio=0.5):
        if not frames:
            return 0, 0

        h, w = frames[0].shape[:2]

        # --- 1) Brightness: median of per-row means across frames (robust) ---
        gray_frames = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
        row_means = np.array([np.mean(g, axis=1) for g in gray_frames])  # shape (F, h)
        median_row_means = np.median(row_means, axis=0)  # length h
        brightness_mask = median_row_means < brightness_threshold  # True if likely black

        # --- 2) Static: derive per-row static proportion from mask_static if provided ---
        if mask_static is not None:
            # mask_static: True = static pixel
            row_static_prop = np.mean(mask_static, axis=1)  # proportion per row
            static_mask = row_static_prop >= static_ratio_threshold
        else:
            static_mask = np.zeros((h,), dtype=bool)

        # --- 3) Combine heuristics ---
        combined = brightness_mask | static_mask

        # Helper: find contiguous True count from top and bottom (must be >= min_consecutive)
        def contiguous_from_top(arr):
            cnt = 0
            for v in arr:
                if v:
                    cnt += 1
                else:
                    if cnt > 0:
                        break
            return cnt

        def contiguous_from_bottom(arr):
            cnt = 0
            for v in arr[::-1]:
                if v:
                    cnt += 1
                else:
                    if cnt > 0:
                        break
            return cnt

        top = contiguous_from_top(combined)
        bottom = contiguous_from_bottom(combined)

        # If combined gives too small runs (<min_consecutive), try brightness-only contiguous
        if top < min_consecutive and bottom < min_consecutive:
            top = contiguous_from_top(brightness_mask)
            bottom = contiguous_from_bottom(brightness_mask)

        total_bar = top + bottom

        # If total_bar is suspiciously large, fallback to brightness-only
        if total_bar > int(max_bar_ratio * h):
            top = contiguous_from_top(brightness_mask)
            bottom = contiguous_from_bottom(brightness_mask)

        # Final sanity: ensure ints and not exceed h
        top = int(max(0, min(top, h-1)))
        bottom = int(max(0, min(bottom, h-1 - top)))

        return {"y_top": top, "y_bottom": bottom}

    @staticmethod
    def main(video_path, version=1):
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
            # Error when detect frame => Convert video to mp4/h264 then detect frame again
            dir_orig = os.path.dirname(video_path)
            base = os.path.basename(video_path)
            name, ext = os.path.splitext(base)
            converted_name = f"convert-mp4-{name}.mp4"
            tmp = os.path.join(dir_orig, converted_name)
            cmd = f"ffmpeg -y -i \"{video_path}\" -c:v libx264 -preset veryfast -c:a copy \"{tmp}\""
            ret = os.system(cmd)
            if ret != 0:
                result["error"] = "Không thể convert video qua codec hỗ trợ. Không lấy đủ frames để detect."
                return result
            # Detect frame again
            frames = VideoBarDetector.get_frames(tmp, [0, 1, 2])
            if len(frames) < 2:
                result["error"] = "Not enough frames to detect."
                return result

        mask_static = VideoBarDetector.compute_static_mask(frames, diff_threshold=20)
        if (version == 1):
            bar = VideoBarDetector.detect_bar_from_mask(mask_static)
        elif (version == 2):
            bar = VideoBarDetector.detect_bar_with_fallback(frames, mask_static)

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
