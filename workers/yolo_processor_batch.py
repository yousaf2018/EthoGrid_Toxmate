# EthoGrid_App/workers/yolo_processor.py

import os
import csv
import cv2
import traceback
from PyQt5.QtCore import QThread, pyqtSignal
from core.stopwatch import Stopwatch

try:
    import numpy as np
    from ultralytics import YOLO
except ImportError:
    YOLO, np = None, None


class YoloProcessor(QThread):
    overall_progress = pyqtSignal(int, int, str)
    file_progress = pyqtSignal(int, int, int)
    log_message = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    time_updated = pyqtSignal(str, str)
    speed_updated = pyqtSignal(float)

    def __init__(self, video_files, model_path, output_dir, confidence, save_video, save_csv, parent=None):
        super().__init__(parent)
        self.video_files = video_files
        self.model_path = model_path
        self.output_dir = output_dir
        self.confidence = confidence
        self.save_video = save_video
        self.save_csv = save_csv
        self.is_running = True

    def stop(self):
        self.log_message.emit("Stopping inference process...")
        self.is_running = False

    def run(self):
        if YOLO is None or np is None:
            self.error.emit("Dependencies not found. Please run: pip install ultralytics numpy")
            return

        try:
            self.log_message.emit(f"Loading YOLO model from: {self.model_path}")
            model = YOLO(self.model_path)
            self.log_message.emit("Model loaded successfully.")
        except Exception as e:
            self.error.emit(f"Failed to load YOLO model: {e}")
            return

        # Try GPU
        use_cuda = False
        try:
            import torch
            if torch.cuda.is_available():
                try:
                    model.to("cuda")
                    use_cuda = True
                    self.log_message.emit("Using CUDA for inference.")
                except Exception:
                    use_cuda = True
                    self.log_message.emit("CUDA available, using device='cuda' for predict.")
            else:
                self.log_message.emit("CUDA not available — using CPU.")
        except Exception:
            self.log_message.emit("torch not found — defaulting to CPU.")

        # Prepare class colors
        class_names = model.names
        class_colors = {}
        for i, name in class_names.items():
            np.random.seed(i + 5)
            color = tuple(np.random.randint(60, 255, size=3).tolist())
            class_colors[name] = color

        centroid_color = (0, 0, 255)

        # Adjust batch size depending on GPU memory
        batch_size = 12

        for idx, video_path in enumerate(self.video_files):
            if not self.is_running:
                break

            video_filename = os.path.basename(video_path)
            self.overall_progress.emit(idx + 1, len(self.video_files), video_filename)
            self.file_progress.emit(0, 0, 0)
            self.time_updated.emit("00:00:00", "--:--:--")
            self.speed_updated.emit(0.0)

            base_name = os.path.splitext(video_filename)[0]
            self.log_message.emit(f"\n--- Starting processing for: {video_filename} ---")

            try:
                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    self.log_message.emit(f"[WARNING] Could not open video: {video_filename}. Skipping.")
                    continue

                width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps, total_frames = cap.get(cv2.CAP_PROP_FPS) or 30.0, int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

                out_video = None
                if self.save_video:
                    out_video_path = os.path.join(self.output_dir, f"{base_name}_inference.mp4")
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                    out_video = cv2.VideoWriter(out_video_path, fourcc, fps, (width, height))

                all_detections_data = []
                frame_idx = 0
                frame_count_for_fps = 0
                fps_check_time = 0

                file_stopwatch = Stopwatch()
                file_stopwatch.start()

                # Batching buffers
                batch_frames = []
                batch_indices = []

                def process_batch(frames_batch, indices_batch):
                    nonlocal all_detections_data, out_video
                    if not frames_batch:
                        return

                    predict_kwargs = {"conf": self.confidence, "verbose": False}
                    if use_cuda:
                        predict_kwargs["device"] = "cuda"

                    try:
                        results_list = model.predict(frames_batch, **predict_kwargs)
                    except Exception:
                        # fallback: process one by one
                        results_list = [model.predict(f, **predict_kwargs)[0] for f in frames_batch]

                    for res, fidx, frame in zip(results_list, indices_batch, frames_batch):
                        if res.boxes is not None:
                            for box in res.boxes:
                                if self.save_video or self.save_csv:
                                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                                    bw, bh = x2 - x1, y2 - y1
                                    inset_x, inset_y = bw * 0.05, bh * 0.05

                                    x1f = x1 + inset_x
                                    y1f = y1 + inset_y
                                    x2f = x2 - inset_x
                                    y2f = y2 - inset_y

                                    conf_val, cls_id = float(box.conf[0]), int(box.cls[0])
                                    class_name = class_names.get(cls_id, "Unknown")
                                    cx, cy = (x1f + x2f) / 2.0, (y1f + y2f) / 2.0

                                    if self.save_video:
                                        color = class_colors.get(class_name, (255, 255, 255))
                                        cv2.rectangle(frame, (int(x1f), int(y1f)), (int(x2f), int(y2f)), color, 2)
                                        label_text = f"{class_name} {conf_val:.2f}"
                                        cv2.putText(frame, label_text, (int(x1f), int(y1f) - 10),
                                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                                        cv2.circle(frame, (int(round(cx)), int(round(cy))), 4, centroid_color, -1)

                                    if self.save_csv:
                                        all_detections_data.append([
                                            fidx, class_name, f"{conf_val:.4f}",
                                            f"{x1f:.4f}", f"{y1f:.4f}", f"{x2f:.4f}", f"{y2f:.4f}",
                                            f"{cx:.4f}", f"{cy:.4f}"
                                        ])

                        if self.save_video and out_video is not None:
                            out_video.write(frame)

                # Main loop
                while self.is_running:
                    ret, frame = cap.read()
                    if not ret:
                        if batch_frames:
                            process_batch(batch_frames, batch_indices)
                            batch_frames, batch_indices = [], []
                        break

                    batch_frames.append(frame.copy())
                    batch_indices.append(frame_idx)

                    frame_idx += 1
                    frame_count_for_fps += 1

                    if len(batch_frames) >= batch_size:
                        process_batch(batch_frames, batch_indices)
                        batch_frames, batch_indices = [], []

                    current_time = file_stopwatch.get_elapsed_time(as_float=True)
                    if current_time > fps_check_time + 1:
                        processing_fps = frame_count_for_fps / (current_time - fps_check_time)
                        self.speed_updated.emit(processing_fps)
                        frame_count_for_fps, fps_check_time = 0, current_time

                    if total_frames > 0:
                        progress = int(frame_idx * 100 / total_frames)
                        self.file_progress.emit(progress, frame_idx, total_frames)
                        self.time_updated.emit(file_stopwatch.get_elapsed_time(),
                                               file_stopwatch.get_etr(frame_idx, total_frames))

                cap.release()
                if self.save_video and out_video is not None:
                    out_video.release()
                    self.log_message.emit(f"✓ Saved annotated video to: {os.path.basename(out_video_path)}")

                if self.save_csv:
                    out_csv_path = os.path.join(self.output_dir, f"{base_name}_detections.csv")
                    with open(out_csv_path, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(["frame_idx", "class_name", "conf", "x1", "y1", "x2", "y2", "cx", "cy"])
                        writer.writerows(all_detections_data)
                    self.log_message.emit(f"✓ Saved detections CSV to: {os.path.basename(out_csv_path)}")

            except Exception as e:
                self.log_message.emit(f"[ERROR] Failed during processing of {video_filename}: {e}")
                self.log_message.emit(traceback.format_exc())
                if 'cap' in locals() and cap.isOpened(): cap.release()
                if 'out_video' in locals() and out_video is not None: out_video.release()
                continue

        if self.is_running:
            self.log_message.emit("\n--- YOLO Inference Complete ---")
        else:
            self.log_message.emit("\n--- YOLO Inference Cancelled ---")
        self.finished.emit()
