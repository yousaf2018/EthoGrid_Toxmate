# EthoGrid_App/core/data_exporter.py

import os
import traceback
from collections import defaultdict
import cv2
import numpy as np
from PyQt5.QtCore import QPointF

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

def export_heatmap_image(processed_detections, video_path, output_path, time_gap_seconds, video_fps, frame_sample_rate):
    """
    Creates and saves a heatmap image superimposed on the first frame of the video,
    using only a subsample of the frames.
    """
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened(): return f"Could not open video file: {video_path}"
        ret, base_image = cap.read()
        if not ret: cap.release(); return f"Could not read the first frame of video: {video_path}"
        video_h, video_w, _ = base_image.shape
        cap.release()

        # ### NEW: Filter detections based on the frame sample rate ###
        sampled_detections = {k: v for k, v in processed_detections.items() if k % frame_sample_rate == 0}

        # The rest of the logic uses the 'sampled_detections'
        points_by_tank = defaultdict(list)
        all_dets = [det for frame_dets in sampled_detections.values() for det in frame_dets]
        for det in all_dets:
            tank_num = det.get('tank_number')
            if tank_num is not None and det.get('cx') is not None:
                points_by_tank[int(tank_num)].append({
                    'frame_idx': int(det['frame_idx']),
                    'point': (int(det['cx']), int(det['cy']))
                })
        
        final_points_to_draw = []
        frame_gap_threshold = int(time_gap_seconds * video_fps) if video_fps > 0 else 1

        for tank_num, detections in sorted(points_by_tank.items()):
            detections.sort(key=lambda d: d['frame_idx'])
            if not detections: continue
            
            final_points_to_draw.append(detections[0]['point'])

            for i in range(1, len(detections)):
                if (detections[i]['frame_idx'] - detections[i-1]['frame_idx']) <= frame_gap_threshold:
                    final_points_to_draw.append(detections[i]['point'])

        heatmap_accumulator = np.zeros((video_h, video_w), dtype=np.float32)
        if final_points_to_draw:
            for (cx, cy) in final_points_to_draw:
                cv2.circle(heatmap_accumulator, (cx, cy), radius=20, color=1, thickness=-1)
        
        blurred_heatmap = cv2.GaussianBlur(heatmap_accumulator, (81, 81), 0)
        normalized_heatmap = cv2.normalize(blurred_heatmap, None, 0, 255, cv2.NORM_MINMAX, cv2.CV_8U)
        heatmap_img = cv2.applyColorMap(normalized_heatmap, cv2.COLORMAP_JET)
        super_imposed_img = cv2.addWeighted(heatmap_img, 0.5, base_image, 0.5, 0)
        
        bar_w, bar_h = 40, int(video_h * 0.5)
        bar_x, bar_y = video_w - bar_w - 20, (video_h - bar_h) // 2
        gradient = np.arange(0, 256, dtype=np.uint8)[::-1].reshape(256, 1)
        color_bar_jet = cv2.applyColorMap(gradient, cv2.COLORMAP_JET)
        color_bar_resized = cv2.resize(color_bar_jet, (bar_w, bar_h))
        super_imposed_img[bar_y:bar_y+bar_h, bar_x:bar_x+bar_w] = color_bar_resized
        cv2.rectangle(super_imposed_img, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (255,255,255), 2)
        cv2.putText(super_imposed_img, "High", (bar_x - 50, bar_y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
        cv2.putText(super_imposed_img, "Low", (bar_x - 40, bar_y + bar_h - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

        cv2.imwrite(output_path, super_imposed_img)
        return None
    except Exception as e:
        print(traceback.format_exc()); return f"An unexpected error occurred during heatmap export: {e}"

def export_trajectory_image(processed_detections, grid_settings, video_size, grid_transform, output_path, time_gap_seconds, video_fps, frame_sample_rate):
    if video_fps <= 0: return "Cannot generate trajectories, video FPS is zero or invalid."
    try:
        video_w, video_h = video_size; cols, rows = grid_settings['cols'], grid_settings['rows']
        
        # 1. Pre-process and sample all detections
        all_detections_by_frame = defaultdict(list)
        frame_indices = sorted([k for k in processed_detections.keys() if k % frame_sample_rate == 0])
        for frame_idx in frame_indices:
            for det in processed_detections[frame_idx]:
                if det.get('cx') is not None and det.get('cy') is not None:
                    all_detections_by_frame[frame_idx].append({'coords': (float(det['cx']), float(det['cy'])), 'id': None})

        # 2. Assign persistent IDs using nearest-neighbor logic
        next_object_id = 0
        tracked_objects = {}  # {id: {'coords': (x,y), 'last_frame': N}}
        max_distance = (video_w / cols) * 0.3 # Max distance to be considered the same object (30% of tank width)

        for frame_idx in sorted(all_detections_by_frame.keys()):
            current_frame_dets = all_detections_by_frame[frame_idx]
            if not current_frame_dets: continue

            # Remove objects that haven't been seen for a while
            frames_to_disappear = video_fps * time_gap_seconds
            lost_ids = [obj_id for obj_id, data in tracked_objects.items() if frame_idx - data['last_frame'] > frames_to_disappear]
            for obj_id in lost_ids: del tracked_objects[obj_id]

            if not tracked_objects:
                for det in current_frame_dets:
                    det['id'] = next_object_id; tracked_objects[next_object_id] = {'coords': det['coords'], 'last_frame': frame_idx}; next_object_id += 1
                continue

            prev_ids = list(tracked_objects.keys()); prev_coords = [tracked_objects[i]['coords'] for i in prev_ids]
            current_coords = [det['coords'] for det in current_frame_dets]
            if not prev_coords or not current_coords: continue

            dist_matrix = cdist(np.array(prev_coords), np.array(current_coords))
            
            # Use a more stable matching algorithm (Hungarian algorithm would be ideal, but greedy is simpler)
            rows, cols = dist_matrix.shape
            matched_curr_indices = set()
            for r in range(rows):
                if len(matched_curr_indices) == cols: break
                row_data = dist_matrix[r, :]
                
                # Find best match for this previous object
                best_match_idx = np.argmin(row_data)
                if row_data[best_match_idx] < max_distance and best_match_idx not in matched_curr_indices:
                    object_id = prev_ids[r]
                    current_frame_dets[best_match_idx]['id'] = object_id
                    tracked_objects[object_id] = {'coords': current_frame_dets[best_match_idx]['coords'], 'last_frame': frame_idx}
                    matched_curr_indices.add(best_match_idx)

            for i, det in enumerate(current_frame_dets):
                if det['id'] is None:
                    det['id'] = next_object_id; tracked_objects[next_object_id] = {'coords': det['coords'], 'last_frame': frame_idx}; next_object_id += 1
        
        # 3. Group points into final paths based on their persistent ID
        animal_paths = defaultdict(list)
        for frame_idx, dets in all_detections_by_frame.items():
            for det in dets:
                if det['id'] is not None:
                    animal_paths[det['id']].append({'frame_idx': frame_idx, 'point': det['coords']})

        # 4. Draw the trajectories
        untransformed_layer = np.full((video_h, video_w, 3), 255, dtype=np.uint8)
        padding = int(min(video_w, video_h) * 0.05); draw_area_x1, draw_area_y1 = padding, padding
        draw_area_w, draw_area_h = video_w - (2 * padding), video_h - (2 * padding)
        cell_w, cell_h = draw_area_w / cols, draw_area_h / rows
        for r in range(rows):
            for c in range(cols):
                x1, y1 = int(draw_area_x1 + c * cell_w), int(draw_area_y1 + r * cell_h); x2, y2 = int(draw_area_x1 + (c + 1) * cell_w), int(draw_area_y1 + (r + 1) * cell_h)
                cv2.rectangle(untransformed_layer, (x1, y1), (x2, y2), (0, 0, 0), 2)
                tank_num = r * cols + c + 1; cv2.putText(untransformed_layer, f"Tank {tank_num}", (x1 + 15, y1 + 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
        
        if animal_paths:
            np.random.seed(42); colors = {uid: tuple(np.random.randint(0, 220, 3).tolist()) for uid in animal_paths.keys()}
            inverse_transform, _ = grid_transform.inverted()
            for animal_id, detections in animal_paths.items():
                if not detections: continue
                points_to_draw = []
                for det in detections:
                    p = inverse_transform.map(QPointF(det['point'][0], det['point'][1]))
                    scaled_x = draw_area_x1 + (p.x() / video_w) * draw_area_w
                    scaled_y = draw_area_y1 + (p.y() / video_h) * draw_area_h
                    points_to_draw.append((scaled_x, scaled_y))
                
                if len(points_to_draw) > 1:
                    pts = np.array(points_to_draw, np.int32).reshape((-1, 1, 2))
                    cv2.polylines(untransformed_layer, [pts], isClosed=False, color=colors[animal_id], thickness=2)
        
        M = np.float32([[grid_transform.m11(), grid_transform.m12(), grid_transform.dx()], [grid_transform.m21(), grid_transform.m22(), grid_transform.dy()]]);
        final_image = cv2.warpAffine(untransformed_layer, M, (video_w, video_h), borderValue=(255, 255, 255))
        cv2.imwrite(output_path, final_image)
        return None
    except Exception as e:
        print(traceback.format_exc()); return f"An unexpected error occurred during trajectory image export: {e}"
def export_centroid_csv(processed_detections, total_tanks, output_path):
    if not PANDAS_AVAILABLE: return "The 'pandas' library is required. Please run: pip install pandas"
    try:
        frame_data = defaultdict(dict); all_dets = [det for frame_dets in processed_detections.values() for det in frame_dets]
        for det in all_dets:
            if det.get('tank_number') is not None:
                frame, tank = int(det['frame_idx']), int(det['tank_number']); cx, cy = det.get('cx', ''), det.get('cy', ''); adjusted_tank = tank - 1
                if 0 <= adjusted_tank < total_tanks: frame_data[frame][adjusted_tank] = (cx, cy)
        int_frame_data = {int(k): v for k, v in frame_data.items()}; all_frames = sorted(int_frame_data.keys())
        if not all_frames: return "No valid detections with tank numbers found to export."
        output_rows = []
        for frame_idx in range(all_frames[0], all_frames[-1] + 1):
            row_dict = {'position': frame_idx}
            for tank_idx in range(total_tanks):
                tank_coords = int_frame_data.get(frame_idx, {}).get(tank_idx)
                if tank_coords: cx, cy = tank_coords; row_dict[f'x{tank_idx}'] = cx; row_dict[f'y{tank_idx}'] = cy
                else: row_dict[f'x{tank_idx}'] = ''; row_dict[f'y{tank_idx}'] = ''
            output_rows.append(row_dict)
        output_df = pd.DataFrame(output_rows); output_df.to_csv(output_path, index=False, float_format='%.4f')
        return None
    except Exception as e:
        print(traceback.format_exc()); return f"An unexpected error occurred during centroid export: {e}"

def export_to_excel_sheets(processed_detections, output_path):
    if not PANDAS_AVAILABLE: return "The 'pandas' and 'openpyxl' libraries are required. Please run: pip install pandas openpyxl"
    try:
        tank_data = defaultdict(list); all_dets = [det for frame_dets in processed_detections.values() for det in frame_dets]
        for det in all_dets:
            tank_num = det.get('tank_number')
            if tank_num is not None: tank_data[int(tank_num)].append(det)
        if not tank_data: return "No detections with tank numbers found to export."
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            for tank_num in sorted(tank_data.keys()):
                sheet_name = f'Tank_{tank_num}'; tank_df = pd.DataFrame(tank_data[tank_num])
                for col in ['x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'conf']:
                    if col in tank_df.columns: tank_df[col] = pd.to_numeric(tank_df[col], errors='coerce')
                if 'tank_number' in tank_df.columns: tank_df = tank_df.drop(columns=['tank_number'])
                tank_df.to_excel(writer, sheet_name=sheet_name, index=False, float_format='%.4f')
        return None
    except Exception as e:
        print(traceback.format_exc()); return f"An unexpected error occurred during Excel export: {e}"