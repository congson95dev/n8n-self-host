import cv2
import numpy as np
import os
import subprocess
import tempfile
from collections import deque

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
    def _ensure_converted_h264_if_needed(path, tmp_dir=None, convert_on_fail=True):
        """Try open with OpenCV; if fail to read first frame and convert_on_fail True -> convert to H264 temp file."""
        cap = cv2.VideoCapture(path)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                cap.release()
                return path  # OK to use original
            cap.release()

        if not convert_on_fail:
            return None

        if tmp_dir is None:
            tmp_dir = tempfile.gettempdir()
        base = os.path.basename(path)
        tmp = os.path.join(tmp_dir, f"convert_h264_{base}")
        cmd = [
            "ffmpeg", "-y", "-i", path,
            "-c:v", "libx264", "-preset", "veryfast",
            "-an", tmp
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return tmp
        except subprocess.CalledProcessError:
            return None

    @staticmethod
    def detect_dynamic_segments(video_path):
        import subprocess
        import numpy as np
        import cv2
        import json

        # Step 1: get width/height/duration via ffprobe
        probe_cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_streams", "-select_streams", "v:0",
            video_path
        ]

        info = json.loads(subprocess.check_output(probe_cmd))
        stream = info["streams"][0]

        width = stream["width"]
        height = stream["height"]
        fps = eval(stream["r_frame_rate"])
        duration = float(stream["duration"])

        # Step 2: read raw frames using ffmpeg
        cmd = [
            "ffmpeg", "-v", "quiet",
            "-i", video_path,
            "-vf", f"scale={width}:{height}",
            "-f", "image2pipe",
            "-pix_fmt", "rgb24",
            "-vcodec", "rawvideo",
            "-"
        ]

        pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=10**8)

        segments = []
        last = None

        BRIGHTNESS_THRESHOLD = 18
        STD_THRESHOLD = 2

        frame_size = width * height * 3
        frame_idx = 0

        while True:
            raw = pipe.stdout.read(frame_size)
            if len(raw) < frame_size:
                break

            frame = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3))
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

            row_means = gray.mean(axis=1)
            row_stds = gray.std(axis=1)

            dark_rows = row_means < BRIGHTNESS_THRESHOLD
            static_rows = row_stds < STD_THRESHOLD

            row_mask = dark_rows | static_rows
            mask = (row_mask.astype(np.uint8) * 255).reshape(-1,1)

            kernel = np.ones((7,1), np.uint8)
            clean = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel).flatten() > 0

            # top bar
            if clean[0]:
                y_top = int(np.argmax(clean == False))
            else:
                y_top = 0

            # bottom bar
            if clean[-1]:
                y_bottom = int(np.argmax(clean[::-1] == False))
            else:
                y_bottom = 0

            timestamp = frame_idx / fps
            current = {
                "start": timestamp,
                "end": timestamp,
                "y_top": int(y_top),
                "y_bottom": int(y_bottom)
            }

            if last is None:
                last = current
            else:
                if (
                    abs(current["y_top"] - last["y_top"]) <= 2 and
                    abs(current["y_bottom"] - last["y_bottom"]) <= 2
                ):
                    last["end"] = current["end"]
                else:
                    last["end"] = min(last["end"], duration)
                    segments.append(last)
                    last = current

            frame_idx += 1

        pipe.stdout.close()

        if last:
            last["end"] = min(last["end"], duration)
            segments.append(last)

        return {"segments": segments}

    def detect_bar_from_mask_video_less_than_1s(video_path,
                                                motion_thresh=2.5,
                                                stable_std_thresh=5.0):
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"error": "cannot open video"}

        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if frame_count < 2:
            return {"error": "not enough frames"}

        # Lấy 3 frames: đầu – giữa – cuối
        idxs = sorted(set([0, frame_count//2, frame_count-1]))
        frames = []
        for idx in idxs:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, fr = cap.read()
            if not ret:
                continue
            gray = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
            frames.append(gray)
        cap.release()

        if len(frames) < 2:
            return {"error": "not enough frames"}

        # unify size
        h = min(f.shape[0] for f in frames)
        w = min(f.shape[1] for f in frames)
        frames = [f[:h, :w] for f in frames]

        # 1. motion per row
        motions = []
        for i in range(len(frames)-1):
            diff = cv2.absdiff(frames[i], frames[i+1]).astype(np.float32)
            motions.append(np.mean(diff, axis=1))
        motions = np.max(np.stack(motions), axis=0)

        # 2. brightness stability per row
        row_means = np.stack([np.mean(f, axis=1) for f in frames])
        row_std = np.std(row_means, axis=0)

        # 3. static mask: motion thấp + brightness ổn định
        static_mask = (motions < motion_thresh) & (row_std < stable_std_thresh)

        # Morphology để làm mịn mask
        static_u8 = (static_mask.astype(np.uint8) * 255)
        kernel = np.ones((9,1), np.uint8)
        clean = cv2.morphologyEx(static_u8.reshape(-1,1), cv2.MORPH_CLOSE, kernel)
        clean = clean.flatten() > 0

        # detect y_top
        y_top = 0
        for i in range(h):
            if clean[i]:
                y_top += 1
            else:
                break

        # detect y_bottom
        y_bottom = 0
        for i in range(h-1, -1, -1):
            if clean[i]:
                y_bottom += 1
            else:
                break

        return {
            "y_top": int(y_top),
            "y_bottom": int(y_bottom),
            "height": h,
            "motion_thresh": motion_thresh,
            "stable_std_thresh": stable_std_thresh
        }

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

        if version == 3:
            segments = VideoBarDetector.detect_dynamic_segments(video_path)
            return segments
        elif (version == 4):
            bar = VideoBarDetector.detect_bar_from_mask_video_less_than_1s(video_path)
            suggested_crop_height = height - bar["y_top"] - bar["y_bottom"] if bar["y_top"] is not None else None
            bar.update({"suggested_crop_height": suggested_crop_height})
            return bar

        frames = VideoBarDetector.get_frames(video_path, [0, 1, 2])
        if len(frames) < 2:
            # Error when detect frame => Convert video to mp4/h264 then detect frame again
            dir_orig = "/tmp/download/"
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
