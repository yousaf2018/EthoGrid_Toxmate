# EthoGrid_App/main_window.py

import os
import sys
import cv2
import csv
import json
import numpy as np
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QImage, QPixmap

# Local imports
from workers.video_loader import VideoLoader
from workers.video_saver import VideoSaver
from workers.detection_processor import DetectionProcessor
from widgets.timeline_widget import TimelineWidget
from core.grid_manager import GridManager
from widgets.batch_dialog import BatchProcessDialog
from widgets.yolo_inference_dialog import YoloInferenceDialog
from widgets.yolo_segmentation_dialog import YoloSegmentationDialog
from core.data_exporter import export_centroid_csv, export_to_excel_sheets, PANDAS_AVAILABLE
from widgets.analysis_dialog import AnalysisDialog
from widgets.video_splitter_dialog import VideoSplitterDialog
from widgets.frame_extractor_dialog import FrameExtractorDialog # Import the new dialog
from widgets.stats_dialog import StatsDialog
from widgets.updater_dialog import UpdaterDialog
from widgets.video_resizer_dialog import VideoResizerDialog

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

class VideoPlayer(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(VideoPlayer, self).__init__(parent)
        self.setWindowTitle("EthoGrid-ToxMate")
        
        logo_path = resource_path("images/logo.png")
        if os.path.exists(logo_path): self.setWindowIcon(QtGui.QIcon(logo_path))
        else: print(f"Warning: Logo not found at '{logo_path}'.")

        self.raw_detections, self.processed_detections, self.csv_headers = {}, {}, []
        self.current_frame, self.current_frame_idx, self.total_frames = None, 0, 0
        self.video_size = (0, 0); self.behavior_colors = {}
        self.predefined_colors = [(31,119,180),(255,127,14),(44,160,44),(214,39,40),(148,103,189),(140,86,75),(227,119,194),(127,127,127),(188,189,34),(23,190,207)]
        self.grid_settings = {'cols': 5, 'rows': 2}; self.selected_cells = set(); self.line_thickness = 2
        self.dragging_mode, self.last_mouse_pos = None, None
        self.grid_manager = GridManager(); self.video_loader, self.video_saver, self.detection_processor = None, None, None
        self.timeline_widget, self.legend_group_box = None, None
        
        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        self.setStyleSheet("""
            QWidget { background-color: #2b2b2b; color: #e0e0e0; font-family: Segoe UI; font-size: 12px; border: none; }
            QGroupBox { border: 1px solid #4a4a4a; margin-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 3px; }
            QLabel#statusLabel { color: #ffc107; background-color: transparent; border: none; }
            QLabel#videoLabel { background-color: #1e1e1e; border: 1px solid #3e3e3e; }
            QPushButton { background-color: #3a3a3a; border: 1px solid #4a4a4a; border-radius: 3px; padding: 5px 10px; min-width: 80px; }
            QPushButton:hover { background-color: #4a4a4a; }
            QPushButton:pressed { background-color: #2a2a2a; }
            QPushButton:disabled { background-color: #2f2f2f; color: #6a6a6a; }
            QSlider::groove:horizontal { height: 6px; background: #3a3a3a; border-radius: 3px; }
            QSlider::handle:horizontal { width: 14px; height: 14px; background: #5a5a5a; border-radius: 7px; margin: -4px 0; }
            QSpinBox, QLineEdit, QDoubleSpinBox { background-color: #252525; border: 1px solid #3a3a3a; border-radius: 3px; padding: 3px 5px; selection-background-color: #3a6ea5; }
            QProgressBar { border: 1px solid #3a3a3a; border-radius: 3px; text-align: center; }
            QProgressBar::chunk { background-color: #3a6ea5; width: 10px; }
        """)
        self.video_label = QtWidgets.QLabel(); self.video_label.setObjectName("videoLabel"); self.video_label.setAlignment(QtCore.Qt.AlignCenter); self.video_label.setMinimumSize(640, 480)
        self.status_label = QtWidgets.QLabel(""); self.status_label.setObjectName("statusLabel"); self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.play_btn, self.pause_btn, self.stop_btn = QtWidgets.QPushButton("▶ Play"), QtWidgets.QPushButton("⏸ Pause"), QtWidgets.QPushButton("⏹ Stop")
        self.frame_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.frame_slider.setEnabled(False)
        self.frame_label = QtWidgets.QLabel("Frame: 0/0"); self.timeline_widget = TimelineWidget(self)
        self.progress_bar = QtWidgets.QProgressBar(); self.progress_bar.setRange(0, 100); self.progress_bar.setTextVisible(False)
        self.legend_group_box = QtWidgets.QGroupBox("Behavior Legend"); self.legend_layout = QtWidgets.QVBoxLayout(); self.legend_layout.setAlignment(QtCore.Qt.AlignTop); self.legend_group_box.setLayout(self.legend_layout)
        grid_config_group = QtWidgets.QGroupBox("Tank Configuration")
        self.grid_cols_spin, self.grid_rows_spin = QtWidgets.QSpinBox(), QtWidgets.QSpinBox(); self.grid_cols_spin.setRange(1, 20); self.grid_cols_spin.setValue(5); self.grid_rows_spin.setRange(1, 20); self.grid_rows_spin.setValue(2)
        self.line_thickness_spin = QtWidgets.QSpinBox(); self.line_thickness_spin.setRange(1, 5); self.line_thickness_spin.setValue(2)
        self.reset_grid_btn = QtWidgets.QPushButton("Reset Grid")
        self.rotate_slider, self.scale_x_slider, self.scale_y_slider, self.move_x_slider, self.move_y_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal), QtWidgets.QSlider(QtCore.Qt.Horizontal), QtWidgets.QSlider(QtCore.Qt.Horizontal), QtWidgets.QSlider(QtCore.Qt.Horizontal), QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.rotate_slider.setRange(-180, 180); self.scale_x_slider.setRange(10, 200); self.scale_y_slider.setRange(10, 200); self.move_x_slider.setRange(-100, 100); self.move_y_slider.setRange(-100, 100)
        self.rotate_slider.setValue(0); self.scale_x_slider.setValue(100); self.scale_y_slider.setValue(100); self.move_x_slider.setValue(0); self.move_y_slider.setValue(0)
        
        self.processing_options_group = QtWidgets.QGroupBox("Processing Options")
        self.max_animals_spinbox = QtWidgets.QSpinBox(); self.max_animals_spinbox.setToolTip("Enforce a maximum number of animals per tank. Detections with the highest confidence will be kept."); self.max_animals_spinbox.setRange(1, 10); self.max_animals_spinbox.setValue(1)
        self.apply_filter_btn = QtWidgets.QPushButton("Apply Filter")

        self.tank_selection_label = QtWidgets.QLabel("Selected Tanks: None"); self.select_all_btn, self.clear_selection_btn = QtWidgets.QPushButton("Select All"), QtWidgets.QPushButton("Clear Selection")
        self.inference_btn = QtWidgets.QPushButton("🔮 Run YOLO Detection..."); self.segmentation_btn = QtWidgets.QPushButton("🎨 Run YOLO Segmentation..."); self.load_video_btn, self.load_csv_btn = QtWidgets.QPushButton("🎬 Load Video"), QtWidgets.QPushButton("📄 Load Detections")
        self.batch_process_btn = QtWidgets.QPushButton("🚀 Batch Process...")
        self.analysis_btn = QtWidgets.QPushButton("📈 Endpoints Analysis...")
        self.stats_btn = QtWidgets.QPushButton("📊 Statistical Analysis...")
        self.video_splitter_btn = QtWidgets.QPushButton("✂️ Video Splitter...")
        self.frame_extractor_btn = QtWidgets.QPushButton("🖼️ Frame Extractor...")
        self.video_resizer_btn = QtWidgets.QPushButton("🔍 Quality Control...")
        self.update_btn = QtWidgets.QPushButton("🔄 Check for Updates")
        self.save_csv_btn, self.export_video_btn = QtWidgets.QPushButton("📝 Save w/ Tanks"), QtWidgets.QPushButton("📹 Export Video"); self.save_csv_btn.setEnabled(False); self.export_video_btn.setEnabled(False)
        self.save_centroid_csv_btn = QtWidgets.QPushButton("📈 Save Centroid CSV"); self.save_centroid_csv_btn.setEnabled(False)        
        self.save_excel_btn = QtWidgets.QPushButton("📗 Save to Excel"); self.save_excel_btn.setEnabled(False)
        if not PANDAS_AVAILABLE:
            self.save_centroid_csv_btn.setToolTip("Install 'pandas' to enable this feature.")
            self.save_excel_btn.setToolTip("Install 'pandas' and 'openpyxl' to enable this feature.")
        self.save_settings_btn, self.load_settings_btn = QtWidgets.QPushButton("💾 Save Settings"), QtWidgets.QPushButton("📂 Load Settings")
        
        main_layout = QtWidgets.QVBoxLayout(self)
        processing_toolbar = QtWidgets.QHBoxLayout();
        logo_label = QtWidgets.QLabel(); logo_path = resource_path("images/logo.png")
        if os.path.exists(logo_path): logo_label.setPixmap(QtGui.QPixmap(logo_path).scaled(32, 32, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        # processing_toolbar.addWidget(logo_label)
        processing_toolbar.addWidget(self.inference_btn); processing_toolbar.addWidget(self.segmentation_btn); processing_toolbar.addWidget(self.batch_process_btn);processing_toolbar.addWidget(self.analysis_btn);processing_toolbar.addWidget(self.stats_btn);processing_toolbar.addWidget(self.frame_extractor_btn);processing_toolbar.addWidget(self.video_splitter_btn);processing_toolbar.addWidget(self.update_btn);processing_toolbar.addWidget(self.video_resizer_btn); processing_toolbar.addStretch(); 
        file_toolbar = QtWidgets.QHBoxLayout(); file_toolbar.addWidget(self.load_video_btn); file_toolbar.addWidget(self.load_csv_btn); file_toolbar.addWidget(self.save_csv_btn); file_toolbar.addWidget(self.save_centroid_csv_btn); file_toolbar.addWidget(self.save_excel_btn); file_toolbar.addWidget(self.export_video_btn); file_toolbar.addStretch(); file_toolbar.addWidget(self.load_settings_btn); file_toolbar.addWidget(self.save_settings_btn)
        main_layout.addLayout(processing_toolbar); main_layout.addLayout(file_toolbar)
        processing_toolbar.addStretch()

        main_h_layout = QtWidgets.QHBoxLayout(); left_pane_layout = QtWidgets.QVBoxLayout(); left_pane_layout.addWidget(self.video_label, stretch=1); left_pane_layout.addWidget(self.status_label)
        controls_layout = QtWidgets.QHBoxLayout(); controls_layout.addWidget(self.play_btn); controls_layout.addWidget(self.pause_btn); controls_layout.addWidget(self.stop_btn); controls_layout.addWidget(self.frame_slider, stretch=1); controls_layout.addWidget(self.frame_label)
        left_pane_layout.addLayout(controls_layout); left_pane_layout.addWidget(self.timeline_widget); left_pane_layout.addWidget(self.progress_bar)
        right_pane_widget = QtWidgets.QWidget(); right_pane_widget.setFixedWidth(280); right_pane_layout = QtWidgets.QVBoxLayout(right_pane_widget); right_pane_layout.addWidget(self.legend_group_box)
        grid_config_layout = QtWidgets.QGridLayout(grid_config_group); grid_config_layout.addWidget(QtWidgets.QLabel("Columns:"), 0, 0); grid_config_layout.addWidget(self.grid_cols_spin, 0, 1); grid_config_layout.addWidget(QtWidgets.QLabel("Rows:"), 1, 0); grid_config_layout.addWidget(self.grid_rows_spin, 1, 1); grid_config_layout.addWidget(QtWidgets.QLabel("Line Thickness:"), 2, 0); grid_config_layout.addWidget(self.line_thickness_spin, 2, 1); grid_config_layout.addWidget(QtWidgets.QLabel("Rotation:"), 3, 0); grid_config_layout.addWidget(self.rotate_slider, 3, 1); grid_config_layout.addWidget(QtWidgets.QLabel("Scale X:"), 4, 0); grid_config_layout.addWidget(self.scale_x_slider, 4, 1); grid_config_layout.addWidget(QtWidgets.QLabel("Scale Y:"), 5, 0); grid_config_layout.addWidget(self.scale_y_slider, 5, 1); grid_config_layout.addWidget(QtWidgets.QLabel("Move X:"), 6, 0); grid_config_layout.addWidget(self.move_x_slider, 6, 1); grid_config_layout.addWidget(QtWidgets.QLabel("Move Y:"), 7, 0); grid_config_layout.addWidget(self.move_y_slider, 7, 1); grid_config_layout.addWidget(self.reset_grid_btn, 8, 0, 1, 2)
        right_pane_layout.addWidget(grid_config_group)
        processing_layout = QtWidgets.QHBoxLayout(self.processing_options_group)
        processing_layout.addWidget(QtWidgets.QLabel("Max Animals/Tank:")); processing_layout.addWidget(self.max_animals_spinbox); processing_layout.addWidget(self.apply_filter_btn)
        right_pane_layout.addWidget(self.processing_options_group)
        selection_layout = QtWidgets.QHBoxLayout(); selection_layout.addWidget(self.tank_selection_label, stretch=1); selection_layout.addWidget(self.select_all_btn); selection_layout.addWidget(self.clear_selection_btn)
        right_pane_layout.addLayout(selection_layout); right_pane_layout.addStretch()
        main_h_layout.addLayout(left_pane_layout, stretch=1); main_h_layout.addWidget(right_pane_widget); main_layout.addLayout(main_h_layout)
        self.setMinimumSize(1280, 800)

    def setup_connections(self):
        self.inference_btn.clicked.connect(self.open_yolo_dialog); self.segmentation_btn.clicked.connect(self.open_yolo_segmentation_dialog); self.batch_process_btn.clicked.connect(self.open_batch_dialog)
        self.load_video_btn.clicked.connect(self.load_video); self.load_csv_btn.clicked.connect(self.load_detections); self.save_csv_btn.clicked.connect(self.save_detections_with_tanks); self.export_video_btn.clicked.connect(self.export_video); self.save_centroid_csv_btn.clicked.connect(self.save_centroid_csv); self.save_excel_btn.clicked.connect(self.save_to_excel); self.save_settings_btn.clicked.connect(self.save_settings); self.load_settings_btn.clicked.connect(self.load_settings)
        self.play_btn.clicked.connect(self.start_playback); self.pause_btn.clicked.connect(self.pause_playback); self.stop_btn.clicked.connect(self.stop_playback); self.frame_slider.sliderMoved.connect(self.seek_frame)
        self.grid_cols_spin.valueChanged.connect(self.update_grid_settings); self.grid_rows_spin.valueChanged.connect(self.update_grid_settings); self.line_thickness_spin.valueChanged.connect(self.update_line_thickness); self.reset_grid_btn.clicked.connect(self.reset_grid_transform_and_ui)
        self.rotate_slider.valueChanged.connect(self.update_grid_rotation); self.scale_x_slider.valueChanged.connect(self.update_grid_scale); self.scale_y_slider.valueChanged.connect(self.update_grid_scale); self.move_x_slider.valueChanged.connect(self.update_grid_position); self.move_y_slider.valueChanged.connect(self.update_grid_position)
        self.rotate_slider.sliderReleased.connect(self.start_detection_processing); self.scale_x_slider.sliderReleased.connect(self.start_detection_processing); self.scale_y_slider.sliderReleased.connect(self.start_detection_processing); self.move_x_slider.sliderReleased.connect(self.start_detection_processing); self.move_y_slider.sliderReleased.connect(self.start_detection_processing)
        self.select_all_btn.clicked.connect(self.select_all_tanks); self.clear_selection_btn.clicked.connect(self.clear_tank_selection); self.apply_filter_btn.clicked.connect(self.start_detection_processing)
        self.grid_manager.transform_updated.connect(self.update_display)
        self.video_label.mousePressEvent = self.handle_mouse_press; self.video_label.mouseMoveEvent = self.handle_mouse_move; self.video_label.mouseReleaseEvent = self.handle_mouse_release
        self.analysis_btn.clicked.connect(self.open_analysis_dialog)
        self.video_splitter_btn.clicked.connect(self.open_video_splitter_dialog)
        self.frame_extractor_btn.clicked.connect(self.open_frame_extractor_dialog)
        self.stats_btn.clicked.connect(self.open_stats_dialog)
        self.update_btn.clicked.connect(self.open_updater_dialog)
        self.video_resizer_btn.clicked.connect(self.open_video_resizer_dialog)
        
    def open_yolo_dialog(self): dialog = YoloInferenceDialog(self); dialog.exec_()
    def open_yolo_segmentation_dialog(self): dialog = YoloSegmentationDialog(self); dialog.exec_()
    def open_batch_dialog(self): dialog = BatchProcessDialog(self); dialog.exec_()
        
    def open_stats_dialog(self):
        dialog = StatsDialog(self)
        dialog.exec_()

    def load_detections(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Detection CSV", "", "CSV Files (*.csv)");
        if file_path:
            try:
                detections = {};
                with open(file_path, newline="", encoding='utf-8') as f:
                    reader = csv.DictReader(f); self.csv_headers = reader.fieldnames[:]
                    coord_cols = ['x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'conf']
                    for row in reader:
                        idx = int(float(row["frame_idx"]))
                        for col in coord_cols:
                            if col in row and row[col]:
                                try: row[col] = float(row[col])
                                except (ValueError, TypeError): row[col] = None
                        detections.setdefault(idx, []).append(row)
                self.raw_detections = detections; self.processed_detections = {}; self.behavior_colors.clear()
                all_behaviors = sorted(list(set(det['class_name'] for dets in self.raw_detections.values() for det in dets)))
                for behavior in all_behaviors: self.get_color_for_behavior(behavior)
                self.update_legend_widget(); self.start_detection_processing(); QtWidgets.QMessageBox.information(self, "Success", f"Loaded {len(detections)} frames of detections.")
            except Exception as e: self.show_error(f"Error loading detections: {str(e)}")

    def save_detections_with_tanks(self):
        if not self.processed_detections: self.show_error("Please load and process detections before saving."); return
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Detections with Tank Info", "detections_with_tanks.csv", "CSV Files (*.csv)")
        if not file_path: return
        try:
            all_detections = [det for frame_dets in self.processed_detections.values() for det in frame_dets]
            new_headers = self.csv_headers[:] if self.csv_headers and all_detections else list(all_detections[0].keys())
            for key in ['tank_number', 'cx', 'cy']:
                if key not in new_headers: new_headers.append(key)
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=new_headers, extrasaction='ignore'); writer.writeheader()
                for det in all_detections:
                    row_to_write = det.copy()
                    for key in ['x1', 'y1', 'x2', 'y2', 'cx', 'cy']:
                        if key in row_to_write and isinstance(row_to_write[key], float):
                            row_to_write[key] = f"{row_to_write[key]:.4f}"
                    writer.writerow(row_to_write)
            QtWidgets.QMessageBox.information(self, "Success", f"Successfully saved to:\n{file_path}")
        except Exception as e: self.show_error(f"Failed to save file: {str(e)}")

    def save_centroid_csv(self):
        if not self.processed_detections: self.show_error("Please load and process detections before saving."); return
        default_name = "output_centroids_wide.csv"
        if self.video_loader and self.video_loader.video_path: default_name = f"{os.path.splitext(os.path.basename(self.video_loader.video_path))[0]}_centroids_wide.csv"
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Centroid CSV (Wide Format)", default_name, "CSV Files (*.csv)")
        if not file_path: return
        self.status_label.setText("Exporting centroid CSV...")
        error_msg = export_centroid_csv(self.processed_detections, self.grid_settings['cols'] * self.grid_settings['rows'], file_path)
        self.status_label.setText("")
        if error_msg: self.show_error(error_msg)
        else: QtWidgets.QMessageBox.information(self, "Success", f"Centroid CSV saved successfully to:\n{file_path}")
    
    # ### NEW METHOD ###
    def open_analysis_dialog(self):
        dialog = AnalysisDialog(self)
        dialog.exec_()
    # ### NEW METHOD ###
    def open_video_splitter_dialog(self):
        dialog = VideoSplitterDialog(self)
        dialog.exec_()
    
    def open_video_resizer_dialog(self):
        dialog = VideoResizerDialog(self)
        dialog.exec_()

    def open_updater_dialog(self):
        dialog = UpdaterDialog(self)
        dialog.exec_()
        
    def closeEvent(self, event):
        # Simple close is fine now
        event.accept()

    # ### NEW METHOD ###
    def open_frame_extractor_dialog(self):
        dialog = FrameExtractorDialog(self)
        dialog.exec_()
    def save_to_excel(self):
        if not self.processed_detections: self.show_error("Please load and process detections before exporting to Excel."); return
        default_name = "output_by_tank.xlsx"
        if self.video_loader and self.video_loader.video_path: default_name = f"{os.path.splitext(os.path.basename(self.video_loader.video_path))[0]}_by_tank.xlsx"
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save to Excel by Tank", default_name, "Excel Files (*.xlsx)")
        if not file_path: return
        self.status_label.setText("Exporting to Excel...")
        error_msg = export_to_excel_sheets(self.processed_detections, file_path)
        self.status_label.setText("")
        if error_msg: self.show_error(error_msg)
        else: QtWidgets.QMessageBox.information(self, "Success", f"Data saved successfully to:\n{file_path}")

    def export_video(self):
        if not self.video_loader or not self.video_loader.video_path or not self.processed_detections: self.show_error("Please load a video and detections first."); return
        dialog = QtWidgets.QDialog(self); dialog.setWindowTitle("Export Video Options"); layout = QtWidgets.QVBoxLayout(dialog)
        checkbox = QtWidgets.QCheckBox("Include Overlays (Legend and Timeline)"); checkbox.setChecked(True); layout.addWidget(checkbox)
        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel); button_box.accepted.connect(dialog.accept); button_box.rejected.connect(dialog.reject); layout.addWidget(button_box)
        if not dialog.exec_() == QtWidgets.QDialog.Accepted: return
        draw_overlays_option = checkbox.isChecked()
        default_name = os.path.splitext(os.path.basename(self.video_loader.video_path))[0] + "_annotated.mp4"
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Annotated Video", default_name, "MP4 Video Files (*.mp4);;AVI Video Files (*.avi)")
        if not file_path: return
        self.toggle_controls(False); self.progress_bar.setValue(0); self.progress_bar.setFormat("Exporting video... %p%"); self.progress_bar.setTextVisible(True)
        self.video_saver = VideoSaver(source_video_path=self.video_loader.video_path, output_video_path=file_path, detections=self.processed_detections, grid_settings=self.grid_settings, grid_transform=self.grid_manager.transform, behavior_colors=self.behavior_colors, video_size=self.video_size, fps=self.video_loader.fps, line_thickness=self.line_thickness, selected_cells=self.selected_cells, timeline_segments=self.timeline_widget.timeline_segments, draw_grid=False, draw_overlays=draw_overlays_option, parent=self)
        self.video_saver.progress_updated.connect(self.progress_bar.setValue); self.video_saver.finished.connect(self.on_video_export_finished); self.video_saver.error_occurred.connect(self.on_video_export_error); self.video_saver.start()

    def _update_button_states(self):
        is_processing = self.detection_processor is not None and self.detection_processor.isRunning()
        self.load_video_btn.setEnabled(not is_processing); self.load_csv_btn.setEnabled(not is_processing); self.batch_process_btn.setEnabled(not is_processing); self.inference_btn.setEnabled(not is_processing); self.segmentation_btn.setEnabled(not is_processing)
        can_save = self.total_frames > 0 and bool(self.processed_detections) and not is_processing
        self.save_csv_btn.setEnabled(can_save); self.export_video_btn.setEnabled(can_save); self.save_centroid_csv_btn.setEnabled(can_save and PANDAS_AVAILABLE); self.save_excel_btn.setEnabled(can_save and PANDAS_AVAILABLE); self.save_settings_btn.setEnabled(True); self.toggle_controls(not is_processing)

    def update_display(self):
        if self.current_frame is None: return
        try:
            frame = self.current_frame.copy(); overlay = frame.copy(); h, w, _ = frame.shape; current_transform = self.grid_manager.transform
            def transform_point(x, y): p = current_transform.map(QPointF(x, y)); return int(p.x()), int(p.y())
            for i in range(self.grid_settings['cols'] + 1): cv2.line(frame, transform_point(w*i/self.grid_settings['cols'],0), transform_point(w*i/self.grid_settings['cols'],h), (0,255,0), self.line_thickness)
            for i in range(self.grid_settings['rows'] + 1): cv2.line(frame, transform_point(0,h*i/self.grid_settings['rows']), transform_point(w,h*i/self.grid_settings['rows']), (0,255,0), self.line_thickness)
            center_px = self.grid_manager.center.x() * w, self.grid_manager.center.y() * h; cv2.circle(frame, (int(center_px[0]), int(center_px[1])), 8, (0, 0, 255), -1)
            has_drawn_mask = False
            if self.current_frame_idx in self.processed_detections:
                for det in self.processed_detections[self.current_frame_idx]:
                    if det.get('tank_number') is not None and (not self.selected_cells or str(det['tank_number']) in self.selected_cells):
                        color_bgr = self.behavior_colors.get(det["class_name"], (128,128,128))[::-1]; x1, y1 = float(det["x1"]), float(det["y1"])
                        if 'polygon' in det and det['polygon']:
                            try:
                                poly_points = np.array([list(map(int, p.split(','))) for p in det['polygon'].split(';')], dtype=np.int32)
                                cv2.fillPoly(overlay, [poly_points], color_bgr); has_drawn_mask = True
                            except: 
                                x2, y2 = float(det["x2"]), float(det["y2"]); cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color_bgr, 2)
                        else:
                            x2, y2 = float(det["x2"]), float(det["y2"]); cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color_bgr, 2)
                        if det.get('cx') is not None and det.get('cy') is not None:
                            cx_float, cy_float = float(det['cx']), float(det['cy']); cv2.circle(frame, (int(round(cx_float)), int(round(cy_float))), 8, (0, 0, 255), -1)
                        label = f"{det['tank_number']}"; font_face, f_scale, f_thick = cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2; (t_w, t_h), _ = cv2.getTextSize(label, font_face, f_scale, f_thick)
                        cv2.rectangle(frame, (int(x1), int(y1) - t_h - 12), (int(x1) + t_w, int(y1)), color_bgr, -1); cv2.putText(frame, label, (int(x1), int(y1) - 7), font_face, f_scale, (0,0,0), f_thick, cv2.LINE_AA)
            if has_drawn_mask: frame = cv2.addWeighted(overlay, 0.4, frame, 0.6, 0)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB); qimg = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888); pixmap = QPixmap.fromImage(qimg).scaled(self.video_label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation); self.video_label.setPixmap(pixmap)
        except Exception as e: print(f"Error updating display: {e}")

    def get_color_for_behavior(self, behavior_name):
        if behavior_name not in self.behavior_colors: self.behavior_colors[behavior_name] = self.predefined_colors[len(self.behavior_colors) % len(self.predefined_colors)]
        return self.behavior_colors[behavior_name]
    def update_legend_widget(self):
        while self.legend_layout.count():
            child = self.legend_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
            elif child.layout():
                while child.layout().count() > 0:
                    sub_child = child.layout().takeAt(0)
                    if sub_child.widget(): sub_child.widget().deleteLater()
        for behavior, color_rgb in sorted(self.behavior_colors.items()):
            item_layout = QtWidgets.QHBoxLayout(); color_label = QtWidgets.QLabel(); color_label.setFixedSize(20, 20); color_label.setStyleSheet(f"background-color: rgb({color_rgb[0]}, {color_rgb[1]}, {color_rgb[2]}); border: 1px solid #5a5a5a;"); item_layout.addWidget(color_label); item_layout.addWidget(QtWidgets.QLabel(behavior), stretch=1); self.legend_layout.addLayout(item_layout)
    def start_playback(self):
        if self.video_loader: self.video_loader.set_playing(True)
    def pause_playback(self):
        if self.video_loader: self.video_loader.set_playing(False)
    def stop_playback(self):
        if self.video_loader: self.video_loader.set_playing(False); self.video_loader.seek(0)
    def seek_frame(self, pos):
        if self.video_loader: self.video_loader.set_playing(False); self.video_loader.seek(pos)
    def reset_playback(self):
        if self.video_loader: self.video_loader.stop()
        self.current_frame, self.current_frame_idx, self.total_frames = None, 0, 0; self.frame_slider.setValue(0); self.frame_slider.setEnabled(False); self.frame_label.setText("Frame: 0/0"); self.progress_bar.setValue(0); self.video_label.clear(); self.behavior_colors.clear(); self.raw_detections.clear(); self.processed_detections.clear()
        self.update_legend_widget();
        if self.timeline_widget: self.timeline_widget.setData({}, {}, 0, 0)
        self._update_button_states()
    def load_video(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Video File", "", "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)");
        if file_path:
            self.reset_playback(); self.video_loader = VideoLoader(file_path)
            self.video_loader.video_loaded.connect(self.on_video_loaded); self.video_loader.frame_loaded.connect(self.on_frame_loaded); self.video_loader.error_occurred.connect(self.show_error); self.video_loader.finished.connect(self.video_loader.deleteLater)
            self.video_loader.start(); self.progress_bar.setRange(0, 0); self.video_label.setText("Loading video...")
    def on_video_loaded(self, width, height, fps):
        self.video_size = (width, height); self.total_frames = self.video_loader.total_frames; self.frame_slider.setRange(0, self.total_frames - 1); self.frame_slider.setEnabled(True)
        self.frame_label.setText(f"Frame: 0/{self.total_frames - 1}"); self.progress_bar.setRange(0, 100); self.grid_manager.set_video_size(width, height); self._update_button_states()
        self.video_loader.seek(0)
        if self.raw_detections: self.start_detection_processing()
    def on_frame_loaded(self, frame_idx, frame):
        self.current_frame_idx, self.current_frame = frame_idx, frame; self.update_display(); self.frame_slider.blockSignals(True); self.frame_slider.setValue(frame_idx); self.frame_slider.blockSignals(False)
        self.frame_label.setText(f"Frame: {frame_idx}/{self.total_frames - 1}")
        if self.total_frames > 0 and self.progress_bar.value() != int((frame_idx + 1) * 100 / self.total_frames): self.progress_bar.setValue(int((frame_idx + 1) * 100 / self.total_frames))
        if self.timeline_widget: self.timeline_widget.setCurrentFrame(frame_idx)
    def start_detection_processing(self):
        if not self.raw_detections or self.video_size[0] == 0: return
        if self.detection_processor and self.detection_processor.isRunning(): self.detection_processor.stop(); self.detection_processor.wait()
        self.status_label.setText("Processing detections...")
        self.detection_processor = DetectionProcessor(self.raw_detections, self.grid_manager.transform, self.grid_settings, self.video_size, self.max_animals_spinbox.value())
        self.detection_processor.processing_finished.connect(self.on_processing_complete); self.detection_processor.error_occurred.connect(self.on_processing_error); self.detection_processor.finished.connect(self.detection_processor.deleteLater); self.detection_processor.finished.connect(self.on_processor_thread_finished)
        self.detection_processor.start(); self._update_button_states()
    def on_processor_thread_finished(self):
        self.detection_processor = None; self._update_button_states()
    def on_processing_complete(self, processed_detections, timeline_segments):
        self.processed_detections = processed_detections
        if self.timeline_widget: self.timeline_widget.setData(timeline_segments, self.behavior_colors, self.total_frames, self.grid_settings['cols'] * self.grid_settings['rows'])
        self.status_label.setText(""); self._update_button_states(); self.update_display()
    def on_processing_error(self, message):
        self.status_label.setText(""); self.show_error(message); self._update_button_states()
    def on_video_export_finished(self):
        self.toggle_controls(True); self.progress_bar.setFormat(""); self.progress_bar.setTextVisible(False); QtWidgets.QMessageBox.information(self, "Success", "Video has been exported successfully."); self.progress_bar.setValue(0); self.video_saver.deleteLater(); self.video_saver = None
    def on_video_export_error(self, message):
        self.toggle_controls(True); self.progress_bar.setFormat(""); self.progress_bar.setTextVisible(False); self.progress_bar.setValue(0); self.show_error(f"Video export failed: {message}")
        if self.video_saver: self.video_saver.deleteLater(); self.video_saver = None
    def save_settings(self):
        # ### NEW: Check if video is loaded ###
        if self.video_size[0] == 0 or self.video_size[1] == 0:
            self.show_error("Please load a video before saving settings to store its dimensions.")
            return

        settings_data = {
            # ### NEW: Store video dimensions ###
            'video_dimensions': {
                'width': self.video_size[0],
                'height': self.video_size[1]
            },
            'grid_settings': self.grid_settings,
            'line_thickness': self.line_thickness,
            'grid_transform': {
                'center_x': self.grid_manager.center.x(),
                'center_y': self.grid_manager.center.y(),
                'angle': self.grid_manager.angle,
                'scale_x': self.grid_manager.scale_x,
                'scale_y': self.grid_manager.scale_y,
            }
        }
        
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Environment Settings", "settings.json", "JSON Files (*.json)")
        if not file_path: return
            
        try:
            with open(file_path, 'w') as f:
                json.dump(settings_data, f, indent=4)
            QtWidgets.QMessageBox.information(self, "Success", f"Settings saved to {file_path}")
        except Exception as e:
            self.show_error(f"Failed to save settings: {e}")
    def load_settings(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Environment Settings", "", "JSON Files (*.json)")
        if not file_path: return
        try:
            with open(file_path, 'r') as f: settings_data = json.load(f)
            self.grid_settings, self.line_thickness = settings_data['grid_settings'], settings_data['line_thickness']; transform_settings = settings_data['grid_transform']
            self.grid_manager.update_center(QPointF(transform_settings['center_x'], transform_settings['center_y'])); self.grid_manager.update_rotation(transform_settings['angle']); self.grid_manager.update_scale(transform_settings['scale_x'], transform_settings['scale_y'])
            self._block_signals_for_controls(True)
            self.grid_cols_spin.setValue(self.grid_settings['cols']); self.grid_rows_spin.setValue(self.grid_settings['rows']); self.line_thickness_spin.setValue(self.line_thickness)
            self.rotate_slider.setValue(int(self.grid_manager.angle)); self.scale_x_slider.setValue(int(self.grid_manager.scale_x * 100)); self.scale_y_slider.setValue(int(self.grid_manager.scale_y * 100))
            self.move_x_slider.setValue(int((self.grid_manager.center.x() - 0.5) * 200)); self.move_y_slider.setValue(int((self.grid_manager.center.y() - 0.5) * 200))
            self._block_signals_for_controls(False); self.start_detection_processing(); self.update_display()
            QtWidgets.QMessageBox.information(self, "Success", "Settings loaded successfully.")
        except Exception as e: self.show_error(f"Failed to load or apply settings: {e}")
    def update_grid_settings(self): self.grid_settings = {'cols': self.grid_cols_spin.value(), 'rows': self.grid_rows_spin.value()}; self.selected_cells.clear(); self.update_tank_selection_label(); self.start_detection_processing(); self.update_display()
    def update_line_thickness(self): self.line_thickness = self.line_thickness_spin.value(); self.update_display()
    def update_grid_rotation(self, angle): self.grid_manager.update_rotation(angle)
    def update_grid_scale(self): self.grid_manager.update_scale(self.scale_x_slider.value() / 100.0, self.scale_y_slider.value() / 100.0)
    def update_grid_position(self): self.grid_manager.update_center(QPointF(0.5 + self.move_x_slider.value() / 200.0, 0.5 + self.move_y_slider.value() / 200.0))
    def reset_grid_transform_and_ui(self): self._block_signals_for_controls(True); self.rotate_slider.setValue(0); self.scale_x_slider.setValue(100); self.scale_y_slider.setValue(100); self.move_x_slider.setValue(0); self.move_y_slider.setValue(0); self._block_signals_for_controls(False); self.grid_manager.reset(); self.start_detection_processing()
    def select_all_tanks(self): self.selected_cells = {str(i + 1) for i in range(self.grid_settings['rows'] * self.grid_settings['cols'])}; self.update_tank_selection_label(); self.update_display()
    def clear_tank_selection(self): self.selected_cells.clear(); self.update_tank_selection_label(); self.update_display()
    def update_tank_selection_label(self): self.tank_selection_label.setText("Selected Tanks: " + (', '.join(sorted(self.selected_cells, key=int)) if self.selected_cells else "None"))
    def handle_mouse_press(self, event):
        if self.current_frame is None or self.video_size[0] == 0: return
        pos, pixmap = event.pos(), self.video_label.pixmap();
        if not pixmap: return
        label_size, pixmap_size = self.video_label.size(), pixmap.size(); offset_x, offset_y = (label_size.width()-pixmap_size.width())//2, (label_size.height()-pixmap_size.height())//2
        if not (offset_x <= pos.x() < offset_x + pixmap_size.width() and offset_y <= pos.y() < offset_y + pixmap_size.height()): return
        x = (pos.x() - offset_x) / pixmap_size.width(); y = (pos.y() - offset_y) / pixmap_size.height()
        click_px_x = x * pixmap_size.width(); click_px_y = y * pixmap_size.height(); center_px_x = self.grid_manager.center.x() * pixmap_size.width(); center_px_y = self.grid_manager.center.y() * pixmap_size.height()
        if ((click_px_x - center_px_x)**2 + (click_px_y - center_px_y)**2)**0.5 < 15: self.dragging_mode = "center"
        else: self.dragging_mode = "rotate"
        self.last_mouse_pos = QPointF(x, y)
    def handle_mouse_move(self, event):
        if self.dragging_mode is None or self.last_mouse_pos is None or not self.video_label.pixmap(): return
        pos, pixmap = event.pos(), self.video_label.pixmap(); label_size, pixmap_size = self.video_label.size(), pixmap.size(); offset_x, offset_y = (label_size.width() - pixmap_size.width())//2, (label_size.height() - pixmap_size.height())//2
        if not (offset_x <= pos.x() < offset_x + pixmap_size.width() and offset_y <= pos.y() < offset_y + pixmap_size.height()): return
        x, y = (pos.x() - offset_x) / pixmap_size.width(), (pos.y() - offset_y) / pixmap_size.height()
        current_pos = QPointF(x, y)
        if self.dragging_mode == "center":
            self.grid_manager.update_center(current_pos); self.move_x_slider.blockSignals(True); self.move_y_slider.blockSignals(True)
            self.move_x_slider.setValue(int((current_pos.x() - 0.5) * 200)); self.move_y_slider.setValue(int((current_pos.y() - 0.5) * 200))
            self.move_x_slider.blockSignals(False); self.move_y_slider.blockSignals(False)
        else:
            self.grid_manager.handle_mouse_drag_rotate(self.last_mouse_pos, current_pos); self.rotate_slider.blockSignals(True); self.rotate_slider.setValue(int(self.grid_manager.angle)); self.rotate_slider.blockSignals(False)
        self.last_mouse_pos = current_pos
    def handle_mouse_release(self, event):
        if self.dragging_mode: self.start_detection_processing()
        self.dragging_mode = self.last_mouse_pos = None
    def _block_signals_for_controls(self, should_block):
        widgets = [self.grid_cols_spin, self.grid_rows_spin, self.line_thickness_spin, self.rotate_slider, self.scale_x_slider, self.scale_y_slider, self.move_x_slider, self.move_y_slider, self.reset_grid_btn]
        for widget in widgets: widget.blockSignals(should_block)
    def toggle_controls(self, enabled):
        final_state = enabled and not (self.detection_processor and self.detection_processor.isRunning())
        self.play_btn.setEnabled(final_state); self.pause_btn.setEnabled(final_state); self.stop_btn.setEnabled(final_state)
        self.frame_slider.setEnabled(final_state and self.total_frames > 0)
    def show_error(self, message):
        QtWidgets.QMessageBox.critical(self, "Error", message)
    def closeEvent(self, event):
        for worker in [self.video_loader, self.video_saver, self.detection_processor]:
            if worker: worker.stop(); worker.wait()
        event.accept()