# EthoGrid_App/core/endpoints_analyzer.py

import math
import numpy as np
import pandas as pd
from collections import defaultdict
from PyQt5.QtCore import QPointF, QLineF

EPSILON = 1e-10

def calculate_turning_angle(p1, p2, p3):
    v1 = (p1[0] - p2[0], p1[1] - p2[1])
    v2 = (p3[0] - p2[0], p3[1] - p2[1])
    dot_product = v1[0] * v2[0] + v1[1] * v2[1]
    mag_v1 = math.sqrt(v1[0]**2 + v1[1]**2)
    mag_v2 = math.sqrt(v2[0]**2 + v2[1]**2)
    if mag_v1 * mag_v2 == 0: return 0.0
    cos_theta = max(-1.0, min(1.0, dot_product / (mag_v1 * mag_v2)))
    angle_rad = math.acos(cos_theta)
    return math.degrees(angle_rad)

def calculate_fractal_dimension_and_entropy(coords_df):
    x_list, y_list = coords_df['cx'], coords_df['cy']
    if len(x_list) < 3: return 1.0, 0.0
    
    delta_x, delta_y, delta_r, thetas = {}, {}, {}, {}
    for i in range(1, len(x_list)):
        temp_x, temp_y = x_list.iloc[i] - x_list.iloc[i-1], y_list.iloc[i] - y_list.iloc[i-1]
        temp_r = math.sqrt(temp_x**2 + temp_y**2)
        delta_x[i], delta_y[i], delta_r[i] = temp_x, temp_y, temp_r
        if i > 1:
            dot = delta_x[i] * delta_x[i-1] + delta_y[i] * delta_y[i-1]
            prod_mag = delta_r[i] * delta_r[i-1]
            value = dot / (prod_mag + EPSILON)
            thetas[i] = math.acos(max(-1, min(1, value))) * 180 / math.pi
            
    points = np.array(list(zip(x_list, y_list)))
    if len(points) < 2: return 1.0, 0.0
    
    min_coords, max_coords = np.min(points, axis=0), np.max(points, axis=0)
    size = np.max(max_coords - min_coords, initial=0.0)
    if size < 1e-6: return 1.0, 0.0
    
    log_size_half = np.log10(size / 2) if (size / 2) > 0 else 0
    scales = np.logspace(0.01, log_size_half, num=10, base=10.0)
    
    counts, valid_scales = [], []
    for scale in scales:
        if scale < 1e-6: continue
        H, _, _ = np.histogram2d(points[:, 0], points[:, 1], bins=(np.arange(min_coords[0], max_coords[0] + scale, scale), np.arange(min_coords[1], max_coords[1] + scale, scale)))
        counts.append(np.sum(H > 0))
        valid_scales.append(scale)

    if len(counts) < 2: return 1.0, 0.0
    
    log_counts = np.log([c for c in counts if c > 0])
    log_scales = np.log([s for i, s in enumerate(valid_scales) if counts[i] > 0])
    
    if len(log_counts) < 2: return 1.0, 0.0

    coeffs = np.polyfit(log_scales, log_counts, 1)
    fractal_dimension = -coeffs[0] if len(coeffs) > 0 and not np.isnan(coeffs[0]) else 1.0

    if not thetas: return fractal_dimension, 0.0
    G_array = np.array(list(thetas.values()))
    p1 = (G_array >= 90).sum() / G_array.size if G_array.size > 0 else 0
    p2 = 1.0 - p1
    entropy = 0.0
    if p1 > 0: entropy -= p1 * np.log2(p1)
    if p2 > 0: entropy -= p2 * np.log2(p2)
    
    return fractal_dimension if not np.isnan(fractal_dimension) else 1.0, entropy if not np.isnan(entropy) else 0.0


def calculate_turning_angle(p1, p2, p3):
    v1 = (p1[0] - p2[0], p1[1] - p2[1]); v2 = (p3[0] - p2[0], p3[1] - p2[1])
    dot_product = v1[0] * v2[0] + v1[1] * v2[1]; mag_v1 = math.sqrt(v1[0]**2 + v1[1]**2); mag_v2 = math.sqrt(v2[0]**2 + v2[1]**2)
    if mag_v1 * mag_v2 == 0: return 0.0
    cos_theta = max(-1.0, min(1.0, dot_product / (mag_v1 * mag_v2))); angle_rad = math.acos(cos_theta)
    return math.degrees(angle_rad)

