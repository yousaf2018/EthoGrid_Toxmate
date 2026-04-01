import os
import csv
import cv2
import time
import queue
import threading
import traceback
from PyQt5.QtCore import QThread, pyqtSignal
from core.stopwatch import Stopwatch

try:
    import numpy as np
    import torch
    from ultralytics import YOLO
except ImportError:
    YOLO, np, torch = None, None, None

class ThreadedVideoReader:
    def __init__(self, video_path, batch_size):
        self.cap = cv2.VideoCapture(video_path)
        self.batch_size = batch_size
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        self.q = queue.Queue(maxsize=batch_size * 5)
        self.running = True
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()

    def _read_loop(self):
        try:
            while self.running:
                if not self.q.full():
                    ret, frame = self.cap.read()
                    if not ret:
                        self.running = False
                        break
                    self.q.put(frame)
                else:
                    time.sleep(0.005)
        except Exception as e:
            print(f"Video Reader Error: {e}")
            self.running = False

    def get_batch(self):
        batch = []
        while len(batch) < self.batch_size:
            try:
                frame = self.q.get(timeout=0.05)
                batch.append(frame)
            except queue.Empty:
                if not self.running:
                    break
        return batch

    def release(self):
        self.running = False
        if self.thread.is_alive():
            self.thread.join(timeout=1.0)
        if self.cap.isOpened():
            self.cap.release()

