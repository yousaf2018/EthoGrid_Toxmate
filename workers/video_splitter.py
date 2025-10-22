# EthoGrid_App/workers/video_splitter.py

import os
import re
import subprocess
import traceback
from PyQt5.QtCore import QThread, pyqtSignal

class VideoSplitter(QThread):
    overall_progress = pyqtSignal(int, int, str)
    file_progress = pyqtSignal(int, str)
    log_message = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, video_files, output_dir, chunk_minutes, use_subfolders, parent=None):
        super().__init__(parent)
        self.video_files = video_files
        self.output_dir = output_dir
        self.chunk_seconds = chunk_minutes * 60
        self.use_subfolders = use_subfolders
        self.is_running = True

    def stop(self):
        self.log_message.emit("Stopping split process...")
        self.is_running = False
        # Terminate any running ffmpeg process
        if hasattr(self, 'process') and self.process.poll() is None:
            self.process.terminate()

    def _check_ffmpeg(self):
        try:
            subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def run(self):
        if not self._check_ffmpeg():
            self.error.emit("FFmpeg not found. Please install FFmpeg and ensure it's in your system's PATH.")
            return

        total_files = len(self.video_files)
        for i, video_path in enumerate(self.video_files):
            if not self.is_running: break
            
            filename = os.path.basename(video_path)
            self.overall_progress.emit(i + 1, total_files, filename)
            self.log_message.emit(f"\n--- Starting to process: {filename} ---")

            try:
                # 1. Get video duration using ffprobe
                cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
                duration = float(result.stdout.strip())
                self.log_message.emit(f"  - Video duration: {duration:.2f} seconds")

                num_chunks = int(duration // self.chunk_seconds) + (1 if duration % self.chunk_seconds > 1 else 0) # Add chunk if remainder is > 1s
                
                # 2. Determine output folder
                base_name = os.path.splitext(filename)[0]
                current_output_dir = self.output_dir
                if self.use_subfolders:
                    current_output_dir = os.path.join(self.output_dir, base_name)
                os.makedirs(current_output_dir, exist_ok=True)
                
                # 3. Loop and split into chunks
                for chunk_idx in range(num_chunks):
                    if not self.is_running: break
                    
                    start_time = chunk_idx * self.chunk_seconds
                    output_file = os.path.join(current_output_dir, f"{base_name}_part_{chunk_idx+1:02d}.mp4")
                    self.log_message.emit(f"  ▶ Splitting Part {chunk_idx+1}/{num_chunks} -> {os.path.basename(output_file)}")
                    
                    cmd = [
                        "ffmpeg", "-ss", str(start_time), "-i", video_path,
                        "-t", str(self.chunk_seconds), "-c", "copy", output_file, "-y",
                        "-progress", "pipe:1" # For progress reporting
                    ]

                    self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True)
                    
                    total_frames_in_chunk = 0
                    while self.process.poll() is None:
                        if not self.is_running:
                            self.process.terminate(); break
                        
                        line = self.process.stdout.readline()
                        if "total_size" in line:
                            # The last line of progress indicates completion for this chunk
                            self.file_progress.emit(100, f"Part {chunk_idx+1}/{num_chunks} Complete")
                        elif "frame=" in line:
                            if total_frames_in_chunk == 0: total_frames_in_chunk = self.chunk_seconds * 30 # Rough estimate
                            current_frame = int(line.strip().split('=')[-1])
                            progress = min(100, int(current_frame * 100 / total_frames_in_chunk))
                            self.file_progress.emit(progress, f"Part {chunk_idx+1}/{num_chunks} | Frame: {current_frame}")

                    self.process.wait()
                    if self.is_running:
                        self.log_message.emit(f"  ✓ Saved: {os.path.basename(output_file)}")
                    else:
                        self.log_message.emit(f"  ✗ Cancelled split for: {os.path.basename(output_file)}")

            except Exception as e:
                self.log_message.emit(f"[ERROR] Failed to split {filename}: {e}")
                self.log_message.emit(traceback.format_exc())
                continue
        
        if self.is_running: self.log_message.emit("\n--- Video splitting complete! ---")
        else: self.log_message.emit("\n--- Video splitting cancelled by user. ---")
        self.finished.emit()