def calculate_fractal_dimension_and_entropy(coords_df):
    x_list, y_list = coords_df['cx'], coords_df['cy']
    if len(x_list) < 3: return 1.0, 0.0
    delta_x, delta_y, delta_r, thetas = {}, {}, {}, {}
    for i in range(1, len(x_list)):
        temp_x, temp_y = x_list.iloc[i] - x_list.iloc[i-1], y_list.iloc[i] - y_list.iloc[i-1]
        temp_r = math.sqrt(temp_x**2 + temp_y**2)
        delta_x[i], delta_y[i], delta_r[i] = temp_x, temp_y, temp_r
        if i > 1:
            dot = delta_x[i] * delta_x[i-1] + delta_y[i] * delta_y[i-1]; prod_mag = delta_r[i] * delta_r[i-1]
            value = dot / (prod_mag + EPSILON); thetas[i] = math.acos(max(-1, min(1, value))) * 180 / math.pi
    points = np.array(list(zip(x_list, y_list)))
    if len(points) < 2: return 1.0, 0.0
    min_coords, max_coords = np.min(points, axis=0), np.max(points, axis=0)
    size = np.max(max_coords - min_coords, initial=0.0)
    if size < 1e-6: return 1.0, 0.0
    log_size_half = np.log10(size / 2) if (size / 2) > 0 else 0
    scales = np.logspace(0.01, log_size_half, num=10, base=10.0)
    counts, valid_scales = [], []
    for scale in scales:
        if scale < 1e-6: continue
        H, _, _ = np.histogram2d(points[:, 0], points[:, 1], bins=(np.arange(min_coords[0], max_coords[0] + scale, scale), np.arange(min_coords[1], max_coords[1] + scale, scale)))
        counts.append(np.sum(H > 0)); valid_scales.append(scale)
    if len(counts) < 2: return 1.0, 0.0
    log_counts = np.log([c for c in counts if c > 0]); log_scales = np.log([s for i, s in enumerate(valid_scales) if counts[i] > 0])
    if len(log_counts) < 2: return 1.0, 0.0
    coeffs = np.polyfit(log_scales, log_counts, 1)
    fractal_dimension = -coeffs[0] if len(coeffs) > 0 and not np.isnan(coeffs[0]) else 1.0
    if not thetas: return fractal_dimension, 0.0
    G_array = np.array(list(thetas.values()))
    p1 = (G_array >= 90).sum() / G_array.size if G_array.size > 0 else 0; p2 = 1.0 - p1; entropy = 0.0
    if p1 > 0: entropy -= p1 * np.log2(p1)
    if p2 > 0: entropy -= p2 * np.log2(p2)
    return fractal_dimension if not np.isnan(fractal_dimension) else 1.0, entropy if not np.isnan(entropy) else 0.0

