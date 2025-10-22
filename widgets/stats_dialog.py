# EthoGrid_App/widgets/stats_dialog.py

import os
import pandas as pd
import json
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import QThread
from workers.stats_processor import StatsProcessor
from widgets.base_dialog import BaseDialog 

class FileListWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_list = QtWidgets.QListWidget()
        self.file_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.add_button = QtWidgets.QPushButton("Add File(s)...")
        self.remove_button = QtWidgets.QPushButton("Remove Selected")
        self.clear_button = QtWidgets.QPushButton("Clear All")
        
        layout = QtWidgets.QVBoxLayout(self); button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.add_button); button_layout.addWidget(self.remove_button); button_layout.addWidget(self.clear_button)
        layout.addWidget(self.file_list); layout.addLayout(button_layout); layout.setContentsMargins(0,0,0,0)
        
    def add_files(self, file_paths):
        current_paths = self.get_full_paths()
        for path in file_paths:
            if path not in current_paths:
                item = QtWidgets.QListWidgetItem(os.path.basename(path)); item.setData(QtCore.Qt.UserRole, path); item.setToolTip(path)
                self.file_list.addItem(item)
            
    def remove_selected_files(self):
        for item in self.file_list.selectedItems(): self.file_list.takeItem(self.file_list.row(item))
            
    def clear_files(self): self.file_list.clear()
    def get_full_paths(self): return [self.file_list.item(i).data(QtCore.Qt.UserRole) for i in range(self.file_list.count())]

