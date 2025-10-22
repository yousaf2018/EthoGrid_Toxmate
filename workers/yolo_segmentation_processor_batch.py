# EthoGrid_App/workers/yolo_segmentation_processor.py

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

class YoloSegmentationProcessor(QThread):
    overall_progress = pyqtSignal(int, int, str)
    file_progress = pyqtSignal(int, int, int)
    log_message = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    time_updated = pyqtSignal(str, str)
    speed_updated = pyqtSignal(float)

    def __init__(self, video_files, model_path, output_dir, confidence, save_video, save_csv, parent=None):
        super().__init__(parent)
        self.video_files = video_files; self.model_path = model_path; self.output_dir = output_dir
        self.confidence = confidence; self.save_video = save_video; self.save_csv = save_csv
        self.is_running = True

    def stop(self):
        self.log_message.emit("Stopping segmentation process..."); self.is_running = False

    def run(self):
        if YOLO is None or np is None:
            self.error.emit("Dependencies not found. Please run: pip install ultralytics numpy"); return

        try:
            self.log_message.emit(f"Loading YOLO Segmentation model from: {self.model_path}")
            model = YOLO(self.model_path); self.log_message.emit("Model loaded successfully.")
        except Exception as e:
            self.error.emit(f"Failed to load YOLO model: {e}"); return

        class_names = model.names
        class_colors = {i: tuple(np.random.randint(60, 255, size=3).tolist()) for i, name in class_names.items()}
        centroid_color = (0, 0, 255)
        
        for idx, video_path in enumerate(self.video_files):
            if not self.is_running: break
            video_filename = os.path.basename(video_path)
            self.overall_progress.emit(idx + 1, len(self.video_files), video_filename)
            self.file_progress.emit(0, 0, 0)
            self.time_updated.emit("00:00:00", "--:--:--")
            self.speed_updated.emit(0.0)
            
            base_name = os.path.splitext(video_filename)[0]
            self.log_message.emit(f"\n--- Starting segmentation for: {video_filename} ---")
            
            try:
                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened(): self.log_message.emit(f"[WARNING] Could not open video: {video_filename}. Skipping."); continue
                
                width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps, total_frames = cap.get(cv2.CAP_PROP_FPS) or 30.0, int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

                out_video = None
                if self.save_video:
                    out_video_path = os.path.join(self.output_dir, f"{base_name}_segmentation.mp4")
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v'); out_video = cv2.VideoWriter(out_video_path, fourcc, fps, (width, height))
                
                all_detections_data = []; frame_idx = 0
                frame_count_for_fps = 0; fps_check_time = 0
                
                file_stopwatch = Stopwatch()
                file_stopwatch.start()

                while self.is_running:
                    ret, frame = cap.read()
                    if not ret: break
                    results_list = model.predict(frame, conf=self.confidence, verbose=False)
                    results = results_list[0]; overlay = frame.copy(); has_drawn_mask = False
                    if results.masks is not None:
                        for i in range(len(results.masks)):
                            if not self.is_running: break
                            conf = float(results.boxes.conf[i]); cls_id = int(results.boxes.cls[i])
                            class_name = class_names.get(cls_id, "Unknown"); color = class_colors.get(cls_id, (255,255,255))
                            mask = results.masks.data[i].cpu().numpy(); mask_resized = cv2.resize(mask, (width, height), interpolation=cv2.INTER_NEAREST).astype(np.uint8)
                            x1_orig, y1_orig, x2_orig, y2_orig = results.boxes.xyxy[i].tolist()
                            box_width = x2_orig - x1_orig; box_height = y2_orig - y1_orig
                            inset_x = box_width * 0.05; inset_y = box_height * 0.05
                            x1f = x1_orig + inset_x; y1f = y1_orig + inset_y
                            x2f = x2_orig - inset_x; y2f = y2_orig - inset_y
                            M = cv2.moments(mask_resized)
                            if M["m00"] != 0:
                                cx = M["m10"] / M["m00"]
                                cy = M["m01"] / M["m00"]
                            else:
                                cx = (x1f + x2f) / 2.0
                                cy = (y1f + y2f) / 2.0
                            if self.save_csv:
                                contours, _ = cv2.findContours(mask_resized, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                                polygon_points_str = ";".join([",".join(map(str, p[0])) for cnt in contours for p in cnt])
                                all_detections_data.append([frame_idx, class_name, f"{conf:.4f}", f"{x1f:.4f}", f"{y1f:.4f}", f"{x2f:.4f}", f"{y2f:.4f}", f"{cx:.4f}", f"{cy:.4f}", polygon_points_str])
                            if self.save_video:
                                overlay[mask_resized.astype(bool)] = color; has_drawn_mask = True
                                cv2.rectangle(frame, (int(x1f), int(y1f)), (int(x2f), int(y2f)), color, 1)
                                cv2.circle(frame, (int(round(cx)), int(round(cy))), 8, centroid_color, -1)
                    if self.save_video:
                        if has_drawn_mask: frame = cv2.addWeighted(overlay, 0.4, frame, 0.6, 0)
                        out_video.write(frame)
                    
                    frame_idx += 1
                    frame_count_for_fps += 1

                    current_time = file_stopwatch.get_elapsed_time(as_float=True)
                    if current_time > fps_check_time + 1:
                        processing_fps = frame_count_for_fps / (current_time - fps_check_time)
                        self.speed_updated.emit(processing_fps)
                        frame_count_for_fps = 0; fps_check_time = current_time

                    if total_frames > 0:
                        progress = int(frame_idx * 100 / total_frames)
                        self.file_progress.emit(progress, frame_idx, total_frames)
                        self.time_updated.emit(file_stopwatch.get_elapsed_time(), file_stopwatch.get_etr(frame_idx, total_frames))
                
                cap.release()
                if self.save_video:
                    out_video.release(); self.log_message.emit(f"✓ Saved segmented video to: {os.path.basename(out_video_path)}")
                if self.save_csv:
                    out_csv_path = os.path.join(self.output_dir, f"{base_name}_segmentations.csv")
                    with open(out_csv_path, 'w', newline='') as f:
                        writer = csv.writer(f); writer.writerow(["frame_idx", "class_name", "conf", "x1", "y1", "x2", "y2", "cx", "cy", "polygon"]); writer.writerows(all_detections_data)
                    self.log_message.emit(f"✓ Saved segmentations CSV to: {os.path.basename(out_csv_path)}")
            except Exception as e:
                self.log_message.emit(f"[ERROR] Failed during processing of {video_filename}: {e}"); self.log_message.emit(traceback.format_exc())
                if 'cap' in locals() and cap.isOpened(): cap.release()
                if 'out_video' in locals() and out_video is not None: out_video.release()
                continue
        
        if self.is_running: self.log_message.emit("\n--- YOLO Segmentation Complete ---")
        else: self.log_message.emit("\n--- YOLO Segmentation Cancelled ---")
        self.finished.emit()