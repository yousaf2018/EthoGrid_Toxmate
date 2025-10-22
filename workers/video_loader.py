# EthoGrid_App/workers/video_loader.py

import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal, QMutex

class VideoLoader(QThread):
    """
    Loads a video file in a background thread, emitting frames as they are read.
    Handles playback state (playing, paused, seeking).
    """
    video_loaded = pyqtSignal(int, int, float)  # width, height, fps
    frame_loaded = pyqtSignal(int, np.ndarray)  # frame index, frame
    error_occurred = pyqtSignal(str)

    def __init__(self, video_path):
        super().__init__()
        self.video_path = video_path
        self.running = True
        self.mutex = QMutex()
        self.cap = None
        self.total_frames = 0
        self.current_frame_idx = 0
        self.seek_requested = False
        self.seek_frame = 0
        self.playing = False
        self.fps = 30.0

    def run(self):
        self.mutex.lock()
        try:
            self.cap = cv2.VideoCapture(self.video_path)
            if not self.cap.isOpened():
                self.error_occurred.emit("Failed to open video file")
                return

            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
            if self.fps == 0: self.fps = 30.0
            self.video_loaded.emit(width, height, self.fps)
        except Exception as e:
            self.error_occurred.emit(f"Video loading error: {str(e)}")
        finally:
            self.mutex.unlock()

        frame_duration_ms = int(1000 / self.fps if self.fps > 0 else 33)
        while self.running:
            self.mutex.lock()
            try:
                if self.seek_requested:
                    self.current_frame_idx = self.seek_frame
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame_idx)
                    self.seek_requested = False
                    ret, frame = self.cap.read()
                    if ret:
                        self.frame_loaded.emit(self.current_frame_idx, frame.copy())
                        if self.playing: self.current_frame_idx += 1
                
                elif self.playing:
                    if self.current_frame_idx >= self.total_frames:
                        self.playing = False
                        self.mutex.unlock()
                        continue
                    
                    ret, frame = self.cap.read()
                    if not ret:
                        self.playing = False
                        self.mutex.unlock()
                        continue

                    self.frame_loaded.emit(self.current_frame_idx, frame.copy())
                    self.current_frame_idx += 1
            except Exception as e:
                self.error_occurred.emit(f"Frame loading error: {str(e)}")
            finally:
                self.mutex.unlock()
            
            if self.playing:
                self.msleep(frame_duration_ms)
            else:
                self.msleep(20)

    def seek(self, frame_idx):
        self.mutex.lock()
        self.seek_requested = True
        self.seek_frame = frame_idx
        self.mutex.unlock()

    def set_playing(self, playing_state):
        self.mutex.lock()
        self.playing = playing_state
        if playing_state:
            if self.current_frame_idx >= self.total_frames -1:
                self.seek_requested = True
                self.seek_frame = 0
        self.mutex.unlock()

    def stop(self):
        self.mutex.lock()
        self.running = False
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.mutex.unlock()
        self.wait()