class StatsDialog(BaseDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("Statistical Analysis"); self.setMinimumSize(1200, 800)
        self.group_widgets = {} 
        
        main_layout = QtWidgets.QVBoxLayout(self)
        top_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        
        left_pane_scroll = QtWidgets.QScrollArea(); left_pane_scroll.setWidgetResizable(True)
        left_pane_widget = QtWidgets.QWidget(); self.left_pane = QtWidgets.QVBoxLayout(left_pane_widget)
        left_pane_scroll.setWidget(left_pane_widget)
        
        right_pane_widget = QtWidgets.QWidget(); right_pane = QtWidgets.QVBoxLayout(right_pane_widget)
        
        self.input_group = QtWidgets.QGroupBox("1. Input Data & Groups"); self.input_layout = QtWidgets.QVBoxLayout(self.input_group)
        self.add_group_button = QtWidgets.QPushButton("Add New Group..."); self.input_layout.addWidget(self.add_group_button)
        self.left_pane.addWidget(self.input_group)
        
        level_group = QtWidgets.QGroupBox("2. Select Analysis Level"); level_layout = QtWidgets.QFormLayout(level_group)
        self.level_combo = QtWidgets.QComboBox(); self.level_combo.addItems(["Compare Grand Averages", "Compare Sheet Averages", "Compare Tanks"])
        level_layout.addRow(self.level_combo); self.left_pane.addWidget(level_group)

        endpoints_group = QtWidgets.QGroupBox("3. Endpoints to Analyze"); endpoints_layout = QtWidgets.QVBoxLayout(endpoints_group)
        self.endpoints_scroll = QtWidgets.QScrollArea(); self.endpoints_scroll.setWidgetResizable(True)
        self.endpoints_widget = QtWidgets.QWidget(); self.endpoints_cb_layout = QtWidgets.QVBoxLayout(self.endpoints_widget)
        self.endpoints_scroll.setWidget(self.endpoints_widget)
        self.select_all_btn = QtWidgets.QPushButton("Select All / Deselect All")
        endpoints_layout.addWidget(self.endpoints_scroll); endpoints_layout.addWidget(self.select_all_btn); self.left_pane.addWidget(endpoints_group)

        params_group = QtWidgets.QGroupBox("4. Analysis Parameters"); params_layout = QtWidgets.QFormLayout(params_group)
        self.normality_test_combo = QtWidgets.QComboBox(); self.normality_test_combo.addItems(["Shapiro-Wilk", "D'Agostino-Pearson"])
        self.alpha_spinbox = QtWidgets.QDoubleSpinBox(value=0.05, minimum=0.001, maximum=0.1, singleStep=0.01, decimals=3)
        self.force_parametric_cb = QtWidgets.QCheckBox("Force Parametric Test (ignore normality)")
        self.parametric_label = QtWidgets.QLabel("T-test (2 groups) / ANOVA (>2 groups)")
        self.nonparametric_label = QtWidgets.QLabel("Mann-Whitney (2 groups) / Kruskal-Wallis (>2 groups)")
        params_layout.addRow("Normality Test:", self.normality_test_combo); params_layout.addRow("Alpha (p-value):", self.alpha_spinbox)
        params_layout.addRow("If Normal:", self.parametric_label); params_layout.addRow("If Not Normal:", self.nonparametric_label)
        params_layout.addRow(self.force_parametric_cb); self.left_pane.addWidget(params_group)

        plot_group = QtWidgets.QGroupBox("5. Plot Customization"); plot_layout = QtWidgets.QFormLayout(plot_group)
        self.central_tendency_combo = QtWidgets.QComboBox(); self.central_tendency_combo.addItems(["Mean", "Median", "None (Bar Only)"])
        self.error_bar_combo = QtWidgets.QComboBox(); self.error_bar_combo.addItems(["SD", "SEM"])
        self.palette_combo = QtWidgets.QComboBox(); self.palette_combo.addItems(['pastel', 'muted', 'deep', 'viridis', 'plasma'])
        self.plot_width_spinbox = QtWidgets.QSpinBox(value=800, minimum=400, maximum=3000, singleStep=50, suffix=" px"); self.plot_height_spinbox = QtWidgets.QSpinBox(value=600, minimum=400, maximum=3000, singleStep=50, suffix=" px")
        self.plot_dpi_spinbox = QtWidgets.QSpinBox(value=300, minimum=72, maximum=600, singleStep=10, suffix=" DPI")
        self.title_size_spinbox = QtWidgets.QSpinBox(value=16, minimum=8, maximum=30); self.axes_size_spinbox = QtWidgets.QSpinBox(value=12, minimum=6, maximum=24); self.tick_size_spinbox = QtWidgets.QSpinBox(value=10, minimum=6, maximum=20)
        self.title_weight_combo = QtWidgets.QComboBox(); self.title_weight_combo.addItems(["bold", "normal"]); self.axes_weight_combo = QtWidgets.QComboBox(); self.axes_weight_combo.addItems(["normal", "bold"])
        
        plot_layout.addRow("Bar Height:", self.central_tendency_combo); plot_layout.addRow("Error Bar Type:", self.error_bar_combo); plot_layout.addRow("Color Palette:", self.palette_combo)
        plot_layout.addRow("Plot Width / Height (px):", self.create_hbox(self.plot_width_spinbox, self.plot_height_spinbox)); plot_layout.addRow("Plot DPI:", self.plot_dpi_spinbox)
        plot_layout.addRow("Title Font Size / Weight:", self.create_hbox(self.title_size_spinbox, self.title_weight_combo)); plot_layout.addRow("Axes Label Font Size / Weight:", self.create_hbox(self.axes_size_spinbox, self.axes_weight_combo)); plot_layout.addRow("Axes Tick Font Size:", self.tick_size_spinbox); self.left_pane.addWidget(plot_group)
        self.left_pane.addStretch()
        
        self.save_analysis_settings_btn = QtWidgets.QPushButton("Save Settings"); self.load_analysis_settings_btn = QtWidgets.QPushButton("Load Settings")
        settings_button_layout = QtWidgets.QHBoxLayout(); settings_button_layout.addStretch(); settings_button_layout.addWidget(self.load_analysis_settings_btn); settings_button_layout.addWidget(self.save_analysis_settings_btn)
        self.left_pane.addLayout(settings_button_layout)
        
        self.plot_tabs = QtWidgets.QTabWidget(); self.report_text = QtWidgets.QTextEdit(); self.report_text.setReadOnly(True)
        right_pane.addWidget(self.plot_tabs, stretch=2); right_pane.addWidget(QtWidgets.QLabel("Consolidated Report:")); right_pane.addWidget(self.report_text, stretch=1)
        
        right_pane_container = QtWidgets.QWidget(); right_pane_container.setLayout(right_pane)
        top_splitter.addWidget(left_pane_scroll); top_splitter.addWidget(right_pane_container); top_splitter.setSizes([400, 800])
        main_layout.addWidget(top_splitter)
        
        bottom_controls_widget = QtWidgets.QWidget()
        bottom_layout = QtWidgets.QHBoxLayout(bottom_controls_widget)
        self.output_dir_line_edit = QtWidgets.QLineEdit(); self.output_dir_line_edit.setPlaceholderText("Select folder to save results")
        self.browse_output_btn = QtWidgets.QPushButton("Browse..."); self.start_btn = QtWidgets.QPushButton("Run Analysis")
        bottom_layout.addWidget(self.output_dir_line_edit); bottom_layout.addWidget(self.browse_output_btn); bottom_layout.addWidget(self.start_btn)
        main_layout.addWidget(bottom_controls_widget)
        
        self.add_group_button.clicked.connect(self.add_group); self.select_all_btn.clicked.connect(self.toggle_select_all_endpoints); self.browse_output_btn.clicked.connect(self.browse_output); self.start_btn.clicked.connect(self.start_analysis)
        self.central_tendency_combo.currentTextChanged.connect(self.on_central_tendency_changed)
        self.save_analysis_settings_btn.clicked.connect(self.save_analysis_settings); self.load_analysis_settings_btn.clicked.connect(self.load_analysis_settings)
        self.on_central_tendency_changed(self.central_tendency_combo.currentText())

    def create_hbox(self, w1, w2):
        widget = QtWidgets.QWidget(); layout = QtWidgets.QHBoxLayout(widget); layout.addWidget(w1); layout.addWidget(w2); layout.setContentsMargins(0,0,0,0); return widget
    
    def on_central_tendency_changed(self, text):
        self.error_bar_combo.setEnabled(text == "Mean")

    def add_group(self, name="", paths=None):
        group_name = name
        if not name:
            group_name, ok = QtWidgets.QInputDialog.getText(self, "Add Group", "Enter new group name (e.g., 'Control', 'Treatment A'):")
            if not (ok and group_name and group_name not in self.group_widgets):
                return
        
        group_box = QtWidgets.QGroupBox(group_name); group_box.setCheckable(True); group_box.setChecked(True)
        group_layout = QtWidgets.QVBoxLayout(group_box)
        file_list = FileListWidget()
        if paths: file_list.add_files(paths)
        group_layout.addWidget(file_list)
        file_list.add_button.clicked.connect(lambda: self.add_files(file_list))
        file_list.remove_button.clicked.connect(lambda: self.remove_files(file_list))
        file_list.clear_button.clicked.connect(lambda: self.clear_files(file_list))
        group_box.toggled.connect(lambda checked, gb=group_box: self.toggle_group(gb, checked))
        self.input_layout.insertWidget(self.input_layout.count() - 1, group_box)
        self.group_widgets[group_name] = file_list
        self.load_endpoints_from_files()

    def toggle_group(self, group_box, checked):
        if not checked:
            group_name = group_box.title()
            if group_name in self.group_widgets: del self.group_widgets[group_name]
            group_box.deleteLater(); self.load_endpoints_from_files()

    def add_files(self, file_list_widget):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Select Endpoints File(s)", "", "Excel Files (*.xlsx)")
        if files: QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor); file_list_widget.add_files(files); self.load_endpoints_from_files(); QtWidgets.QApplication.restoreOverrideCursor()

    def remove_files(self, file_list_widget):
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor); file_list_widget.remove_selected_files(); self.load_endpoints_from_files(); QtWidgets.QApplication.restoreOverrideCursor()
    
    def clear_files(self, file_list_widget):
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor); file_list_widget.clear_files(); self.load_endpoints_from_files(); QtWidgets.QApplication.restoreOverrideCursor()

    def load_endpoints_from_files(self):
        all_paths = [path for widget in self.group_widgets.values() for path in widget.get_full_paths()]
        self.clear_endpoint_list()
        if not all_paths: return
        try:
            common_endpoints = None
            for path in all_paths:
                df = pd.read_excel(path, sheet_name='GRAND_AVERAGE_SUMMARY', nrows=0)
                current_endpoints = set(col for col in df.columns if col not in ['File', 'Tank'])
                if common_endpoints is None: common_endpoints = current_endpoints
                else: common_endpoints.intersection_update(current_endpoints)
            if common_endpoints:
                for ep in sorted(list(common_endpoints)): cb = QtWidgets.QCheckBox(ep); cb.setChecked(True); self.endpoints_cb_layout.addWidget(cb)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "File Error", f"Could not read endpoints from file: {os.path.basename(all_paths[0])}\nError: {e}")

    def clear_endpoint_list(self):
        while self.endpoints_cb_layout.count():
            self.endpoints_cb_layout.takeAt(0).widget().deleteLater()

    def toggle_select_all_endpoints(self):
        all_selected = all(self.endpoints_cb_layout.itemAt(i).widget().isChecked() for i in range(self.endpoints_cb_layout.count()))
        for i in range(self.endpoints_cb_layout.count()):
            self.endpoints_cb_layout.itemAt(i).widget().setChecked(not all_selected)

    def browse_output(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory: self.output_dir_line_edit.setText(directory)

    def save_analysis_settings(self):
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Analysis Settings", "stats_settings.json", "JSON Files (*.json)")
        if not file_path: return
        settings = {'groups': {}, 'parameters': {}, 'plot': {}}
        for name, widget in self.group_widgets.items(): settings['groups'][name] = widget.get_full_paths()
        p = settings['parameters']; p['level'] = self.level_combo.currentText(); p['normality_test'] = self.normality_test_combo.currentText(); p['alpha'] = self.alpha_spinbox.value(); p['force_parametric'] = self.force_parametric_cb.isChecked()
        p['endpoints'] = [self.endpoints_cb_layout.itemAt(i).widget().text() for i in range(self.endpoints_cb_layout.count()) if self.endpoints_cb_layout.itemAt(i).widget().isChecked()]
        plot = settings['plot']; plot['central_tendency'] = self.central_tendency_combo.currentText(); plot['error_bar'] = self.error_bar_combo.currentText(); plot['palette'] = self.palette_combo.currentText()
        plot['width'] = self.plot_width_spinbox.value(); plot['height'] = self.plot_height_spinbox.value(); plot['dpi'] = self.plot_dpi_spinbox.value()
        plot['title_size'] = self.title_size_spinbox.value(); plot['axes_size'] = self.axes_size_spinbox.value(); plot['tick_size'] = self.tick_size_spinbox.value()
        plot['title_weight'] = self.title_weight_combo.currentText(); plot['axes_weight'] = self.axes_weight_combo.currentText()
        try:
            with open(file_path, 'w') as f: json.dump(settings, f, indent=4)
            QtWidgets.QMessageBox.information(self, "Success", "Analysis settings saved.")
        except Exception as e: self.show_error(f"Failed to save settings: {e}")

    def load_analysis_settings(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Analysis Settings", "", "JSON Files (*.json)")
        if not file_path: return
        try:
            with open(file_path, 'r') as f: settings = json.load(f)
            
            for i in reversed(range(self.input_layout.count())):
                item = self.input_layout.itemAt(i); widget = item.widget()
                if isinstance(widget, QtWidgets.QGroupBox): widget.deleteLater()
            self.group_widgets.clear()
            for name, paths in settings.get('groups', {}).items():
                self.add_group(name=name, paths=paths)
            
            p = settings.get('parameters', {}); self.level_combo.setCurrentText(p.get('level', "Compare Grand Averages")); self.normality_test_combo.setCurrentText(p.get('normality_test', "Shapiro-Wilk")); self.alpha_spinbox.setValue(p.get('alpha', 0.05)); self.force_parametric_cb.setChecked(p.get('force_parametric', False))
            self.load_endpoints_from_files()
            selected_endpoints = p.get('endpoints', [])
            for i in range(self.endpoints_cb_layout.count()):
                self.endpoints_cb_layout.itemAt(i).widget().setChecked(self.endpoints_cb_layout.itemAt(i).widget().text() in selected_endpoints)

            plot = settings.get('plot', {}); self.central_tendency_combo.setCurrentText(plot.get('central_tendency', 'Mean')); self.error_bar_combo.setCurrentText(plot.get('error_bar', 'SD')); self.palette_combo.setCurrentText(plot.get('palette', 'pastel'))
            self.plot_width_spinbox.setValue(plot.get('width', 800)); self.plot_height_spinbox.setValue(plot.get('height', 600)); self.plot_dpi_spinbox.setValue(plot.get('dpi', 300))
            self.title_size_spinbox.setValue(plot.get('title_size', 16)); self.axes_size_spinbox.setValue(plot.get('axes_size', 12)); self.tick_size_spinbox.setValue(plot.get('tick_size', 10))
            self.title_weight_combo.setCurrentText(plot.get('title_weight', 'bold')); self.axes_weight_combo.setCurrentText(plot.get('axes_weight', 'normal'))
            
            QtWidgets.QMessageBox.information(self, "Success", "Analysis settings loaded.")
        except Exception as e: self.show_error(f"Failed to load settings: {e}")

    def start_analysis(self):
        group_files = {}
        for name, widget in self.group_widgets.items():
            group_box = widget.parentWidget()
            if group_box.isChecked():
                paths = widget.get_full_paths()
                if paths: group_files[name] = paths
        
        if len(group_files) < 2: QtWidgets.QMessageBox.warning(self, "Input Error", "Please add files to at least two different active groups for comparison."); return
        if not self.output_dir_line_edit.text() or not os.path.isdir(self.output_dir_line_edit.text()): QtWidgets.QMessageBox.warning(self, "Input Error", "Please select a valid output directory."); return
        
        selected_endpoints = [self.endpoints_cb_layout.itemAt(i).widget().text() for i in range(self.endpoints_cb_layout.count()) if self.endpoints_cb_layout.itemAt(i).widget().isChecked()]
        if not selected_endpoints: QtWidgets.QMessageBox.warning(self, "Input Error", "Please select at least one endpoint to analyze."); return
        
        plot_params = {'central_tendency': self.central_tendency_combo.currentText(), 'error_bar': self.error_bar_combo.currentText(), 'palette': self.palette_combo.currentText(), 'width': self.plot_width_spinbox.value(), 'height': self.plot_height_spinbox.value(), 'dpi': self.plot_dpi_spinbox.value(), 'title_size': self.title_size_spinbox.value(), 'axes_size': self.axes_size_spinbox.value(), 'tick_size': self.tick_size_spinbox.value(), 'title_weight': self.title_weight_combo.currentText(), 'axes_weight': self.axes_weight_combo.currentText()}
        
        self.start_btn.setEnabled(False); self.report_text.clear(); self.plot_tabs.clear()

        self.worker = StatsProcessor(group_files, self.level_combo.currentText(), selected_endpoints, self.normality_test_combo.currentText(), self.alpha_spinbox.value(), self.force_parametric_cb.isChecked(), self.parametric_label.text(), self.nonparametric_label.text(), plot_params, self.output_dir_line_edit.text())
        self.thread = QThread(); self.worker.moveToThread(self.thread)
        self.worker.finished.connect(self.on_analysis_finished); self.worker.plot_generated.connect(self.add_plot_tab); self.worker.log.connect(self.report_text.append); self.worker.error.connect(self.on_analysis_error); self.thread.started.connect(self.worker.run); self.thread.start()

    def add_plot_tab(self, name, path):
        tab = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(tab); scroll = QtWidgets.QScrollArea(); scroll.setWidgetResizable(True)
        label = QtWidgets.QLabel(); pixmap = QtGui.QPixmap(path); label.setPixmap(pixmap); scroll.setWidget(label)
        layout.addWidget(scroll); self.plot_tabs.addTab(tab, name)
    
    def on_analysis_finished(self):
        QtWidgets.QMessageBox.information(self, "Finished", "Analysis complete. Plots and report have been saved."); self.cleanup_thread()
    
    def on_analysis_error(self, message):
        QtWidgets.QMessageBox.critical(self, "Error", message); self.cleanup_thread()
        
    def cleanup_thread(self):
        self.start_btn.setEnabled(True)
        if hasattr(self, 'thread') and self.thread is not None:
            self.thread.quit(); self.thread.wait(); self.thread = None

    def show_error(self, message):
        QtWidgets.QMessageBox.critical(self, "Error", message)