# EthoGrid_App/widgets/analysis_dialog.py

import os
import csv
import json
from collections import defaultdict
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QThread, QPointF
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QTransform
import cv2
from workers.analysis_processor import AnalysisProcessor
from widgets.range_slider import RangeSlider
from widgets.base_dialog import BaseDialog 

class AnalysisDialog(BaseDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Interactive Endpoints Analysis"); self.setMinimumSize(1200, 800)
        self.csv_files, self.analysis_thread, self.analysis_worker = [], None, None
        self.grid_settings, self.grid_transform, self.video_size = {}, None, (0,0)
        self.geometric_centers, self.adjusted_centers, self.tank_corners = {}, {}, {}
        self.side_view_tank_configs = {}
        
        main_layout = QtWidgets.QVBoxLayout(self)
        top_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        
        left_pane_scroll_area = QtWidgets.QScrollArea(); left_pane_scroll_area.setWidgetResizable(True)
        left_pane_widget = QtWidgets.QWidget(); left_pane = QtWidgets.QVBoxLayout(left_pane_widget)
        left_pane_scroll_area.setWidget(left_pane_widget)
        
        right_pane_widget = QtWidgets.QWidget(); right_pane = QtWidgets.QVBoxLayout(right_pane_widget)
        
        file_group = QtWidgets.QGroupBox("Input Files"); file_layout = QtWidgets.QFormLayout(file_group)
        self.video_line_edit = QtWidgets.QLineEdit(); self.video_line_edit.setPlaceholderText("Load a sample video to visualize the grid")
        self.browse_video_btn = QtWidgets.QPushButton("Browse...")
        self.settings_line_edit = QtWidgets.QLineEdit(); self.settings_line_edit.setPlaceholderText("Load the settings.json file for this experiment")
        self.browse_settings_btn = QtWidgets.QPushButton("Browse...")
        self.csv_list_widget = QtWidgets.QListWidget(); self.csv_list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.add_csv_btn = QtWidgets.QPushButton("Add CSV(s)..."); self.add_directory_btn = QtWidgets.QPushButton("Add Directory...")
        self.remove_csv_btn = QtWidgets.QPushButton("Remove Selected"); self.clear_csv_btn = QtWidgets.QPushButton("Clear All")
        file_list_layout = QtWidgets.QHBoxLayout(); file_list_layout.addWidget(self.csv_list_widget)
        file_button_layout = QtWidgets.QVBoxLayout(); file_button_layout.addWidget(self.add_csv_btn); file_button_layout.addWidget(self.add_directory_btn); file_button_layout.addWidget(self.remove_csv_btn); file_button_layout.addWidget(self.clear_csv_btn); file_button_layout.addStretch()
        file_list_layout.addLayout(file_button_layout)
        file_layout.addRow("Sample Video:", self.create_hbox(self.video_line_edit, self.browse_video_btn))
        file_layout.addRow("Grid Settings:", self.create_hbox(self.settings_line_edit, self.browse_settings_btn))
        file_layout.addRow(QtWidgets.QLabel("Input CSV Files ('_with_tanks.csv'):")); file_layout.addRow(file_list_layout)
        left_pane.addWidget(file_group)

        mode_group = QtWidgets.QGroupBox("Analysis Mode"); mode_layout = QtWidgets.QFormLayout(mode_group)
        self.analysis_mode_combo = QtWidgets.QComboBox(); self.analysis_mode_combo.addItems(["Side View", "Top View"]); mode_layout.addRow("View Type:", self.analysis_mode_combo)
        left_pane.addWidget(mode_group)
        
        self.side_view_group = QtWidgets.QGroupBox("Side View Tank Settings"); side_view_main_layout = QtWidgets.QVBoxLayout(self.side_view_group)
        self.side_view_axis_combo = QtWidgets.QComboBox(); self.side_view_axis_combo.addItems(["Top-Bottom", "Left-Top to Right-Bottom", "Left-Bottom to Right-Top"])
        axis_layout = QtWidgets.QHBoxLayout(); axis_layout.addWidget(QtWidgets.QLabel("Global Division Axis:")); axis_layout.addWidget(self.side_view_axis_combo)
        side_view_main_layout.addLayout(axis_layout)
        self.side_view_params_scroll = QtWidgets.QScrollArea(); self.side_view_params_scroll.setWidgetResizable(True); self.side_view_params_scroll.setMinimumHeight(250)
        self.side_view_params_widget = QtWidgets.QWidget(); self.side_view_params_layout = QtWidgets.QVBoxLayout(self.side_view_params_widget)
        self.side_view_params_scroll.setWidget(self.side_view_params_widget)
        side_view_main_layout.addWidget(self.side_view_params_scroll)
        left_pane.addWidget(self.side_view_group)
        
        self.top_view_group = QtWidgets.QGroupBox("Top View Parameters");
        left_pane.addWidget(self.top_view_group)

        self.side_view_endpoints_group = QtWidgets.QGroupBox("Side View Endpoints"); side_endpoints_layout = QtWidgets.QFormLayout(self.side_view_endpoints_group)
        self.side_view_endpoints_checkboxes = {"Average Speed (cm/s)": QtWidgets.QCheckBox("Average Speed (cm/s)", checked=True), "Average Distance from Center (cm)": QtWidgets.QCheckBox("Average Distance from Center (cm)", checked=True), "Freezing Time (%)": QtWidgets.QCheckBox("Freezing Time (%)", checked=True), "Swimming Time (%)": QtWidgets.QCheckBox("Swimming Time (%)", checked=True), "Rapid Time (%)": QtWidgets.QCheckBox("Rapid Time (%)", checked=True), "Time in Top (%)": QtWidgets.QCheckBox("Time in Top (%)", checked=True), "Time in Middle (%)": QtWidgets.QCheckBox("Time in Middle (%)", checked=True), "Time in Bottom (%)": QtWidgets.QCheckBox("Time in Bottom (%)", checked=True), "Entries to Top": QtWidgets.QCheckBox("Entries to Top", checked=True), "Fractal Dimension": QtWidgets.QCheckBox("Fractal Dimension", checked=True), "Entropy": QtWidgets.QCheckBox("Entropy", checked=True)}
        self.rapid_thresh_spinbox = QtWidgets.QDoubleSpinBox(value=5.0, minimum=0, maximum=100, decimals=1, suffix=" cm/s")
        self.freezing_thresh_spinbox = QtWidgets.QDoubleSpinBox(value=0.5, minimum=0, maximum=100, decimals=1, suffix=" cm/s")
        for name, cb in self.side_view_endpoints_checkboxes.items(): side_endpoints_layout.addRow(cb)
        side_endpoints_layout.addRow("Rapid Threshold:", self.rapid_thresh_spinbox); side_endpoints_layout.addRow("Freezing Threshold:", self.freezing_thresh_spinbox)
        left_pane.addWidget(self.side_view_endpoints_group)

        self.top_view_endpoints_group = QtWidgets.QGroupBox("Top View Endpoints"); top_endpoints_layout = QtWidgets.QFormLayout(self.top_view_endpoints_group)
        self.top_view_endpoints_checkboxes = {"Average Speed (cm/s)": QtWidgets.QCheckBox("Average Speed (cm/s)", checked=True), "Average Distance from Center (cm)": QtWidgets.QCheckBox("Average Distance from Center (cm)", checked=True), "Average Angular Velocity (degree/s)": QtWidgets.QCheckBox("Average Angular Velocity (degree/s)", checked=True), "Meandering (degree/m)": QtWidgets.QCheckBox("Meandering (degree/m)", checked=True), "Fractal Dimension": QtWidgets.QCheckBox("Fractal Dimension", checked=True), "Entropy": QtWidgets.QCheckBox("Entropy", checked=True)}
        self.angular_thresh_spinbox = QtWidgets.QDoubleSpinBox(value=90, minimum=0, maximum=180, suffix=" deg/s")
        for name, cb in self.top_view_endpoints_checkboxes.items(): top_endpoints_layout.addRow(cb)
        top_endpoints_layout.addRow("Angular Vel. Threshold:", self.angular_thresh_spinbox)
        left_pane.addWidget(self.top_view_endpoints_group)
        
        universal_group = QtWidgets.QGroupBox("Universal Parameters"); universal_layout = QtWidgets.QFormLayout(universal_group)
        self.frame_rate_spinbox = QtWidgets.QDoubleSpinBox(value=30.0, decimals=1); self.conversion_rate_spinbox = QtWidgets.QDoubleSpinBox(value=100.0, decimals=2, toolTip="Pixels per cm")
        universal_layout.addRow("Frame Rate (FPS):", self.frame_rate_spinbox); universal_layout.addRow("Conversion Rate (px/cm):", self.conversion_rate_spinbox); left_pane.addWidget(universal_group)
        
        # ### THE FIX IS HERE ###
        self.centroid_sliders_group = QtWidgets.QGroupBox("Centroid Adjustment")
        centroid_main_layout = QtWidgets.QVBoxLayout(self.centroid_sliders_group)
        self.centroid_sliders_area = QtWidgets.QScrollArea(); self.centroid_sliders_area.setWidgetResizable(True); self.centroid_sliders_area.setMinimumHeight(250)
        self.centroid_sliders_widget = QtWidgets.QWidget(); self.centroid_sliders_layout = QtWidgets.QVBoxLayout(self.centroid_sliders_widget)
        self.centroid_sliders_area.setWidget(self.centroid_sliders_widget)
        centroid_main_layout.addWidget(self.centroid_sliders_area)
        left_pane.addWidget(self.centroid_sliders_group)
        left_pane.addStretch()
        
        self.save_analysis_settings_btn = QtWidgets.QPushButton("Save Analysis Settings"); self.load_analysis_settings_btn = QtWidgets.QPushButton("Load Analysis Settings")
        settings_button_layout = QtWidgets.QHBoxLayout(); settings_button_layout.addStretch(); settings_button_layout.addWidget(self.load_analysis_settings_btn); settings_button_layout.addWidget(self.save_analysis_settings_btn)
        left_pane.addLayout(settings_button_layout)
        
        self.video_display = QtWidgets.QLabel("Load a sample video and settings file to see the grid"); self.video_display.setAlignment(QtCore.Qt.AlignCenter); right_pane.addWidget(self.video_display)
        
        top_splitter.addWidget(left_pane_scroll_area); top_splitter.addWidget(right_pane_widget); top_splitter.setSizes([450, 750])
        main_layout.addWidget(top_splitter)
        
        bottom_tabs = QtWidgets.QTabWidget(); bottom_tabs.setMaximumHeight(150)
        progress_widget = QtWidgets.QWidget(); log_widget = QtWidgets.QWidget()
        progress_layout = QtWidgets.QHBoxLayout(progress_widget)
        self.progress_bar = QtWidgets.QProgressBar(); self.progress_label = QtWidgets.QLabel("Waiting to start...")
        self.output_dir_line_edit = QtWidgets.QLineEdit(); self.output_dir_line_edit.setPlaceholderText("Select output folder...")
        self.browse_output_btn = QtWidgets.QPushButton("Browse..."); self.start_btn = QtWidgets.QPushButton("Start Analysis")
        progress_layout.addWidget(self.progress_label); progress_layout.addWidget(self.progress_bar, stretch=1); progress_layout.addWidget(self.output_dir_line_edit); progress_layout.addWidget(self.browse_output_btn); progress_layout.addWidget(self.start_btn)
        
        log_layout = QtWidgets.QVBoxLayout(log_widget)
        self.log_text_edit = QtWidgets.QTextEdit(); self.log_text_edit.setReadOnly(True) # Assign to self
        log_layout.addWidget(self.log_text_edit)
        
        bottom_tabs.addTab(progress_widget, "Run Control & Log"); bottom_tabs.addTab(log_widget, "Detailed Log")
        main_layout.addWidget(bottom_tabs)

        self.browse_video_btn.clicked.connect(self.load_video); self.browse_settings_btn.clicked.connect(self.load_settings); self.add_csv_btn.clicked.connect(self.add_csv_files); self.add_directory_btn.clicked.connect(self.add_csv_directory); self.remove_csv_btn.clicked.connect(self.remove_selected_csvs); self.clear_csv_btn.clicked.connect(self.clear_all_csvs); self.browse_output_btn.clicked.connect(self.browse_output); self.analysis_mode_combo.currentTextChanged.connect(self.on_mode_change); self.start_btn.clicked.connect(self.start_analysis)
        self.save_analysis_settings_btn.clicked.connect(self.save_analysis_settings); self.load_analysis_settings_btn.clicked.connect(self.load_analysis_settings)
        self.on_mode_change("Side View")

    def create_hbox(self, w1, w2):
        hbox = QtWidgets.QHBoxLayout(); hbox.addWidget(w1); hbox.addWidget(w2); return hbox
    
    def on_mode_change(self, mode):
        is_side_view = (mode == "Side View")
        self.side_view_group.setVisible(is_side_view); self.side_view_endpoints_group.setVisible(is_side_view)
        self.top_view_group.setVisible(not is_side_view); self.top_view_endpoints_group.setVisible(not is_side_view)
        self.centroid_sliders_group.setVisible(True)

    def load_video(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Sample Video", "", "Video Files (*.mp4 *.avi *.mov *.mkv)");
        if path: self.video_line_edit.setText(path); self.update_visualization()

    def load_settings(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Settings File", "", "JSON Files (*.json)");
        if path:
            try:
                with open(path, 'r') as f: settings_data = json.load(f)
                self.grid_settings = settings_data['grid_settings']; self.video_size = (settings_data['video_dimensions']['width'], settings_data['video_dimensions']['height'])
                tf = settings_data['grid_transform']; w, h = self.video_size
                self.grid_transform = QTransform(); self.grid_transform.translate(w * tf['center_x'], h * tf['center_y']); self.grid_transform.rotate(tf['angle']); self.grid_transform.scale(tf['scale_x'], tf['scale_y']); self.grid_transform.translate(-w / 2, -h / 2)
                self.settings_line_edit.setText(path); self.calculate_geometric_centers(); self.setup_centroid_sliders(); self.setup_side_view_tank_widgets(); self.update_visualization()
            except Exception as e: QtWidgets.QMessageBox.critical(self, "Error", f"Failed to load settings file: {e}")

    def calculate_geometric_centers(self):
        if not self.grid_transform or self.video_size[0] == 0: return
        self.geometric_centers, self.adjusted_centers, self.tank_corners = {}, {}, {}
        w, h = self.video_size; rows, cols = self.grid_settings['rows'], self.grid_settings['cols']
        for r in range(rows):
            for c in range(cols):
                tank_num = r * cols + c + 1
                center_x_local, center_y_local = (c + 0.5) * w / cols, (r + 0.5) * h / rows
                p = self.grid_transform.map(QPointF(center_x_local, center_y_local))
                self.geometric_centers[tank_num] = (p.x(), p.y()); self.adjusted_centers[tank_num] = (p.x(), p.y())
                p1 = self.grid_transform.map(QPointF(c*w/cols, r*h/rows)); p2 = self.grid_transform.map(QPointF((c+1)*w/cols, r*h/rows)); p3 = self.grid_transform.map(QPointF((c+1)*w/cols, (r+1)*h/rows)); p4 = self.grid_transform.map(QPointF(c*w/cols, (r+1)*h/rows))
                self.tank_corners[tank_num] = [(p1.x(), p1.y()), (p2.x(), p2.y()), (p3.x(), p3.y()), (p4.x(), p4.y())]

    def setup_centroid_sliders(self):
        while self.centroid_sliders_layout.count():
            item = self.centroid_sliders_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        if not self.geometric_centers: return
        for tank_num in sorted(self.geometric_centers.keys()):
            group = QtWidgets.QGroupBox(f"Tank {tank_num} Center Offset")
            layout = QtWidgets.QFormLayout(group); x_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal, minimum=-100, maximum=100, value=0); y_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal, minimum=-100, maximum=100, value=0)
            x_slider.valueChanged.connect(lambda val, tn=tank_num: self.update_adjusted_center(tn, 'x', val)); y_slider.valueChanged.connect(lambda val, tn=tank_num: self.update_adjusted_center(tn, 'y', val))
            layout.addRow("X Offset:", x_slider); layout.addRow("Y Offset:", y_slider); self.centroid_sliders_layout.addWidget(group)

    def setup_side_view_tank_widgets(self):
        while self.side_view_params_layout.count():
            item = self.side_view_params_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        if not self.geometric_centers: return
        for tank_num in sorted(self.geometric_centers.keys()):
            self.side_view_tank_configs[tank_num] = {'zone1': 50, 'zone2': 50}
            group = QtWidgets.QGroupBox(f"Tank {tank_num} Zones"); layout = QtWidgets.QVBoxLayout(group)
            range_slider = RangeSlider()
            range_slider.setValues(50, 50) 
            range_slider.valuesChanged.connect(lambda low, high, tn=tank_num, s=range_slider: self.update_side_view_config(tn, 'zones', (low, high), s))
            layout.addWidget(range_slider)
            self.side_view_params_layout.addWidget(group)

    def update_adjusted_center(self, tank_num, axis, value):
        geom_x, geom_y = self.geometric_centers[tank_num]; current_adj_x, current_adj_y = self.adjusted_centers[tank_num]
        if axis == 'x': self.adjusted_centers[tank_num] = (geom_x + value, current_adj_y)
        else: self.adjusted_centers[tank_num] = (current_adj_x, geom_y + value)
        self.update_visualization()

    def update_side_view_config(self, tank_num, key, value, slider_instance):
        if key == 'zones':
            low, high = value
            if low + high > 100:
                last_config = self.side_view_tank_configs[tank_num]
                slider_instance.setValues(last_config['zone1'], last_config['zone2'])
                return
            self.side_view_tank_configs[tank_num]['zone1'], self.side_view_tank_configs[tank_num]['zone2'] = low, high

    def update_visualization(self):
        video_path = self.video_line_edit.text()
        if not video_path or not os.path.exists(video_path) or not self.grid_transform:
            self.video_display.setText("Load a sample video and settings file to see the grid"); return
        cap = cv2.VideoCapture(video_path); ret, frame = cap.read(); cap.release()
        if not ret: return
        pixmap = QPixmap.fromImage(QImage(frame.data, frame.shape[1], frame.shape[0], QImage.Format_BGR888)); painter = QPainter(pixmap)
        rows, cols = self.grid_settings['rows'], self.grid_settings['cols']; w, h = self.video_size
        painter.setPen(QPen(QColor(0, 255, 0, 150), 2))
        for r in range(rows + 1): p1 = self.grid_transform.map(QPointF(0, r * h / rows)); p2 = self.grid_transform.map(QPointF(w, r * h / rows)); painter.drawLine(p1, p2)
        for c in range(cols + 1): p1 = self.grid_transform.map(QPointF(c * w / cols, 0)); p2 = self.grid_transform.map(QPointF(c * w / cols, h)); painter.drawLine(p1, p2)
        for tank_num in sorted(self.geometric_centers.keys()):
            corners = self.tank_corners[tank_num]; p1, p2, p3, p4 = QPointF(corners[0][0], corners[0][1]), QPointF(corners[1][0], corners[1][1]), QPointF(corners[2][0], corners[2][1]), QPointF(corners[3][0], corners[3][1])
            painter.setPen(QPen(QColor(255, 255, 0, 100), 1, QtCore.Qt.DotLine)); painter.drawLine(p1, p3); painter.drawLine(p2, p4)
            adj_x, adj_y = self.adjusted_centers[tank_num]; painter.setPen(QPen(QColor(255, 0, 0), 2)); painter.setBrush(QColor(255, 0, 0)); painter.drawEllipse(QtCore.QPoint(int(adj_x), int(adj_y)), 5, 5)
        painter.end()
        self.video_display.setPixmap(pixmap.scaled(self.video_display.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))

    def add_csv_files(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Select Enriched CSV Files", "", "CSV Files (*_with_tanks.csv)");
        if files:
            newly_added = []
            for f in files:
                if f not in self.csv_files: self.csv_files.append(f); newly_added.append(os.path.basename(f))
            if newly_added: self.csv_list_widget.addItems(newly_added)

    def add_csv_directory(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory Containing CSV Files")
        if directory:
            csv_extension = '_with_tanks.csv'; newly_found = []
            for root, _, files in os.walk(directory):
                for file in files:
                    if file.lower().endswith(csv_extension):
                        full_path = os.path.join(root, file)
                        if full_path not in self.csv_files: self.csv_files.append(full_path); newly_found.append(os.path.basename(full_path))
            if newly_found: self.csv_list_widget.addItems(newly_found)
            else: QtWidgets.QMessageBox.information(self, "No Files Found", f"No '{csv_extension}' files were found in:\n{directory}")

    def remove_selected_csvs(self):
        selected_items = self.csv_list_widget.selectedItems()
        if not selected_items: return
        for item in selected_items:
            row = self.csv_list_widget.row(item); self.csv_list_widget.takeItem(row)
            base_name = item.text(); self.csv_files = [f for f in self.csv_files if os.path.basename(f) != base_name]

    def clear_all_csvs(self):
        self.csv_list_widget.clear(); self.csv_files.clear()

    def browse_output(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory");
        if directory: self.output_dir_line_edit.setText(directory)

    def save_analysis_settings(self):
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Analysis Settings", "analysis_settings.json", "JSON Files (*.json)")
        if not file_path: return
        settings = {'analysis_mode': self.analysis_mode_combo.currentText(), 'side_view_axis': self.side_view_axis_combo.currentText(), 'side_view_configs': self.side_view_tank_configs, 'rapid_threshold': self.rapid_thresh_spinbox.value(), 'freezing_threshold': self.freezing_thresh_spinbox.value(), 'angular_threshold': self.angular_thresh_spinbox.value(), 'frame_rate': self.frame_rate_spinbox.value(), 'conversion_rate': self.conversion_rate_spinbox.value(), 'adjusted_centers': {str(k): v for k,v in self.adjusted_centers.items()}, 'side_view_endpoints': [name for name, cb in self.side_view_endpoints_checkboxes.items() if cb.isChecked()], 'top_view_endpoints': [name for name, cb in self.top_view_endpoints_checkboxes.items() if cb.isChecked()]}
        try:
            with open(file_path, 'w') as f: json.dump(settings, f, indent=4)
            QtWidgets.QMessageBox.information(self, "Success", "Analysis settings saved.")
        except Exception as e: self.show_error(f"Failed to save settings: {e}")

    def load_analysis_settings(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Analysis Settings", "", "JSON Files (*.json)")
        if not file_path: return
        try:
            with open(file_path, 'r') as f: settings = json.load(f)
            self.analysis_mode_combo.setCurrentText(settings.get('analysis_mode', 'Side View'))
            self.side_view_axis_combo.setCurrentText(settings.get('side_view_axis', 'Top-Bottom'))
            self.rapid_thresh_spinbox.setValue(settings.get('rapid_threshold', 5.0)); self.freezing_thresh_spinbox.setValue(settings.get('freezing_threshold', 0.5)); self.angular_thresh_spinbox.setValue(settings.get('angular_threshold', 90.0)); self.frame_rate_spinbox.setValue(settings.get('frame_rate', 30.0)); self.conversion_rate_spinbox.setValue(settings.get('conversion_rate', 100.0))
            if 'adjusted_centers' in settings and settings['adjusted_centers']: self.adjusted_centers = {int(k): tuple(v) for k, v in settings['adjusted_centers'].items()}
            else: self.adjusted_centers = self.geometric_centers.copy()
            self.setup_centroid_sliders(); self.update_visualization()
            if 'side_view_configs' in settings: self.side_view_tank_configs = {int(k): v for k,v in settings['side_view_configs'].items()}
            self.setup_side_view_tank_widgets()
            for i in range(self.side_view_params_layout.count()):
                group = self.side_view_params_layout.itemAt(i).widget(); tank_num = int(group.title().split(" ")[1])
                if tank_num in self.side_view_tank_configs:
                    config = self.side_view_tank_configs[tank_num]
                    group.findChild(RangeSlider).setValues(config['zone1'], config['zone2'])
            side_endpoints = settings.get('side_view_endpoints', []); top_endpoints = settings.get('top_view_endpoints', [])
            for name, cb in self.side_view_endpoints_checkboxes.items(): cb.setChecked(name in side_endpoints)
            for name, cb in self.top_view_endpoints_checkboxes.items(): cb.setChecked(name in top_endpoints)
            QtWidgets.QMessageBox.information(self, "Success", "Analysis settings loaded.")
        except Exception as e: self.show_error(f"Failed to load settings: {e}")

    def start_analysis(self):
        if not self.csv_files: QtWidgets.QMessageBox.warning(self, "Input Error", "Please add at least one CSV file."); return
        if not self.output_dir_line_edit.text() or not os.path.isdir(self.output_dir_line_edit.text()): QtWidgets.QMessageBox.warning(self, "Input Error", "Please select a valid output directory."); return
        if not self.settings_line_edit.text() or not os.path.exists(self.settings_line_edit.text()): QtWidgets.QMessageBox.warning(self, "Input Error", "Please select a valid grid settings.json file."); return
        if self.analysis_mode_combo.currentText() == "Side View": selected_endpoints = [name for name, cb in self.side_view_endpoints_checkboxes.items() if cb.isChecked()]
        else: selected_endpoints = [name for name, cb in self.top_view_endpoints_checkboxes.items() if cb.isChecked()]
        if not selected_endpoints: QtWidgets.QMessageBox.warning(self, "Input Error", "Please select at least one endpoint to calculate."); return
        params = {'analysis_mode': self.analysis_mode_combo.currentText(), 'side_view_axis': self.side_view_axis_combo.currentText(), 'rapid_threshold': self.rapid_thresh_spinbox.value(), 'freezing_threshold': self.freezing_thresh_spinbox.value(), 'slow_angular_velocity_threshold': self.angular_thresh_spinbox.value(), 'frame_rate': self.frame_rate_spinbox.value(), 'conversion_rate': self.conversion_rate_spinbox.value(), 'adjusted_tank_centers': self.adjusted_centers, 'tank_corners': self.tank_corners, 'selected_endpoints': selected_endpoints, 'side_view_configs': self.side_view_tank_configs}
        self.start_btn.setEnabled(False)
        self.analysis_worker = AnalysisProcessor(self.csv_files, params, self.output_dir_line_edit.text())
        self.analysis_thread = QThread(); self.analysis_worker.moveToThread(self.analysis_thread)
        self.analysis_worker.progress.connect(self.update_progress); self.analysis_worker.log.connect(self.log_text_edit.append); self.analysis_worker.finished.connect(self.on_analysis_finished); self.analysis_thread.started.connect(self.analysis_worker.run)
        self.analysis_thread.start()
    
    def on_analysis_finished(self):
        self.start_btn.setEnabled(True)
        if self.analysis_thread: self.analysis_thread.quit(); self.analysis_thread.wait(); self.analysis_thread = None
        self.progress_label.setText("Analysis Finished.")
        QtWidgets.QMessageBox.information(self, "Finished", f"Analysis complete. Results saved to:\n{self.output_dir_line_edit.text()}")
    
    def update_progress(self, current, total, filename):
        self.progress_bar.setValue(int((current + 1) * 100 / total)); self.progress_label.setText(f"Processing {current+1}/{total}: {filename}...")
        
    def show_error(self, message): QtWidgets.QMessageBox.critical(self, "Error", message)