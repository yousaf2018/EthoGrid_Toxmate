# EthoGrid_App/workers/video_saver.py

import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal, QPointF

class VideoSaver(QThread):
    progress_updated = pyqtSignal(int)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, source_video_path, output_video_path, detections, 
                 grid_settings, grid_transform, behavior_colors, 
                 video_size, fps, line_thickness, selected_cells, 
                 timeline_segments, draw_grid=False, draw_overlays=True, parent=None):
        super().__init__(parent)
        self.source_path = source_video_path; self.output_path = output_video_path; self.detections = detections
        self.grid_settings = grid_settings; self.grid_transform = grid_transform; self.behavior_colors = behavior_colors
        self.video_size = video_size; self.fps = fps; self.line_thickness = line_thickness; self.selected_cells = selected_cells
        self.timeline_segments = timeline_segments; self.draw_grid = draw_grid; self.draw_overlays = draw_overlays; self.is_running = True

        original_w, original_h = self.video_size
        if self.draw_overlays:
            legend_width = 250
            num_tanks = self.grid_settings['cols'] * self.grid_settings['rows']
            timeline_h = (num_tanks * 15) + 40 if num_tanks > 0 else 0
            final_w = original_w + legend_width
            final_h = original_h + timeline_h
            self.final_video_size = (final_w, final_h)
        else:
            self.final_video_size = self.video_size

    def stop(self):
        self.is_running = False

    def _get_clipped_mask(self, polygon_str, tank_number):
        try:
            seg_mask = np.zeros((self.video_size[1], self.video_size[0]), dtype=np.uint8)
            poly_points = np.array([list(map(int, p.split(','))) for p in polygon_str.split(';')], dtype=np.int32)
            cv2.fillPoly(seg_mask, [poly_points], 255)

            tank_mask = np.zeros_like(seg_mask)
            rows, cols = self.grid_settings['rows'], self.grid_settings['cols']
            r = (int(tank_number) - 1) // cols
            c = (int(tank_number) - 1) % cols
            w, h = self.video_size
            
            p1 = self.grid_transform.map(QPointF(c * w / cols, r * h / rows))
            p2 = self.grid_transform.map(QPointF((c + 1) * w / cols, r * h / rows))
            p3 = self.grid_transform.map(QPointF((c + 1) * w / cols, (r + 1) * h / rows))
            p4 = self.grid_transform.map(QPointF(c * w / cols, (r + 1) * h / rows))
            tank_contour = np.array([(p1.x(), p1.y()), (p2.x(), p2.y()), (p3.x(), p3.y()), (p4.x(), p4.y())], dtype=np.int32)
            cv2.fillPoly(tank_mask, [tank_contour], 255)
            
            clipped_mask = cv2.bitwise_and(seg_mask, tank_mask)
            return clipped_mask
        except:
            return None

    def _draw_legend_on_frame(self, frame, original_video_width):
        if not self.behavior_colors: return
        y_offset = 0; legend_x_start = original_video_width + 20
        for behavior, color_rgb in sorted(self.behavior_colors.items()):
            y_pos = 20 + y_offset
            cv2.rectangle(frame, (legend_x_start, y_pos), (legend_x_start + 20, y_pos + 20), color_rgb[::-1], -1)
            cv2.putText(frame, behavior, (legend_x_start + 30, y_pos + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (240, 240, 240), 1, cv2.LINE_AA)
            y_offset += 25

    def _draw_timeline_on_frame(self, frame, frame_idx, total_frames, original_video_height):
        new_h, new_w, _ = frame.shape; num_tanks = self.grid_settings['cols'] * self.grid_settings['rows']
        if new_h <= original_video_height or num_tanks == 0 or total_frames <= 1: return
        cv2.rectangle(frame, (0, original_video_height), (new_w, new_h), (10, 10, 10), -1)
        draw_area_x, draw_area_y = 40, original_video_height + 10
        draw_area_w, draw_area_h = new_w - 80, new_h - original_video_height - 20
        if draw_area_h <= 0 or draw_area_w <= 0: return
        bar_h_total = draw_area_h / num_tanks; bar_h_visible = bar_h_total * 0.8
        for i in range(num_tanks):
            tank_id = i + 1; y_pos = draw_area_y + i * bar_h_total
            cv2.rectangle(frame, (draw_area_x, int(y_pos)), (draw_area_x + draw_area_w, int(y_pos + bar_h_visible)), (74, 74, 74), -1)
            if tank_id in self.timeline_segments:
                for start_f, end_f, behavior in self.timeline_segments[tank_id]:
                    color_rgb = self.behavior_colors.get(behavior, (100, 100, 100))
                    x_start = int(draw_area_x + (start_f / total_frames) * draw_area_w)
                    x_end = int(draw_area_x + ((end_f + 1) / total_frames) * draw_area_w)
                    cv2.rectangle(frame, (x_start, int(y_pos)), (x_end, int(y_pos + bar_h_visible)), color_rgb[::-1], -1)
            cv2.putText(frame, f"T{tank_id}", (draw_area_x - 35, int(y_pos + bar_h_visible / 2 + 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (224, 224, 224), 1, cv2.LINE_AA)
        indicator_x = int(draw_area_x + (frame_idx / total_frames) * draw_area_w)
        cv2.line(frame, (indicator_x, draw_area_y), (indicator_x, draw_area_y + draw_area_h), (80, 80, 255), 2)

    def process_frame(self, original_frame, frame_idx, total_frames):
        original_w, original_h = self.video_size
        if self.draw_overlays:
            new_w, new_h = self.final_video_size
            processed_frame = np.full((new_h, new_w, 3), 43, dtype=np.uint8)
            processed_frame[0:original_h, 0:original_w] = original_frame
        else:
            processed_frame = original_frame.copy()
            
        overlay = processed_frame.copy()
        has_drawn_mask = False
        
        if frame_idx in self.detections:
            for det in self.detections[frame_idx]:
                if det.get('tank_number') is not None and (not self.selected_cells or str(det['tank_number']) in self.selected_cells):
                    color_bgr = self.behavior_colors.get(det["class_name"], (255, 255, 255))[::-1]
                    
                    if 'polygon' in det and det['polygon']:
                        clipped_mask = self._get_clipped_mask(det['polygon'], det['tank_number'])
                        if clipped_mask is not None:
                            # ### THE FIX IS HERE ###
                            # Ensure the mask has the same dimensions as the overlay canvas before applying it
                            final_mask = np.zeros((overlay.shape[0], overlay.shape[1]), dtype=np.uint8)
                            final_mask[0:clipped_mask.shape[0], 0:clipped_mask.shape[1]] = clipped_mask
                            
                            overlay[final_mask > 0] = color_bgr
                            has_drawn_mask = True
                    
                    x1, y1, x2, y2 = map(float, (det["x1"], det["y1"], det["x2"], det["y2"]))
                    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0

                    cv2.rectangle(processed_frame, (int(x1), int(y1)), (int(x2), int(y2)), color_bgr, 2)
                    cv2.circle(processed_frame, (int(round(cx)), int(round(cy))), 8, (0, 0, 255), -1)
                    
                    label = f"T{det['tank_number']}"; font_face, f_scale, f_thick = cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2
                    (tw, th), _ = cv2.getTextSize(label, font_face, f_scale, f_thick)
                    cv2.rectangle(processed_frame, (int(x1), int(y1) - th - 12), (int(x1) + tw, int(y1)), color_bgr, -1)
                    cv2.putText(processed_frame, label, (int(x1), int(y1) - 7), font_face, f_scale, (0,0,0), f_thick, cv2.LINE_AA)
        
        if has_drawn_mask:
            processed_frame = cv2.addWeighted(overlay, 0.4, processed_frame, 0.6, 0)
        
        if self.draw_overlays:
            self._draw_legend_on_frame(processed_frame, original_w)
            self._draw_timeline_on_frame(processed_frame, frame_idx, total_frames, original_h)
            
        return processed_frame

    def run(self):
        cap = cv2.VideoCapture(self.source_path)
        if not cap.isOpened(): self.error_occurred.emit(f"Could not open source video: {self.source_path}"); return
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fourcc = cv2.VideoWriter_fourcc(*'mp4v'); writer = cv2.VideoWriter(self.output_path, fourcc, self.fps, self.final_video_size)
        if not writer.isOpened(): self.error_occurred.emit(f"Could not open video writer for: {self.output_path}"); cap.release(); return
        for frame_idx in range(total_frames):
            if not self.is_running: break
            ret, original_frame = cap.read()
            if not ret: break
            processed_frame = self.process_frame(original_frame, frame_idx, total_frames)
            writer.write(processed_frame)
            self.progress_updated.emit(int((frame_idx + 1) * 100 / total_frames))
        cap.release(); writer.release()
        if self.is_running: self.finished.emit()