class ThreadedPostProcessor(threading.Thread):
    def __init__(self, out_video_path, out_csv_path, fps, width, height, class_names, class_colors, save_video, save_csv):
        super().__init__(daemon=True)
        self.q = queue.Queue(maxsize=200)
        self.running = True
        
        self.save_video = save_video
        self.save_csv = save_csv
        self.class_names = class_names
        self.class_colors = class_colors
        self.centroid_color = (0, 0, 255)
        
        self.out_video = None
        if self.save_video:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.out_video = cv2.VideoWriter(out_video_path, fourcc, fps, (width, height))
            
        self.csv_file = None
        self.csv_writer = None
        if self.save_csv:
            self.csv_file = open(out_csv_path, 'w', newline='')
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow(["frame_idx", "class_name", "conf", "x1", "y1", "x2", "y2", "cx", "cy"])

    def run(self):
        while self.running or not self.q.empty():
            try:
                item = self.q.get(timeout=0.1)
                if item is None: 
                    break 
                
                frame, frame_idx, boxes_np = item
                
                if boxes_np is not None and len(boxes_np) > 0:
                    xyxys = boxes_np.xyxy
                    confs = boxes_np.conf
                    clss = boxes_np.cls

                    for box_idx in range(len(boxes_np)):
                        x1_orig, y1_orig, x2_orig, y2_orig = xyxys[box_idx]
                        box_width = x2_orig - x1_orig
                        box_height = y2_orig - y1_orig
                        inset_x = box_width * 0.05
                        inset_y = box_height * 0.05
                        
                        x1f = x1_orig + inset_x
                        y1f = y1_orig + inset_y
                        x2f = x2_orig - inset_x
                        y2f = y2_orig - inset_y

                        conf = confs[box_idx]
                        cls_id = int(clss[box_idx])
                        class_name = self.class_names.get(cls_id, "Unknown")
                        
                        cx = (x1f + x2f) / 2.0
                        cy = (y1f + y2f) / 2.0
                    
                        if self.save_video:
                            color = self.class_colors.get(class_name, (255, 255, 255))
                            cv2.rectangle(frame, (int(x1f), int(y1f)), (int(x2f), int(y2f)), color, 2)
                            label_text = f"{class_name} {conf:.2f}"
                            cv2.putText(frame, label_text, (int(x1f), int(y1f) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                            cv2.circle(frame, (int(round(cx)), int(round(cy))), 4, self.centroid_color, -1)
                        
                        if self.save_csv:
                            self.csv_writer.writerow([
                                frame_idx, class_name, f"{conf:.4f}", 
                                f"{x1f:.4f}", f"{y1f:.4f}", f"{x2f:.4f}", f"{y2f:.4f}", 
                                f"{cx:.4f}", f"{cy:.4f}"
                            ])

                if self.save_video and self.out_video is not None:
                    self.out_video.write(frame)
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in writer thread: {e}")

    def stop_and_release(self):
        self.running = False
        try:
            self.q.put(None)
            self.join(timeout=2.0)
        except:
            pass
        finally:
            if self.out_video:
                self.out_video.release()
            if self.csv_file:
                self.csv_file.close()

class YoloProcessor(QThread):
    overall_progress = pyqtSignal(int, int, str)
    file_progress = pyqtSignal(int, int, int)
    log_message = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    time_updated = pyqtSignal(str, str)
    speed_updated = pyqtSignal(float)

    def __init__(self, video_files, model_path, output_dir, confidence, save_video, save_csv, batch_size=8, parent=None):
        super().__init__(parent)
        self.video_files = video_files
        self.model_path = model_path
        self.output_dir = output_dir
        self.confidence = confidence
        self.save_video = save_video
        self.save_csv = save_csv
        self.batch_size = batch_size
        self.is_running = True

    def stop(self):
        self.log_message.emit("Stopping inference process...")
        self.is_running = False

    def run(self):
        if YOLO is None or np is None or torch is None:
            self.error.emit("Dependencies missing! Please run: pip install ultralytics numpy torch")
            return

        # --- LOAD MODEL ---
        try:
            self.log_message.emit(f"Loading YOLO model from: {self.model_path}")
            model = YOLO(self.model_path)
            self.log_message.emit("Model loaded successfully.")
        except Exception as e:
            self.error.emit(f"Failed to load YOLO model: {e}")
            return

        device_target = 'cpu'
        use_half = False

        if torch.cuda.is_available():
            self.log_message.emit(f"🔍 Checking Hardware: {torch.cuda.get_device_name(0)}")
            dummy_img = np.zeros((160, 160, 3), dtype=np.uint8) 

            try:
                model.predict(dummy_img, device=0, half=True, verbose=False)
                device_target = 0
                use_half = True
                self.log_message.emit("✅ GPU Test 1 Passed: FP16 (Max Speed) enabled.")
            except Exception:
                self.log_message.emit("⚠️ GPU Test 1 (FP16) Failed. Trying Safe Mode (FP32)...")
                try:
                    model.predict(dummy_img, device=0, half=False, verbose=False)
                    device_target = 0
                    use_half = False
                    self.log_message.emit("✅ GPU Test 2 Passed: FP32 enabled.")
                except Exception:
                    device_target = 'cpu'
                    use_half = False
                    self.log_message.emit("❌ CRITICAL: Your PyTorch version does not support this GPU architecture!")
                    self.log_message.emit("🛡️ APP CRASH PREVENTED: Auto-falling back to CPU processing.")
                    self.log_message.emit("👉 To fix the GPU, run: pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124")
                    
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device_target = 'mps'
            self.log_message.emit("✅ Apple Silicon GPU Detected.")
        else:
            self.log_message.emit("⚠️ No GPU detected. Running on CPU.")

        class_names = model.names
        class_colors = {}
        for i, name in class_names.items():
            np.random.seed(i + 5)
            class_colors[name] = tuple(np.random.randint(60, 255, size=3).tolist())

        for idx, video_path in enumerate(self.video_files):
            if not self.is_running: break

            reader = None
            writer = None
            
            try:
                video_filename = os.path.basename(video_path)
                base_name = os.path.splitext(video_filename)[0]
                
                self.overall_progress.emit(idx + 1, len(self.video_files), video_filename)
                self.file_progress.emit(0, 0, 0)
                self.time_updated.emit("00:00:00", "--:--:--")
                self.speed_updated.emit(0.0)
                
                self.log_message.emit(f"\n--- Starting processing for: {video_filename} ---")
                
                reader = ThreadedVideoReader(video_path, self.batch_size)
                if reader.total_frames == 0:
                    self.log_message.emit(f"⚠️ Could not read {video_filename}. Skipping.")
                    reader.release()
                    continue

                out_video_path = os.path.join(self.output_dir, f"{base_name}_inference.mp4")
                out_csv_path = os.path.join(self.output_dir, f"{base_name}_detections.csv")
                
                writer = ThreadedPostProcessor(
                    out_video_path, out_csv_path, reader.fps, reader.width, reader.height, 
                    class_names, class_colors, self.save_video, self.save_csv
                )
                writer.start()
                
                frame_idx = 0
                frame_count_for_fps = 0
                fps_check_time = 0
                ui_update_timer = 0
                
                file_stopwatch = Stopwatch()
                file_stopwatch.start()

                while self.is_running:
                    batch_frames = reader.get_batch()
                    if not batch_frames:
                        break

                    results_generator = model.predict(
                        source=batch_frames, 
                        conf=self.confidence, 
                        stream=True, 
                        verbose=False,
                        device=device_target,
                        half=use_half
                    )

                    for i, results in enumerate(results_generator):
                        current_frame = batch_frames[i]
                        actual_frame_idx = frame_idx + i
                        
                        boxes_np = None
                        if results.boxes is not None and len(results.boxes) > 0:
                            boxes_np = results.boxes.cpu().numpy()
                            
                        writer.q.put((current_frame, actual_frame_idx, boxes_np))
                    
                    frames_processed = len(batch_frames)
                    frame_idx += frames_processed
                    frame_count_for_fps += frames_processed
                    
                    current_time = file_stopwatch.get_elapsed_time(as_float=True)
                    
                    if current_time - ui_update_timer > 0.5:
                        ui_update_timer = current_time
                        if current_time > fps_check_time + 1.0:
                            processing_fps = frame_count_for_fps / (current_time - fps_check_time)
                            self.speed_updated.emit(processing_fps)
                            frame_count_for_fps = 0
                            fps_check_time = current_time

                        if reader.total_frames > 0:
                            progress = int(frame_idx * 100 / reader.total_frames)
                            self.file_progress.emit(progress, frame_idx, reader.total_frames)
                            self.time_updated.emit(file_stopwatch.get_elapsed_time(), file_stopwatch.get_etr(frame_idx, reader.total_frames))

                if self.save_video:
                    self.log_message.emit(f"✓ Saved annotated video to: {os.path.basename(out_video_path)}")
                if self.save_csv:
                    self.log_message.emit(f"✓ Saved detections CSV to: {os.path.basename(out_csv_path)}")

            except Exception as e:
                self.log_message.emit(f"❌ Error during processing of {os.path.basename(video_path)}: {e}")
                self.log_message.emit(traceback.format_exc())
            finally:
                if reader: reader.release()
                if writer: writer.stop_and_release()
        
        if self.is_running: self.log_message.emit("\n--- YOLO Inference Complete ---")
        else: self.log_message.emit("\n--- YOLO Inference Cancelled ---")
        self.finished.emit()