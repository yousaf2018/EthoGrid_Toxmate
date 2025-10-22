# EthoGrid_App/workers/frame_extractor.py

import os
import cv2
import traceback
import random
from PyQt5.QtCore import QThread, pyqtSignal

class FrameExtractor(QThread):
    overall_progress = pyqtSignal(int, int, str)
    file_progress = pyqtSignal(int, int, int)
    log_message = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, video_files, parent_dir, output_dir, frame_count, parent=None):
        super().__init__(parent)
        self.video_files = video_files
        self.parent_dir = parent_dir # The top-level folder the user selected
        self.output_dir = output_dir
        self.frame_count = frame_count
        self.is_running = True

    def stop(self):
        self.log_message.emit("Stopping frame extraction...")
        self.is_running = False

    def run(self):
        total_files = len(self.video_files)
        for i, video_path in enumerate(self.video_files):
            if not self.is_running:
                break
            
            filename = os.path.basename(video_path)
            self.overall_progress.emit(i + 1, total_files, filename)
            self.log_message.emit(f"\n--- Extracting frames from: {filename} ---")

            try:
                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    self.log_message.emit(f"[WARNING] Could not open video: {filename}. Skipping.")
                    continue
                
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if total_frames <= 0:
                    self.log_message.emit(f"[WARNING] Video has no frames: {filename}. Skipping.")
                    cap.release()
                    continue

                self.log_message.emit(f"  - Video has {total_frames} total frames.")
                
                num_to_extract = min(self.frame_count, total_frames)
                if num_to_extract == 0:
                    self.log_message.emit(f"[INFO] Number of frames to extract is zero. Skipping.")
                    cap.release()
                    continue
                
                # ### NEW LOGIC: Random Sampling ###
                # Select a random, unique set of frame indices to extract
                indices_to_extract = sorted(random.sample(range(total_frames), num_to_extract))
                self.log_message.emit(f"  - Randomly sampling {len(indices_to_extract)} frames...")

                # ### NEW LOGIC: Descriptive Filename ###
                # Create a clean, descriptive name from the relative path
                try:
                    # parent_dir might not be a direct parent, find the common root
                    common_path = os.path.commonpath([self.parent_dir, video_path])
                    rel_path = os.path.relpath(video_path, common_path)
                except ValueError: # Happens if paths are on different drives
                    rel_path = os.path.basename(video_path)

                video_name_prefix = os.path.splitext(rel_path.replace(os.sep, "_"))[0]

                for count, frame_idx in enumerate(indices_to_extract):
                    if not self.is_running:
                        break
                    
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                    ret, frame = cap.read()
                    if ret:
                        output_filename = f"{video_name_prefix}_frame_{frame_idx:06d}.jpg"
                        output_path = os.path.join(self.output_dir, output_filename)
                        cv2.imwrite(output_path, frame)
                    
                    progress = int((count + 1) * 100 / len(indices_to_extract))
                    self.file_progress.emit(progress, count + 1, len(indices_to_extract))

                cap.release()
                if self.is_running:
                    self.log_message.emit(f"✓ Finished extracting frames for {filename}")

            except Exception as e:
                self.log_message.emit(f"[ERROR] Failed to process {filename}: {e}")
                self.log_message.emit(traceback.format_exc())
                if 'cap' in locals() and cap.isOpened():
                    cap.release()
                continue
        
        if self.is_running:
            self.log_message.emit("\n--- Frame extraction complete! ---")
        else:
            self.log_message.emit("\n--- Frame extraction cancelled by user. ---")
        self.finished.emit()