class EndpointsAnalyzer:
    def __init__(self, tank_specific_df, params):
        self.df = tank_specific_df.copy()
        self.params = params
        self.results = {}

    def analyze(self):
        analysis_mode = self.params.get('analysis_mode', 'Side View')
        self.df = self.df.sort_values(by='frame_idx').reset_index(drop=True)
        cx_np, cy_np, frame_idx_np = self.df['cx'].to_numpy(), self.df['cy'].to_numpy(), self.df['frame_idx'].to_numpy()
        
        if len(cx_np) > 1:
            distances = np.sqrt(np.diff(cx_np)**2 + np.diff(cy_np)**2) / self.params['conversion_rate']
            self.results['Total Distance (cm)'] = np.sum(distances)
            frame_rate = self.params['frame_rate']; time_intervals = np.diff(frame_idx_np) / frame_rate
            speeds = np.divide(distances, time_intervals, out=np.zeros_like(distances), where=time_intervals!=0)
            self.results['Average Speed (cm/s)'] = np.mean(speeds) if len(speeds) > 0 else 0.0
        else:
            self.results['Total Distance (cm)'] = 0.0; speeds = np.array([]); self.results['Average Speed (cm/s)'] = 0.0; time_intervals = np.array([])

        if analysis_mode == 'Side View':
            self._analyze_side_view(speeds, time_intervals, frame_idx_np)
        
        self._analyze_top_view(cx_np, cy_np)

        fd, entropy = calculate_fractal_dimension_and_entropy(self.df)
        self.results['Fractal Dimension'] = fd; self.results['Entropy'] = entropy

        final_results = {}
        for endpoint_name in self.params['selected_endpoints']:
            if endpoint_name in self.results:
                value = self.results[endpoint_name]
                final_results[endpoint_name] = 0.0 if isinstance(value, (float, np.floating)) and np.isnan(value) else value
        
        return {k: f"{v:.4f}" if isinstance(v, (float, np.floating)) else v for k, v in final_results.items()}

    def _analyze_side_view(self, speeds, time_intervals, frame_idx_np):
        total_duration = (frame_idx_np[-1] - frame_idx_np[0]) / self.params['frame_rate'] if len(frame_idx_np) > 1 else 0.0
        
        rapid_mask = speeds > self.params['rapid_threshold']
        freezing_mask = speeds <= self.params['freezing_threshold']
        swimming_mask = (~rapid_mask) & (~freezing_mask)
        
        time_rapid = np.sum(time_intervals[rapid_mask]) if len(time_intervals) > 0 else 0.0
        time_swimming = np.sum(time_intervals[swimming_mask]) if len(time_intervals) > 0 else 0.0
        time_freezing = total_duration - time_rapid - time_swimming
        
        self.results['Rapid Time (%)'] = (time_rapid / total_duration) * 100 if total_duration > 0 else 0.0
        self.results['Swimming Time (%)'] = (time_swimming / total_duration) * 100 if total_duration > 0 else 0.0
        self.results['Freezing Time (%)'] = max(0.0, (time_freezing / total_duration) * 100) if total_duration > 0 else 0.0
        
        tank_corners = self.params['tank_corners']
        p1, p2, p3, p4 = (QPointF(c[0], c[1]) for c in tank_corners)
        
        axis = self.params['side_view_axis']
        if axis == 'Top-Bottom': start_point, end_point = (p1 + p2) / 2, (p4 + p3) / 2
        elif axis == 'Left-Top to Right-Bottom': start_point, end_point = p1, p3
        else: start_point, end_point = p4, p2 # Left-Bottom to Right-Top

        line_vec = np.array([end_point.x() - start_point.x(), end_point.y() - start_point.y()])
        line_mag_sq = line_vec[0]**2 + line_vec[1]**2
        
        def get_zone_progress(row):
            if line_mag_sq < EPSILON: return 0.5
            point_vec = np.array([row['cx'] - start_point.x(), row['cy'] - start_point.y()])
            progress = np.dot(point_vec, line_vec) / line_mag_sq
            return np.clip(progress, 0.0, 1.0)
        self.df['progress'] = self.df.apply(get_zone_progress, axis=1)
        
        zone1_percent = self.params['zone1_percent'] / 100.0; zone2_percent = self.params['zone2_percent'] / 100.0
        top_mask = (self.df['progress'] <= zone1_percent).to_numpy(); bottom_mask = (self.df['progress'] >= (1.0 - zone2_percent)).to_numpy()
        middle_mask = (~top_mask) & (~bottom_mask)
        time_in_top = np.sum(top_mask) / self.params['frame_rate']; time_in_middle = np.sum(middle_mask) / self.params['frame_rate']; time_in_bottom = np.sum(bottom_mask) / self.params['frame_rate']
        
        self.results['Time in Top (%)'] = (time_in_top / total_duration) * 100 if total_duration > 0 else 0.0
        self.results['Time in Middle (%)'] = (time_in_middle / total_duration) * 100 if total_duration > 0 else 0.0
        self.results['Time in Bottom (%)'] = (time_in_bottom / total_duration) * 100 if total_duration > 0 else 0.0
        self.results['Entries to Top'] = (top_mask[:-1] < top_mask[1:]).sum()

    def _analyze_top_view(self, cx_np, cy_np):
        tank_center = self.params['tank_center']
        distances_to_center = np.sqrt((cx_np - tank_center[0])**2 + (cy_np - tank_center[1])**2)
        self.results['Average Distance from Center (cm)'] = (np.mean(distances_to_center) / self.params['conversion_rate']) if len(distances_to_center) > 0 else 0.0
        if len(cx_np) > 2:
            coords = np.column_stack((cx_np, cy_np))
            angles = [calculate_turning_angle(coords[i], coords[i+1], coords[i+2]) for i in range(len(coords) - 2)]
            self.results['Total Absolute Turn Angle (degree)'] = np.sum(np.abs(angles))
            angular_velocities = np.abs(angles) / (1 / self.params['frame_rate']) if self.params['frame_rate'] > 0 else np.zeros(len(angles))
            self.results['Average Angular Velocity (degree/s)'] = np.mean(angular_velocities) if len(angular_velocities) > 0 else 0.0
        else:
            self.results['Total Absolute Turn Angle (degree)'] = 0.0; self.results['Average Angular Velocity (degree/s)'] = 0.0
        self.results['Meandering (degree/m)'] = (self.results['Total Absolute Turn Angle (degree)'] / (self.results['Total Distance (cm)'] / 100)) if self.results['Total Distance (cm)'] > 0 else 0.0