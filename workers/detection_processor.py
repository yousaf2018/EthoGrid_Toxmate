# EthoGrid_App/workers/detection_processor.py

from PyQt5.QtCore import QThread, pyqtSignal, QPointF
from collections import defaultdict

class DetectionProcessor(QThread):
    processing_finished = pyqtSignal(dict, dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, detections, grid_transform, grid_settings, video_size, max_animals_per_tank, parent=None):
        super().__init__(parent)
        self.detections = {k: list(v) for k, v in detections.items()} # Make a mutable copy
        self.grid_transform = grid_transform
        self.grid_settings = grid_settings
        self.video_size = video_size
        self.max_animals_per_tank = max_animals_per_tank
        self._is_running = True

    def stop(self):
        self._is_running = False

    def _get_tank_for_point(self, x, y, w, h, cols, rows, inverse_transform):
        transformed_point = inverse_transform.map(QPointF(x, y))
        tx, ty = transformed_point.x(), transformed_point.y()
        if not (0 <= tx < w and 0 <= ty < h): return None
        cell_width, cell_height = w / cols, h / rows
        col = min(cols - 1, max(0, int(tx / cell_width)))
        row = min(rows - 1, max(0, int(ty / cell_height)))
        return row * cols + col + 1

    def run(self):
        try:
            w, h = self.video_size
            cols, rows = self.grid_settings['cols'], self.grid_settings['rows']
            inverse_transform, invertible = self.grid_transform.inverted()
            if not invertible:
                self.error_occurred.emit("Grid transform is not invertible. Cannot process detections.")
                return

            # Step 1: Assign tank numbers to all detections
            for frame_idx, dets in self.detections.items():
                if not self._is_running: return
                for det in dets:
                    # Ensure cx/cy are calculated as floats
                    if 'cx' not in det or det.get('cx') is None:
                        det['cx'] = (float(det["x1"]) + float(det["x2"])) / 2.0
                        det['cy'] = (float(det["y1"]) + float(det["y2"])) / 2.0
                    det['tank_number'] = self._get_tank_for_point(det['cx'], det['cy'], w, h, cols, rows, inverse_transform)

            # Step 2: Filter detections based on max_animals_per_tank by confidence
            filtered_detections = defaultdict(list)
            for frame_idx, dets_in_frame in self.detections.items():
                if not self._is_running: return
                
                dets_by_tank = defaultdict(list)
                for det in dets_in_frame:
                    if det.get('tank_number') is not None:
                        # Ensure confidence is a float for sorting
                        try:
                            det['conf'] = float(det.get('conf', 0.0))
                        except (ValueError, TypeError):
                            det['conf'] = 0.0
                        dets_by_tank[det['tank_number']].append(det)
                
                for tank_num, dets_in_tank in dets_by_tank.items():
                    dets_in_tank.sort(key=lambda d: d['conf'], reverse=True)
                    filtered_detections[frame_idx].extend(dets_in_tank[:self.max_animals_per_tank])

            # Step 3: Generate timeline from the FILTERED detections
            tank_data_for_timeline = defaultdict(dict)
            for frame_idx, dets in filtered_detections.items():
                if not self._is_running: return
                for det in dets:
                    if det.get('tank_number') is not None:
                        tank_data_for_timeline[det['tank_number']][frame_idx] = det["class_name"]

            timeline_segments = {}
            for tank_id, frames in tank_data_for_timeline.items():
                if not self._is_running: return
                if not frames: continue
                segments, sorted_frames = [], sorted(frames.keys())
                start_frame, current_behavior = sorted_frames[0], frames[sorted_frames[0]]
                for i in range(1, len(sorted_frames)):
                    frame, prev_frame, behavior = sorted_frames[i], sorted_frames[i-1], frames[sorted_frames[i]]
                    if behavior != current_behavior or frame != prev_frame + 1:
                        segments.append((start_frame, prev_frame, current_behavior))
                        start_frame, current_behavior = frame, behavior
                segments.append((start_frame, sorted_frames[-1], current_behavior))
                timeline_segments[tank_id] = segments
            
            if self._is_running:
                self.processing_finished.emit(filtered_detections, timeline_segments)
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            self.error_occurred.emit(f"Error during detection processing: {e}")