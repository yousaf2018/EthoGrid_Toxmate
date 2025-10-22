# EthoGrid_App/widgets/frame_extractor_dialog.py

import os
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QThread
from workers.frame_extractor import FrameExtractor
from widgets.base_dialog import BaseDialog 

class FrameExtractorDialog(BaseDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Frame Extractor")
        self.setMinimumSize(700, 600)
        self.video_files = []
        self.parent_directory = "" # Store the selected parent directory
        self.extractor_thread = None
        self.extractor_worker = None
        
        main_widget = QtWidgets.QWidget(); form_layout = QtWidgets.QGridLayout(main_widget)
        
        self.video_list_widget = QtWidgets.QListWidget(); self.video_list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.add_videos_btn = QtWidgets.QPushButton("Add Video(s)..."); self.add_directory_btn = QtWidgets.QPushButton("Add Directory...")
        self.remove_video_btn = QtWidgets.QPushButton("Remove Selected"); self.clear_videos_btn = QtWidgets.QPushButton("Clear All")
        
        self.output_dir_line_edit = QtWidgets.QLineEdit(); self.output_dir_line_edit.setPlaceholderText("Select a folder to save the extracted frames")
        self.browse_output_btn = QtWidgets.QPushButton("Browse...")
        
        self.frame_count_spinbox = QtWidgets.QSpinBox(value=100, minimum=1, maximum=10000, toolTip="The number of frames to extract from each video, spaced evenly.")
        
        self.start_btn = QtWidgets.QPushButton("Start Extraction"); self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.overall_progress_bar = QtWidgets.QProgressBar(); self.overall_progress_label = QtWidgets.QLabel("Waiting to start...")
        self.file_progress_bar = QtWidgets.QProgressBar(); self.file_progress_label = QtWidgets.QLabel("Frame: 0/0")
        self.log_text_edit = QtWidgets.QTextEdit(); self.log_text_edit.setReadOnly(True)

        file_buttons_layout = QtWidgets.QVBoxLayout(); file_buttons_layout.addWidget(self.add_videos_btn); file_buttons_layout.addWidget(self.add_directory_btn); file_buttons_layout.addWidget(self.remove_video_btn); file_buttons_layout.addWidget(self.clear_videos_btn); file_buttons_layout.addStretch()
        form_layout.addWidget(QtWidgets.QLabel("Video Files to Process:"), 0, 0); form_layout.addWidget(self.video_list_widget, 1, 0, 1, 2); form_layout.addLayout(file_buttons_layout, 1, 2)
        form_layout.addWidget(QtWidgets.QLabel("Output Folder:"), 2, 0); form_layout.addWidget(self.output_dir_line_edit, 3, 0); form_layout.addWidget(self.browse_output_btn, 3, 1)
        
        options_group = QtWidgets.QGroupBox("Options")
        options_layout = QtWidgets.QFormLayout(options_group)
        options_layout.addRow("Frames to Extract per Video:", self.frame_count_spinbox)
        form_layout.addWidget(options_group, 4, 0, 1, 3)

        scroll_area = QtWidgets.QScrollArea(); scroll_area.setWidgetResizable(True); scroll_area.setWidget(main_widget)
        main_dialog_layout = QtWidgets.QVBoxLayout(self); main_dialog_layout.addWidget(scroll_area)
        
        progress_group = QtWidgets.QGroupBox("Progress"); progress_layout = QtWidgets.QVBoxLayout(progress_group)
        progress_layout.addWidget(self.overall_progress_label); progress_layout.addWidget(self.overall_progress_bar)
        progress_layout.addWidget(self.file_progress_label); progress_layout.addWidget(self.file_progress_bar)
        main_dialog_layout.addWidget(progress_group)
        log_group = QtWidgets.QGroupBox("Log"); log_layout = QtWidgets.QVBoxLayout(log_group); log_layout.addWidget(self.log_text_edit)
        main_dialog_layout.addWidget(log_group)
        button_layout = QtWidgets.QHBoxLayout(); button_layout.addStretch(); button_layout.addWidget(self.cancel_btn); button_layout.addWidget(self.start_btn)
        main_dialog_layout.addLayout(button_layout)

        self.add_videos_btn.clicked.connect(self.add_videos); self.add_directory_btn.clicked.connect(self.add_directory); self.remove_video_btn.clicked.connect(self.remove_selected); self.clear_videos_btn.clicked.connect(self.clear_all)
        self.browse_output_btn.clicked.connect(self.browse_output); self.start_btn.clicked.connect(self.start_extraction); self.cancel_btn.clicked.connect(self.cancel_extraction)
        self.cancel_btn.setEnabled(False)

    def add_videos(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Select Video Files", "", "Video Files (*.mp4 *.avi *.mov *.mkv)")
        if files:
            self.parent_directory = os.path.dirname(files[0]) # Use parent of first file as reference
            newly_added = []
            for f in files:
                if f not in self.video_files: self.video_files.append(f); newly_added.append(os.path.basename(f))
            if newly_added: self.video_list_widget.addItems(newly_added)

    def add_directory(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory Containing Videos")
        if directory:
            self.parent_directory = directory # Store the top-level directory
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
        self.video_list_widget.clear(); self.video_files.clear(); self.parent_directory = ""

    def browse_output(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory");
        if directory: self.output_dir_line_edit.setText(directory)

    def start_extraction(self):
        if not self.video_files: QtWidgets.QMessageBox.warning(self, "Input Error", "Please add at least one video file."); return
        if not self.output_dir_line_edit.text() or not os.path.isdir(self.output_dir_line_edit.text()): QtWidgets.QMessageBox.warning(self, "Input Error", "Please select a valid output directory."); return
        if not self.parent_directory: QtWidgets.QMessageBox.warning(self, "Input Error", "Could not determine a parent directory for naming. Please use 'Add Directory'."); return
        
        self.toggle_controls(False); self.log_text_edit.clear()
        self.extractor_worker = FrameExtractor(self.video_files, self.parent_directory, self.output_dir_line_edit.text(), self.frame_count_spinbox.value())
        self.extractor_thread = QThread(); self.extractor_worker.moveToThread(self.extractor_thread)
        self.extractor_worker.overall_progress.connect(self.update_overall_progress); self.extractor_worker.file_progress.connect(self.update_file_progress); self.extractor_worker.log_message.connect(self.log_text_edit.append); self.extractor_worker.finished.connect(self.on_extraction_finished); self.extractor_worker.error.connect(self.on_processing_error); self.extractor_thread.started.connect(self.extractor_worker.run)
        self.extractor_thread.start()

    def cancel_extraction(self):
        if self.extractor_worker: self.extractor_worker.stop(); self.cancel_btn.setEnabled(False)
    def on_processing_error(self, message):
        QtWidgets.QMessageBox.critical(self, "Error", message); self.on_extraction_finished()
    def on_extraction_finished(self):
        if self.extractor_thread: self.extractor_thread.quit(); self.extractor_thread.wait()
        self.toggle_controls(True)
        if self.extractor_worker and self.extractor_worker.is_running: QtWidgets.QMessageBox.information(self, "Finished", "Frame extraction has completed.")
    def update_overall_progress(self, current_num, total, filename):
        self.overall_progress_bar.setValue(int(current_num * 100 / total)); self.overall_progress_label.setText(f"Processing file {current_num} of {total}: {filename}")
        self.file_progress_bar.setValue(0); self.file_progress_label.setText("Frame: 0/0")
    def update_file_progress(self, percentage, current_frame, total_frames):
        self.file_progress_bar.setValue(percentage); self.file_progress_label.setText(f"Frame: {current_frame} / {total_frames}")
    def toggle_controls(self, enabled):
        self.start_btn.setEnabled(enabled); self.add_videos_btn.setEnabled(enabled); self.add_directory_btn.setEnabled(enabled); self.remove_video_btn.setEnabled(enabled); self.clear_videos_btn.setEnabled(enabled); self.browse_output_btn.setEnabled(enabled)
        self.cancel_btn.setEnabled(not enabled)
    def closeEvent(self, event):
        if self.extractor_thread and self.extractor_thread.isRunning():
            self.cancel_extraction(); self.extractor_thread.quit(); self.extractor_thread.wait()
        event.accept()