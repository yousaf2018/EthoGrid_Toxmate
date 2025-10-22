# EthoGrid_App/widgets/yolo_inference_dialog.py

import os
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QThread
from workers.yolo_processor import YoloProcessor
from widgets.base_dialog import BaseDialog 

class YoloInferenceDialog(BaseDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("YOLO Detection")
        self.setMinimumSize(700, 600)
        self.video_files, self.yolo_thread, self.yolo_worker = [], None, None
        
        main_widget = QtWidgets.QWidget()
        form_layout = QtWidgets.QGridLayout(main_widget)
        
        self.video_list_widget = QtWidgets.QListWidget()
        self.video_list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        
        self.add_videos_btn = QtWidgets.QPushButton("Add Video(s)...")
        self.add_directory_btn = QtWidgets.QPushButton("Add Directory...")
        self.remove_video_btn = QtWidgets.QPushButton("Remove Selected")
        self.clear_videos_btn = QtWidgets.QPushButton("Clear All")

        self.model_line_edit = QtWidgets.QLineEdit(); self.model_line_edit.setPlaceholderText("Click 'Browse' to select a YOLO model file (.pt)")
        self.output_dir_line_edit = QtWidgets.QLineEdit(); self.output_dir_line_edit.setPlaceholderText("Click 'Browse' to select an output folder")
        self.browse_model_btn = QtWidgets.QPushButton("Browse..."); self.browse_output_btn = QtWidgets.QPushButton("Browse...")
        self.confidence_spinbox = QtWidgets.QDoubleSpinBox(); self.confidence_spinbox.setRange(0.0, 1.0); self.confidence_spinbox.setSingleStep(0.05); self.confidence_spinbox.setValue(0.4)
        self.save_video_checkbox = QtWidgets.QCheckBox("Save Annotated Video"); self.save_video_checkbox.setChecked(True)
        self.save_csv_checkbox = QtWidgets.QCheckBox("Save Detections CSV"); self.save_csv_checkbox.setChecked(True)
        self.start_btn = QtWidgets.QPushButton("Start Inference"); self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.overall_progress_bar = QtWidgets.QProgressBar(); self.overall_progress_label = QtWidgets.QLabel("Waiting to start...")
        self.file_progress_bar = QtWidgets.QProgressBar(); self.file_progress_label = QtWidgets.QLabel("Frame: 0 / 0")
        self.elapsed_time_label = QtWidgets.QLabel("Elapsed: 00:00:00"); self.etr_label = QtWidgets.QLabel("ETR: --:--:--")
        self.speed_label = QtWidgets.QLabel("Speed: 0.00 FPS")
        self.log_text_edit = QtWidgets.QTextEdit(); self.log_text_edit.setReadOnly(True)

        file_buttons_layout = QtWidgets.QVBoxLayout()
        file_buttons_layout.addWidget(self.add_videos_btn); file_buttons_layout.addWidget(self.add_directory_btn); file_buttons_layout.addWidget(self.remove_video_btn); file_buttons_layout.addWidget(self.clear_videos_btn); file_buttons_layout.addStretch()
        form_layout.addWidget(QtWidgets.QLabel("Video Files:"), 0, 0); form_layout.addWidget(self.video_list_widget, 1, 0, 1, 2); form_layout.addLayout(file_buttons_layout, 1, 2)
        form_layout.addWidget(QtWidgets.QLabel("YOLO Model File (.pt):"), 2, 0); form_layout.addWidget(self.model_line_edit, 3, 0); form_layout.addWidget(self.browse_model_btn, 3, 1)
        form_layout.addWidget(QtWidgets.QLabel("Output Directory:"), 4, 0); form_layout.addWidget(self.output_dir_line_edit, 5, 0); form_layout.addWidget(self.browse_output_btn, 5, 1)
        form_layout.addWidget(QtWidgets.QLabel("Confidence Threshold:"), 6, 0); form_layout.addWidget(self.confidence_spinbox, 6, 1)
        output_options_group = QtWidgets.QGroupBox("Output Options"); output_options_layout = QtWidgets.QHBoxLayout(output_options_group)
        output_options_layout.addWidget(self.save_video_checkbox); output_options_layout.addWidget(self.save_csv_checkbox); output_options_layout.addStretch()
        form_layout.addWidget(output_options_group, 7, 0, 1, 3)
        
        scroll_area = QtWidgets.QScrollArea(); scroll_area.setWidgetResizable(True); scroll_area.setWidget(main_widget)
        main_dialog_layout = QtWidgets.QVBoxLayout(self); main_dialog_layout.addWidget(scroll_area)
        
        progress_group = QtWidgets.QGroupBox("Progress"); progress_layout = QtWidgets.QVBoxLayout(progress_group)
        progress_layout.addWidget(self.overall_progress_label); progress_layout.addWidget(self.overall_progress_bar)
        file_progress_layout = QtWidgets.QHBoxLayout(); file_progress_layout.addWidget(QtWidgets.QLabel("Current Video Progress:")); file_progress_layout.addWidget(self.file_progress_label); file_progress_layout.addStretch(); file_progress_layout.addWidget(self.speed_label); file_progress_layout.addWidget(self.elapsed_time_label); file_progress_layout.addWidget(self.etr_label)
        progress_layout.addLayout(file_progress_layout); progress_layout.addWidget(self.file_progress_bar)
        main_dialog_layout.addWidget(progress_group)
        log_group = QtWidgets.QGroupBox("Log"); log_layout = QtWidgets.QVBoxLayout(log_group); log_layout.addWidget(self.log_text_edit)
        main_dialog_layout.addWidget(log_group)
        button_layout = QtWidgets.QHBoxLayout(); button_layout.addStretch(); button_layout.addWidget(self.cancel_btn); button_layout.addWidget(self.start_btn)
        main_dialog_layout.addLayout(button_layout)

        self.add_videos_btn.clicked.connect(self.add_videos); self.add_directory_btn.clicked.connect(self.add_directory); self.remove_video_btn.clicked.connect(self.remove_selected); self.clear_videos_btn.clicked.connect(self.clear_all)
        self.browse_model_btn.clicked.connect(self.browse_model); self.browse_output_btn.clicked.connect(self.browse_output)
        self.start_btn.clicked.connect(self.start_processing); self.cancel_btn.clicked.connect(self.cancel_processing)
        self.cancel_btn.setEnabled(False)

    def add_videos(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Select Video Files", "", "Video Files (*.mp4 *.avi *.mov *.mkv)")
        if files:
            newly_added = []
            for f in files:
                if f not in self.video_files:
                    self.video_files.append(f)
                    newly_added.append(os.path.basename(f))
            if newly_added: self.video_list_widget.addItems(newly_added)

    def add_directory(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory Containing Videos")
        if directory:
            video_extensions = ('.mp4', '.avi', '.mov', '.mkv')
            newly_found = []
            for root, _, files in os.walk(directory):
                for file in files:
                    if file.lower().endswith(video_extensions):
                        full_path = os.path.join(root, file)
                        if full_path not in self.video_files:
                            self.video_files.append(full_path)
                            newly_found.append(os.path.basename(full_path))
            if newly_found: self.video_list_widget.addItems(newly_found)
            else: QtWidgets.QMessageBox.information(self, "No New Videos Found", f"No new video files were found in:\n{directory}")

    def remove_selected(self):
        selected_items = self.video_list_widget.selectedItems()
        if not selected_items: return
        for item in selected_items:
            row = self.video_list_widget.row(item)
            self.video_list_widget.takeItem(row)
            base_name = item.text()
            self.video_files = [f for f in self.video_files if os.path.basename(f) != base_name]

    def clear_all(self):
        self.video_list_widget.clear(); self.video_files.clear()
        
    def browse_model(self):
        file, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select YOLO Model", "", "PyTorch Models (*.pt)");
        if file: self.model_line_edit.setText(file)
    def browse_output(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory");
        if directory: self.output_dir_line_edit.setText(directory)
    def start_processing(self):
        if not self.video_files: QtWidgets.QMessageBox.warning(self, "Input Error", "Please add at least one video file."); return
        if not self.model_line_edit.text() or not os.path.exists(self.model_line_edit.text()): QtWidgets.QMessageBox.warning(self, "Input Error", "Please select a valid YOLO model (.pt) file."); return
        if not self.output_dir_line_edit.text() or not os.path.isdir(self.output_dir_line_edit.text()): QtWidgets.QMessageBox.warning(self, "Input Error", "Please select a valid output directory."); return
        if not self.save_video_checkbox.isChecked() and not self.save_csv_checkbox.isChecked(): QtWidgets.QMessageBox.warning(self, "Input Error", "Please select at least one output option."); return
        self.toggle_controls(False); self.log_text_edit.clear()
        self.yolo_worker = YoloProcessor(self.video_files, self.model_line_edit.text(), self.output_dir_line_edit.text(), self.confidence_spinbox.value(), save_video=self.save_video_checkbox.isChecked(), save_csv=self.save_csv_checkbox.isChecked())
        self.yolo_thread = QThread(); self.yolo_worker.moveToThread(self.yolo_thread)
        self.yolo_worker.overall_progress.connect(self.update_overall_progress); self.yolo_worker.file_progress.connect(self.update_file_progress); self.yolo_worker.log_message.connect(self.log_text_edit.append); self.yolo_worker.error.connect(self.on_processing_error); self.yolo_worker.finished.connect(self.on_processing_finished); self.yolo_worker.time_updated.connect(self.update_time_labels); self.yolo_worker.speed_updated.connect(self.update_speed_label); self.yolo_thread.started.connect(self.yolo_worker.run)
        self.yolo_thread.start()
    def cancel_processing(self):
        if self.yolo_worker: self.yolo_worker.stop(); self.cancel_btn.setEnabled(False)
    def on_processing_error(self, message):
        QtWidgets.QMessageBox.critical(self, "Error", message); self.on_processing_finished()
    def on_processing_finished(self):
        if self.yolo_thread: self.yolo_thread.quit(); self.yolo_thread.wait()
        self.toggle_controls(True)
        if self.yolo_worker and self.yolo_worker.is_running: QtWidgets.QMessageBox.information(self, "Finished", "YOLO inference has completed.")
    def update_overall_progress(self, current_num, total, filename):
        self.overall_progress_bar.setValue(int(current_num * 100 / total)); self.overall_progress_label.setText(f"Processing file {current_num} of {total}: {filename}")
        self.file_progress_bar.setValue(0); self.file_progress_label.setText("Frame: 0 / 0"); self.elapsed_time_label.setText("Elapsed: 00:00:00"); self.etr_label.setText("ETR: --:--:--")
        self.speed_label.setText("Speed: 0.00 FPS")
    def update_file_progress(self, percentage, current_frame, total_frames):
        self.file_progress_bar.setValue(percentage); self.file_progress_label.setText(f"Frame: {current_frame} / {total_frames}")
    def update_time_labels(self, elapsed, etr):
        self.elapsed_time_label.setText(f"Elapsed: {elapsed}"); self.etr_label.setText(f"ETR: {etr}")
    def update_speed_label(self, fps):
        self.speed_label.setText(f"Speed: {fps:.2f} FPS")
    def toggle_controls(self, enabled):
        self.start_btn.setEnabled(enabled); self.add_videos_btn.setEnabled(enabled); self.browse_model_btn.setEnabled(enabled); self.browse_output_btn.setEnabled(enabled); self.add_directory_btn.setEnabled(enabled); self.remove_video_btn.setEnabled(enabled); self.clear_videos_btn.setEnabled(enabled)
        self.cancel_btn.setEnabled(not enabled)
    def closeEvent(self, event):
        if self.yolo_thread and self.yolo_thread.isRunning():
            self.cancel_processing(); self.yolo_thread.quit(); self.yolo_thread.wait()
        event.accept()