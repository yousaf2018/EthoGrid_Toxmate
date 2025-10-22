# EthoGrid_App/widgets/batch_dialog.py

import os
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QThread
from workers.batch_processor import BatchProcessor
from widgets.base_dialog import BaseDialog 

class BatchProcessDialog(BaseDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Processing (Grid Annotation)")
        self.setMinimumSize(700, 650)
        self.video_files, self.batch_thread, self.batch_worker = [], None, None
        self.setStyleSheet(""" QDoubleSpinBox { padding: 4px; min-height: 20px; } QSpinBox { padding: 4px; min-height: 20px; } """)
        
        main_options_widget = QtWidgets.QWidget()
        form_layout = QtWidgets.QGridLayout(main_options_widget)
        
        self.video_list_widget = QtWidgets.QListWidget(); self.video_list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.add_videos_btn = QtWidgets.QPushButton("Add Video(s)..."); self.add_directory_btn = QtWidgets.QPushButton("Add Directory..."); self.remove_video_btn = QtWidgets.QPushButton("Remove Selected"); self.clear_videos_btn = QtWidgets.QPushButton("Clear All")
        self.settings_line_edit = QtWidgets.QLineEdit(); self.settings_line_edit.setPlaceholderText("Click 'Browse' to select a settings.json file")
        self.csv_dir_line_edit = QtWidgets.QLineEdit(); self.csv_dir_line_edit.setPlaceholderText("(Optional) Select a folder containing all your CSV files")
        self.output_dir_line_edit = QtWidgets.QLineEdit(); self.output_dir_line_edit.setPlaceholderText("Click 'Browse' to select an output folder")
        self.browse_settings_btn = QtWidgets.QPushButton("Browse..."); self.browse_output_btn = QtWidgets.QPushButton("Browse..."); self.browse_csv_dir_btn = QtWidgets.QPushButton("Browse...")
        
        self.max_animals_spinbox = QtWidgets.QSpinBox(); self.max_animals_spinbox.setToolTip("Enforce a maximum number of animals per tank."); self.max_animals_spinbox.setRange(1, 10); self.max_animals_spinbox.setValue(1)
        self.frame_sample_rate_spinbox = QtWidgets.QSpinBox(); self.frame_sample_rate_spinbox.setToolTip("Use data from every Nth frame for trajectories and heatmaps (e.g., 30 = 1 point per second for a 30 FPS video)."); self.frame_sample_rate_spinbox.setRange(1, 10000); self.frame_sample_rate_spinbox.setValue(30)
        self.time_gap_spinbox = QtWidgets.QDoubleSpinBox(); self.time_gap_spinbox.setToolTip("Max time gap in seconds for trajectories."); self.time_gap_spinbox.setRange(0.1, 99999.0); self.time_gap_spinbox.setValue(1.0); self.time_gap_spinbox.setSingleStep(0.1)
        
        self.save_video_checkbox = QtWidgets.QCheckBox("Save Annotated Video"); self.save_video_checkbox.setChecked(True)
        self.show_overlays_checkbox = QtWidgets.QCheckBox("Show Overlays (Legend/Timeline)"); self.show_overlays_checkbox.setChecked(True)
        self.save_csv_checkbox = QtWidgets.QCheckBox("Save Enriched CSV (Long Format)"); self.save_csv_checkbox.setChecked(True)
        self.save_centroid_csv_checkbox = QtWidgets.QCheckBox("Save Centroid CSV (Wide Format)"); self.save_centroid_csv_checkbox.setChecked(True)
        self.save_excel_checkbox = QtWidgets.QCheckBox("Save to Excel (by Tank)"); self.save_excel_checkbox.setChecked(True)
        self.save_trajectory_img_checkbox = QtWidgets.QCheckBox("Save Trajectory Image"); self.save_trajectory_img_checkbox.setChecked(True)
        self.save_heatmap_img_checkbox = QtWidgets.QCheckBox("Save Heatmap Image"); self.save_heatmap_img_checkbox.setChecked(True)

        self.start_btn = QtWidgets.QPushButton("Start Processing"); self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.overall_progress_bar = QtWidgets.QProgressBar(); self.overall_progress_label = QtWidgets.QLabel("Waiting to start...")
        self.file_progress_bar = QtWidgets.QProgressBar(); self.file_progress_label = QtWidgets.QLabel("Frame: 0 / 0")
        self.elapsed_time_label = QtWidgets.QLabel("Elapsed: 00:00:00"); self.etr_label = QtWidgets.QLabel("ETR: --:--:--"); self.speed_label = QtWidgets.QLabel("Speed: 0.00 FPS")
        self.log_text_edit = QtWidgets.QTextEdit(); self.log_text_edit.setReadOnly(True)

        main_dialog_layout = QtWidgets.QVBoxLayout(self)
        file_buttons_layout = QtWidgets.QVBoxLayout(); file_buttons_layout.addWidget(self.add_videos_btn); file_buttons_layout.addWidget(self.add_directory_btn); file_buttons_layout.addWidget(self.remove_video_btn); file_buttons_layout.addWidget(self.clear_videos_btn); file_buttons_layout.addStretch()
        form_layout.addWidget(QtWidgets.QLabel("Video Files (must have matching .csv):"), 0, 0); form_layout.addWidget(self.video_list_widget, 1, 0, 1, 2); form_layout.addLayout(file_buttons_layout, 1, 2)
        form_layout.addWidget(QtWidgets.QLabel("Grid Settings File (.json):"), 2, 0); form_layout.addWidget(self.settings_line_edit, 3, 0); form_layout.addWidget(self.browse_settings_btn, 3, 1)
        form_layout.addWidget(QtWidgets.QLabel("CSV Detections Folder (Optional):"), 4, 0); form_layout.addWidget(self.csv_dir_line_edit, 5, 0); form_layout.addWidget(self.browse_csv_dir_btn, 5, 1)
        form_layout.addWidget(QtWidgets.QLabel("Output Directory:"), 6, 0); form_layout.addWidget(self.output_dir_line_edit, 7, 0); form_layout.addWidget(self.browse_output_btn, 7, 1)
        
        processing_options_group = QtWidgets.QGroupBox("Processing Options"); processing_layout = QtWidgets.QFormLayout(processing_options_group)
        processing_layout.addRow("Max Animals per Tank:", self.max_animals_spinbox)
        processing_layout.addRow("Image Sample Rate (every Nth frame):", self.frame_sample_rate_spinbox)
        form_layout.addWidget(processing_options_group, 8, 0, 1, 3)

        output_options_group = QtWidgets.QGroupBox("Output Options"); output_options_layout = QtWidgets.QVBoxLayout(output_options_group)
        output_options_layout.addWidget(self.save_video_checkbox); output_options_layout.addWidget(self.show_overlays_checkbox)
        output_options_layout.addWidget(self.save_csv_checkbox); output_options_layout.addWidget(self.save_centroid_csv_checkbox)
        output_options_layout.addWidget(self.save_excel_checkbox); output_options_layout.addWidget(self.save_heatmap_img_checkbox)
        traj_layout = QtWidgets.QHBoxLayout(); traj_layout.addWidget(self.save_trajectory_img_checkbox); traj_layout.addStretch(); traj_layout.addWidget(QtWidgets.QLabel("Max Time Gap (s):")); traj_layout.addWidget(self.time_gap_spinbox)
        output_options_layout.addLayout(traj_layout); form_layout.addWidget(output_options_group, 9, 0, 1, 3);
        
        scroll_area = QtWidgets.QScrollArea(); scroll_area.setWidgetResizable(True); scroll_area.setWidget(main_options_widget)
        main_dialog_layout.addWidget(scroll_area)
        
        progress_group = QtWidgets.QGroupBox("Progress"); progress_layout = QtWidgets.QVBoxLayout(progress_group)
        progress_layout.addWidget(self.overall_progress_label); progress_layout.addWidget(self.overall_progress_bar)
        file_progress_layout = QtWidgets.QHBoxLayout(); file_progress_layout.addWidget(QtWidgets.QLabel("Current File Progress:")); file_progress_layout.addWidget(self.file_progress_label); file_progress_layout.addStretch(); file_progress_layout.addWidget(self.speed_label); file_progress_layout.addWidget(self.elapsed_time_label); file_progress_layout.addWidget(self.etr_label)
        progress_layout.addLayout(file_progress_layout); progress_layout.addWidget(self.file_progress_bar); main_dialog_layout.addWidget(progress_group)
        log_group = QtWidgets.QGroupBox("Log"); log_layout = QtWidgets.QVBoxLayout(log_group); log_layout.addWidget(self.log_text_edit)
        main_dialog_layout.addWidget(log_group)
        button_layout = QtWidgets.QHBoxLayout(); button_layout.addStretch(); button_layout.addWidget(self.cancel_btn); button_layout.addWidget(self.start_btn)
        main_dialog_layout.addLayout(button_layout)
        
        self.add_videos_btn.clicked.connect(self.add_videos); self.add_directory_btn.clicked.connect(self.add_directory); self.remove_video_btn.clicked.connect(self.remove_selected); self.clear_videos_btn.clicked.connect(self.clear_all); self.browse_settings_btn.clicked.connect(self.browse_settings); self.browse_csv_dir_btn.clicked.connect(self.browse_csv_dir); self.browse_output_btn.clicked.connect(self.browse_output)
        self.start_btn.clicked.connect(self.start_processing); self.cancel_btn.clicked.connect(self.cancel_processing)
        self.cancel_btn.setEnabled(False); self.save_video_checkbox.stateChanged.connect(self.on_save_video_changed); self.save_trajectory_img_checkbox.stateChanged.connect(self.on_save_trajectory_changed)
        self.on_save_video_changed(); self.on_save_trajectory_changed()

    def on_save_video_changed(self):
        is_checked = self.save_video_checkbox.isChecked(); self.show_overlays_checkbox.setEnabled(is_checked)
        if not is_checked: self.show_overlays_checkbox.setChecked(False)
    def on_save_trajectory_changed(self):
        self.time_gap_spinbox.setEnabled(self.save_trajectory_img_checkbox.isChecked())
    def add_videos(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Select Video Files", "", "Video Files (*.mp4 *.avi *.mov *.mkv)");
        if files:
            newly_added = []
            for f in files:
                if f not in self.video_files: self.video_files.append(f); newly_added.append(os.path.basename(f))
            if newly_added: self.video_list_widget.addItems(newly_added)
    def add_directory(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory Containing Videos")
        if directory:
            video_extensions = ('.mp4', '.avi', '.mov', '.mkv'); newly_found = []
            for root, _, files in os.walk(directory):
                for file in files:
                    if file.lower().endswith(video_extensions):
                        full_path = os.path.join(root, file)
                        if full_path not in self.video_files: self.video_files.append(full_path); newly_found.append(os.path.basename(full_path))
            if newly_found: self.video_list_widget.addItems(newly_found)
            else: QtWidgets.QMessageBox.information(self, "No New Videos Found", f"No new video files were found in:\n{directory}")
    def remove_selected(self):
        selected_items = self.video_list_widget.selectedItems()
        if not selected_items: return
        for item in selected_items:
            row = self.video_list_widget.row(item); self.video_list_widget.takeItem(row)
            base_name = item.text(); self.video_files = [f for f in self.video_files if os.path.basename(f) != base_name]
    def clear_all(self):
        self.video_list_widget.clear(); self.video_files.clear()
    def browse_settings(self):
        file, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Settings File", "", "JSON Files (*.json)");
        if file: self.settings_line_edit.setText(file)
    def browse_csv_dir(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Folder Containing CSV Files");
        if directory: self.csv_dir_line_edit.setText(directory)
    def browse_output(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory");
        if directory: self.output_dir_line_edit.setText(directory)
    def start_processing(self):
        if not self.video_files: QtWidgets.QMessageBox.warning(self, "Input Error", "Please add at least one video file."); return
        if not self.settings_line_edit.text() or not os.path.exists(self.settings_line_edit.text()): QtWidgets.QMessageBox.warning(self, "Input Error", "Please select a valid settings.json file."); return
        if not self.output_dir_line_edit.text() or not os.path.isdir(self.output_dir_line_edit.text()): QtWidgets.QMessageBox.warning(self, "Input Error", "Please select a valid output directory."); return
        if not any([self.save_video_checkbox.isChecked(), self.save_csv_checkbox.isChecked(), self.save_centroid_csv_checkbox.isChecked(), self.save_excel_checkbox.isChecked(), self.save_trajectory_img_checkbox.isChecked(), self.save_heatmap_img_checkbox.isChecked()]):
            QtWidgets.QMessageBox.warning(self, "Input Error", "Please select at least one output option."); return
        self.toggle_controls(False); self.log_text_edit.clear()
        self.batch_worker = BatchProcessor(
            self.video_files, self.settings_line_edit.text(), self.output_dir_line_edit.text(),
            csv_dir=self.csv_dir_line_edit.text(),
            max_animals_per_tank=self.max_animals_spinbox.value(),
            frame_sample_rate=self.frame_sample_rate_spinbox.value(),
            save_video=self.save_video_checkbox.isChecked(),
            save_csv=self.save_csv_checkbox.isChecked(),
            save_centroid_csv=self.save_centroid_csv_checkbox.isChecked(),
            save_excel=self.save_excel_checkbox.isChecked(),
            save_trajectory_img=self.save_trajectory_img_checkbox.isChecked(),
            save_heatmap_img=self.save_heatmap_img_checkbox.isChecked(),
            time_gap_seconds=self.time_gap_spinbox.value(),
            draw_overlays=self.show_overlays_checkbox.isChecked()
        )
        self.batch_thread = QThread(); self.batch_worker.moveToThread(self.batch_thread)
        self.batch_worker.overall_progress.connect(self.update_overall_progress); self.batch_worker.file_progress.connect(self.update_file_progress); self.batch_worker.log_message.connect(self.log_text_edit.append); self.batch_worker.finished.connect(self.on_processing_finished); self.batch_worker.time_updated.connect(self.update_time_labels); self.batch_worker.speed_updated.connect(self.update_speed_label); self.batch_thread.started.connect(self.batch_worker.run)
        self.batch_thread.start()
    def cancel_processing(self):
        if self.batch_worker: self.batch_worker.stop(); self.cancel_btn.setEnabled(False)
    def on_processing_finished(self):
        if self.batch_thread: self.batch_thread.quit(); self.batch_thread.wait()
        self.toggle_controls(True)
        if self.batch_worker and self.batch_worker.is_running: QtWidgets.QMessageBox.information(self, "Finished", "Batch processing has completed.")
    def update_overall_progress(self, current_num, total, filename):
        self.overall_progress_bar.setValue(int(current_num * 100 / total)); self.overall_progress_label.setText(f"Processing file {current_num} of {total}: {filename}")
        self.file_progress_bar.setValue(0); self.file_progress_label.setText("Frame: 0 / 0"); self.elapsed_time_label.setText("Elapsed: 00:00:00"); self.etr_label.setText("ETR: --:--:--"); self.speed_label.setText("Speed: 0.00 FPS")
    def update_file_progress(self, percentage, current_frame, total_frames):
        self.file_progress_bar.setValue(percentage); self.file_progress_label.setText(f"Frame: {current_frame} / {total_frames}")
    def update_time_labels(self, elapsed, etr):
        self.elapsed_time_label.setText(f"Elapsed: {elapsed}"); self.etr_label.setText(f"ETR: {etr}")
    def update_speed_label(self, fps):
        self.speed_label.setText(f"Speed: {fps:.2f} FPS")
    def toggle_controls(self, enabled):
        self.start_btn.setEnabled(enabled); self.add_videos_btn.setEnabled(enabled); self.browse_settings_btn.setEnabled(enabled); self.browse_output_btn.setEnabled(enabled); self.browse_csv_dir_btn.setEnabled(enabled); self.add_directory_btn.setEnabled(enabled); self.remove_video_btn.setEnabled(enabled); self.clear_videos_btn.setEnabled(enabled)
        self.cancel_btn.setEnabled(not enabled)
    def closeEvent(self, event):
        if self.batch_thread and self.batch_thread.isRunning():
            self.cancel_processing(); self.batch_thread.quit(); self.batch_thread.wait()
        event.accept()