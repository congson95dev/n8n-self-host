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
        cap = cv2.VideoCapture(path)
        if cap.isOpened():
            ret, _ = cap.read()
            cap.release()
            if ret:
                return path
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
    def detect_dynamic_segments(video_path,
                                   sample_rate_sec=0.25,
                                   sliding_win_seconds=1.0,
                                   brightness_thresh=None,
                                   static_std_thresh=3.0,
                                   diff_px_tolerance=6,
                                   min_segment_duration=0.3,
                                   merge_gap_seconds=0.25,
                                   min_detect_rows=2,
                                   convert_on_fail=True,
                                   debug=False):
        if not os.path.exists(video_path):
            return {"error": "file not found"}

        usable_path = VideoBarDetector._ensure_converted_h264_if_needed(video_path, convert_on_fail=convert_on_fail)
        if usable_path is None:
            return {"error": "cannot open video and conversion failed"}

        cap = cv2.VideoCapture(usable_path)
        if not cap.isOpened():
            return {"error": "cannot open video after conversion"}

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) if cap.get(cv2.CAP_PROP_FRAME_COUNT) else None

        # compute numeric duration safely
        if frame_count and fps and fps > 0:
            total_duration = frame_count / fps
        else:
            # fallback: try reading video length via CAP_PROP_POS_MSEC by seeking to end
            total_duration = None
            try:
                cap.set(cv2.CAP_PROP_POS_AVI_RATIO, 1.0)
                # read current position in ms
                ms = cap.get(cv2.CAP_PROP_POS_MSEC)
                if ms and ms > 0:
                    total_duration = ms / 1000.0
            except Exception:
                total_duration = None
            # reset position
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        win_len = max(1, int(round(sliding_win_seconds / sample_rate_sec)))
        row_means_win = deque(maxlen=win_len)
        row_stds_win = deque(maxlen=win_len)

        t = 0.0
        sampled = []
        height = None
        width = None

        # sample loop
        while True:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
            ret, frame = cap.read()
            if not ret:
                break

            if height is None:
                height, width = frame.shape[:2]

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray_blur = cv2.GaussianBlur(gray, (5,5), 0)

            row_means = np.mean(gray_blur, axis=1)
            row_stds = np.std(gray_blur, axis=1)

            row_means_win.append(row_means)
            row_stds_win.append(row_stds)

            median_row_means = np.median(np.stack(list(row_means_win)), axis=0)
            median_row_stds = np.median(np.stack(list(row_stds_win)), axis=0)

            if brightness_thresh is None:
                global_median = float(np.median(median_row_means))
                brightness_thresh_local = min(80, max(20, int(global_median * 0.9)))
            else:
                brightness_thresh_local = brightness_thresh
                global_median = float(np.median(median_row_means))

            dark_rows = median_row_means < brightness_thresh_local
            static_rows = median_row_stds < static_std_thresh
            row_mask = dark_rows | static_rows

            mask_u8 = row_mask.astype(np.uint8)
            kernel = max(1, int(round(0.02 * height)))
            conv = np.convolve(mask_u8, np.ones(kernel, dtype=int), mode='same')
            mask_smooth = conv > 0

            def contiguous_from_top_bool(arr):
                cnt = 0
                for v in arr:
                    if v:
                        cnt += 1
                    elif cnt>0:
                        break
                return cnt
            def contiguous_from_bottom_bool(arr):
                cnt = 0
                for v in arr[::-1]:
                    if v:
                        cnt += 1
                    elif cnt>0:
                        break
                return cnt

            y_top = contiguous_from_top_bool(mask_smooth)
            y_bottom = contiguous_from_bottom_bool(mask_smooth)

            if y_top < min_detect_rows:
                y_top = 0
            if y_bottom < min_detect_rows:
                y_bottom = 0

            def quantize(v):
                return int(max(0, (v//2)*2))
            y_top_q = quantize(y_top)
            y_bottom_q = quantize(y_bottom)

            sampled.append({
                "time": t,
                "y_top": y_top_q,
                "y_bottom": y_bottom_q,
                "brightness_thresh": float(brightness_thresh_local),
                "global_median": float(global_median)
            })

            t += sample_rate_sec
            if total_duration and t > total_duration + 0.0001:
                break
            if t > 100000:
                break

        cap.release()

        if len(sampled) == 0:
            return {"segments": [], "error": "no samples (maybe cannot read frames)"}

        # Group consecutive samples
        segments = []
        cur = None
        for s in sampled:
            bar = (s["y_top"], s["y_bottom"])
            if cur is None:
                cur = {"start": s["time"], "end": s["time"] + sample_rate_sec, "y_top": bar[0], "y_bottom": bar[1]}
            else:
                if abs(bar[0] - cur["y_top"]) <= diff_px_tolerance and abs(bar[1] - cur["y_bottom"]) <= diff_px_tolerance:
                    cur["end"] = s["time"] + sample_rate_sec
                    cur["y_top"] = int(round((cur["y_top"] + bar[0]) / 2.0))
                    cur["y_bottom"] = int(round((cur["y_bottom"] + bar[1]) / 2.0))
                else:
                    segments.append(cur)
                    cur = {"start": s["time"], "end": s["time"] + sample_rate_sec, "y_top": bar[0], "y_bottom": bar[1]}
        if cur:
            segments.append(cur)

        # helper renamed to avoid shadowing numeric total_duration
        def seg_duration(seg): 
            return seg["end"] - seg["start"]

        merged = []
        i = 0
        while i < len(segments):
            seg = segments[i]
            if seg_duration(seg) < min_segment_duration:
                if merged:
                    merged[-1]["end"] = seg["end"]
                    merged[-1]["y_top"] = int(round((merged[-1]["y_top"] + seg["y_top"]) / 2.0))
                    merged[-1]["y_bottom"] = int(round((merged[-1]["y_bottom"] + seg["y_bottom"]) / 2.0))
                elif i + 1 < len(segments):
                    segments[i+1]["start"] = seg["start"]
                    segments[i+1]["y_top"] = int(round((segments[i+1]["y_top"] + seg["y_top"]) / 2.0))
                    segments[i+1]["y_bottom"] = int(round((segments[i+1]["y_bottom"] + seg["y_bottom"]) / 2.0))
                else:
                    merged.append(seg)
            else:
                merged.append(seg)
            i += 1

        out = []
        for seg in merged:
            if not out:
                out.append(seg)
            else:
                prev = out[-1]
                gap = seg["start"] - prev["end"]
                if gap <= merge_gap_seconds and abs(seg["y_top"] - prev["y_top"]) <= diff_px_tolerance and abs(seg["y_bottom"] - prev["y_bottom"]) <= diff_px_tolerance:
                    prev["end"] = seg["end"]
                    prev["y_top"] = int(round((prev["y_top"] + seg["y_top"]) / 2.0))
                    prev["y_bottom"] = int(round((prev["y_bottom"] + seg["y_bottom"]) / 2.0))
                else:
                    out.append(seg)

        # clamp to video duration if available and ensure numeric
        for o in out:
            o["start"] = float(max(0.0, float(o["start"])))
            if total_duration:
                o["end"] = float(min(total_duration, float(o["end"])))
            else:
                o["end"] = float(o["end"])

        res = {"segments": out}
        if debug:
            res["debug"] = {"sample_rate_sec": sample_rate_sec, "samples": sampled[:200], "height": height, "width": width, "total_duration": total_duration}
        return res

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
