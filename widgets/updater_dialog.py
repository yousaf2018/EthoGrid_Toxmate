# EthoGrid_App/widgets/updater_dialog.py

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QThread
from workers.updater import Updater
from widgets.base_dialog import BaseDialog

class UpdaterDialog(BaseDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Application Updater")
        self.setMinimumSize(600, 400)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        warning_label = QtWidgets.QLabel(
            "<b>WARNING:</b> This tool will use 'git' to download the latest version of the application.\n"
            "This process will <b>discard any local changes</b> you have made to the source code.\n\n"
            "Ensure you have 'git' installed and accessible in your system's PATH."
        )
        warning_label.setWordWrap(True)
        
        self.log_view = QtWidgets.QTextEdit()
        self.log_view.setReadOnly(True)
        
        self.check_button = QtWidgets.QPushButton("Check for Updates")
        self.update_button = QtWidgets.QPushButton("Download Update & Restart")
        self.close_button = QtWidgets.QPushButton("Close")
        
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.check_button)
        button_layout.addWidget(self.update_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        
        layout.addWidget(warning_label)
        layout.addWidget(self.log_view)
        layout.addLayout(button_layout)
        
        self.update_button.setEnabled(False)
        
        self.check_button.clicked.connect(self.run_check)
        self.update_button.clicked.connect(self.run_update)
        self.close_button.clicked.connect(self.accept)

    def run_check(self):
        self.toggle_controls(False)
        self.log_view.clear()
        self.log_view.append("Starting update check...")
        
        self.worker = Updater(mode="check")
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        
        self.worker.log_message.connect(self.log_view.append)
        self.worker.error.connect(self.on_error)
        self.worker.update_available.connect(self.on_check_complete)
        self.worker.finished.connect(self.cleanup_thread)
        
        self.thread.started.connect(self.worker.run)
        self.thread.start()
        
    def run_update(self):
        self.toggle_controls(False)
        self.log_view.append("\nStarting update process...")
        
        self.worker = Updater(mode="update")
        self.thread = QThread()
        self.worker.moveToThread(self.thread)

        self.worker.log_message.connect(self.log_view.append)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.cleanup_thread) # Worker handles restart

        self.thread.started.connect(self.worker.run)
        self.thread.start()

    def on_check_complete(self, update_found):
        self.update_button.setEnabled(update_found)
        if not update_found:
            QtWidgets.QMessageBox.information(self, "Up to Date", "You are already running the latest version.")
        
    def on_error(self, message):
        QtWidgets.QMessageBox.critical(self, "Update Error", message)
        self.toggle_controls(True)
        self.update_button.setEnabled(False)
        
    def cleanup_thread(self):
        if not self.update_button.isEnabled():
            self.toggle_controls(True)
        if hasattr(self, 'thread') and self.thread is not None:
            self.thread.quit()
            self.thread.wait()
            self.thread = None
            
    def toggle_controls(self, enabled):
        self.check_button.setEnabled(enabled)
        self.close_button.setEnabled(enabled)
        # Update button is controlled separately by on_check_complete