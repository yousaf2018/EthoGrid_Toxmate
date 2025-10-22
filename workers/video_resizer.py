# EthoGrid_App/workers/video_resizer.py

import os
import subprocess
import traceback
import shutil
import cv2
import re
from PyQt5.QtCore import QThread, pyqtSignal
from core.stopwatch import Stopwatch

def has_nvidia_gpu():
    """Checks if nvidia-smi command is available, indicating an NVIDIA GPU."""
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.run(['nvidia-smi'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, startupinfo=startupinfo)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False

class VideoResizer(QThread):
    overall_progress = pyqtSignal(int, int, str)
    file_progress = pyqtSignal(int, str)
    log_message = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    time_updated = pyqtSignal(str, str)
    speed_updated = pyqtSignal(float)

    def __init__(self, video_files, output_dir, target_height, parent=None):
        super().__init__(parent)
        self.video_files = video_files
        self.output_dir = output_dir
        self.target_height = target_height
        self.is_running = True
        self.process = None

    def stop(self):
        self.log_message.emit("Stopping resize process...")
        self.is_running = False
        if self.process and self.process.poll() is None:
            self.process.terminate()

    def _check_ffmpeg(self):
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, startupinfo=startupinfo)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _copy_with_progress(self, src, dst):
        try:
            source_size = os.path.getsize(src)
            copied = 0
            file_stopwatch = Stopwatch(); file_stopwatch.start()
            
            with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
                while self.is_running:
                    buf = fsrc.read(1024 * 1024) # Read in 1MB chunks
                    if not buf:
                        break
                    fdst.write(buf)
                    copied += len(buf)
                    progress = int(copied * 100 / source_size)
                    self.file_progress.emit(progress, "Copying...")
                    self.time_updated.emit(file_stopwatch.get_elapsed_time(), file_stopwatch.get_etr(copied, source_size))
            return self.is_running
        except Exception as e:
            self.log_message.emit(f"[ERROR] File copy failed: {e}")
            return False

    def run(self):
        if not self._check_ffmpeg():
            self.error.emit("FFmpeg not found. Please install FFmpeg and ensure it's in your system's PATH.")
            return

        use_gpu = has_nvidia_gpu()
        if use_gpu:
            self.log_message.emit("NVIDIA GPU detected. Using hardware-accelerated transcoding.")
        else:
            self.log_message.emit("No NVIDIA GPU detected. Using CPU-based transcoding (slower).")

        for i, video_path in enumerate(self.video_files):
            if not self.is_running: break
            
            filename = os.path.basename(video_path)
            self.overall_progress.emit(i + 1, len(self.video_files), filename)
            self.log_message.emit(f"\n--- Processing: {filename} ---")
            self.time_updated.emit("00:00:00", "--:--:--")
            self.speed_updated.emit(0.0)

            try:
                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    self.log_message.emit(f"[WARNING] Could not open video. Skipping.")
                    continue

                original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                original_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                cap.release()
                base_name = os.path.splitext(filename)[0]

                if self.target_height >= original_height:
                    output_file = os.path.join(self.output_dir, f"{base_name}.mp4")
                    self.log_message.emit(f"  - Skipping resize, copying original file -> {os.path.basename(output_file)}")
                    
                    if self._copy_with_progress(video_path, output_file):
                        self.log_message.emit(f"  ✓ Copied original file.")
                    else:
                        self.log_message.emit(f"  ✗ Cancelled copy for: {filename}")
                    continue

                output_file = os.path.join(self.output_dir, f"{base_name}.mp4")
                self.log_message.emit(f"  ▶ Resizing to {self.target_height}p -> {os.path.basename(output_file)}")
                
                if use_gpu:
                    cmd = [
                        "ffmpeg", "-i", video_path,
                        "-vf", f"scale=-2:{self.target_height}",
                        "-c:v", "h264_nvenc", "-preset", "fast", "-cq", "22", 
                        output_file, "-y"
                    ]
                else: # CPU fallback
                    cmd = [
                        "ffmpeg", "-i", video_path,
                        "-vf", f"scale=-2:{self.target_height}",
                        "-c:v", "libx264", "-preset", "fast", "-crf", "22", 
                        output_file, "-y"
                    ]
                
                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, startupinfo=startupinfo)
                
                file_stopwatch = Stopwatch()
                file_stopwatch.start()
                
                frame_regex = re.compile(r"frame=\s*(\d+)")
                speed_regex = re.compile(r"speed=\s*(\d+\.?\d*)x")

                for line in self.process.stderr:
                    if not self.is_running:
                        self.process.terminate()
                        break
                    
                    frame_match = frame_regex.search(line)
                    speed_match = speed_regex.search(line)

                    if frame_match:
                        current_frame = int(frame_match.group(1))
                        progress = min(100, int(current_frame * 100 / total_frames)) if total_frames > 0 else 0
                        self.file_progress.emit(progress, f"Frame: {current_frame}/{total_frames}")
                        self.time_updated.emit(file_stopwatch.get_elapsed_time(), file_stopwatch.get_etr(current_frame, total_frames))

                    if speed_match:
                        speed_multiplier = float(speed_match.group(1))
                        processing_fps = original_fps * speed_multiplier
                        self.speed_updated.emit(processing_fps)
                
                return_code = self.process.wait()
                if return_code != 0 and self.is_running:
                    error_output = self.process.stderr.read()
                    self.log_message.emit(f"[ERROR] FFmpeg failed with exit code {return_code}:\n{error_output}")
                    continue

                if self.is_running:
                    self.file_progress.emit(100, "Complete")
                    self.log_message.emit(f"  ✓ Saved: {os.path.basename(output_file)}")
                else:
                    self.log_message.emit(f"  ✗ Cancelled resize for: {os.path.basename(output_file)}")
            except Exception as e:
                self.log_message.emit(f"[ERROR] Failed to resize {filename}: {e}")
                self.log_message.emit(traceback.format_exc())
                continue
        
        if self.is_running:
            self.log_message.emit("\n--- Video resizing complete! ---")
        else:
            self.log_message.emit("\n--- Video resizing cancelled by user. ---")
        self.finished.emit()