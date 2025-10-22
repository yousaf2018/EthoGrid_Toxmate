# EthoGrid_App/widgets/installer_dialog.py

import subprocess
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QThread, pyqtSignal

class InstallWorker(QThread):
    log_message = pyqtSignal(str)
    finished = pyqtSignal(int)

    def __init__(self, command, parent=None):
        super().__init__(parent)
        self.command = command

    def run(self):
        self.log_message.emit(f"Running command:\n{self.command}\n")
        self.log_message.emit("This may take several minutes. Please be patient...")
        
        # Use shell=True for complex commands with '&&'
        process = subprocess.Popen(self.command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True, bufsize=1)
        
        for line in iter(process.stdout.readline, ''):
            self.log_message.emit(line.strip())
        
        process.wait()
        self.finished.emit(process.returncode)

class InstallerDialog(QtWidgets.QDialog):
    def __init__(self, message, command=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dependency Installation")
        self.setMinimumSize(600, 400)
        self.command = command
        
        self.message_label = QtWidgets.QLabel(message)
        self.message_label.setWordWrap(True)
        
        self.log_view = QtWidgets.QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QtGui.QFont("Courier", 9))
        
        self.install_button = QtWidgets.QPushButton("Install Automatically")
        self.restart_button = QtWidgets.QPushButton("Restart Application")
        self.close_button = QtWidgets.QPushButton("Close")
        
        self.restart_button.hide()
        
        if not self.command:
            self.install_button.hide()

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.message_label)
        layout.addWidget(self.log_view)
        
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.install_button)
        button_layout.addWidget(self.restart_button)
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)
        
        self.install_button.clicked.connect(self.start_installation)
        self.restart_button.clicked.connect(self.restart_app)
        self.close_button.clicked.connect(self.accept)

    def start_installation(self):
        self.install_button.setEnabled(False)
        self.close_button.setEnabled(False)
        
        self.worker = InstallWorker(self.command)
        self.worker.log_message.connect(self.log_view.append)
        self.worker.finished.connect(self.on_installation_finished)
        self.worker.start()

    def on_installation_finished(self, return_code):
        if return_code == 0:
            self.log_view.append("\n\nInstallation completed successfully!")
            self.message_label.setText("Installation successful. Please restart the application for the changes to take effect.")
        else:
            self.log_view.append(f"\n\nInstallation failed with error code: {return_code}")
            self.message_label.setText("Installation failed. Please check the log above for errors. You may need to run the command manually in a terminal.")
        
        self.restart_button.show()
        self.close_button.setEnabled(True)
        
    def restart_app(self):
        # This is a simple way to restart. A more robust solution might involve a launcher script.
        QtCore.QCoreApplication.quit()
        status = QtCore.QProcess.startDetached(sys.executable, sys.argv)