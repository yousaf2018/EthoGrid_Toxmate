# EthoGrid_App/workers/updater.py

import os
import sys
import subprocess
import shutil
from PyQt5.QtCore import QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import QApplication

class Updater(QThread):
    log_message = pyqtSignal(str)
    update_available = pyqtSignal(bool, str) # bool: found, str: message
    finished = pyqtSignal()
    error = pyqtSignal(str)

    REPO_URL = "https://github.com/yousaf2018/EthoGrid.git"

    def __init__(self, mode, parent=None):
        super().__init__(parent)
        self.mode = mode # "check" or "update"
        # Determine the project root (one level up from the 'EthoGrid_App' dir)
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def run(self):
        try:
            subprocess.run(['git', '--version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        except (FileNotFoundError, subprocess.CalledProcessError):
            self.error.emit("Git not found. This feature requires Git to be installed and available in your system's PATH.")
            return

        try:
            if self.mode == "check":
                self.check_for_update()
            elif self.mode == "update":
                self.perform_update()
        except subprocess.CalledProcessError as e:
            error_output = e.stderr or e.stdout or "No error output from git."
            self.error.emit(f"A git command failed:\n\n{error_output}")
        except Exception as e:
            self.error.emit(f"An unexpected error occurred: {e}")
        finally:
            self.finished.emit()
            
    def check_for_update(self):
        git_dir = os.path.join(self.project_root, '.git')
        if not os.path.isdir(git_dir):
            self.log_message.emit("No local git repository found.")
            self.log_message.emit("An update is available (this will clone the entire project).")
            self.update_available.emit(True, "Clone latest version into a new folder.")
            return

        self.log_message.emit("Fetching latest information from remote repository...")
        subprocess.run(['git', 'fetch', 'origin'], check=True, capture_output=True, cwd=self.project_root)
        
        self.log_message.emit("Checking local status against remote 'main' branch...")
        status_result = subprocess.run(['git', 'status', '-uno'], check=True, capture_output=True, text=True, cwd=self.project_root)
        
        if "Your branch is up to date" in status_result.stdout:
            self.log_message.emit("\nResult: You are already running the latest version.")
            self.update_available.emit(False, "You are already running the latest version.")
        elif "Your branch is behind" in status_result.stdout:
            self.log_message.emit("\nResult: An update is available!")
            self.update_available.emit(True, "An update is available. This will overwrite local changes.")
        else:
            self.log_message.emit("\nResult: Could not determine update status. Your local branch may have diverged.")
            self.update_available.emit(False, "Cannot automatically update a diverged branch.")

    def perform_update(self):
        git_dir = os.path.join(self.project_root, '.git')
        if not os.path.isdir(git_dir):
            self.clone_repository()
        else:
            self.reset_repository()

    def clone_repository(self):
        self.log_message.emit("\nNo local git repository found.")
        self.log_message.emit(f"Cloning from {self.REPO_URL}...")
        
        # Clone into a new folder next to the current one
        parent_dir = os.path.dirname(self.project_root)
        clone_path = os.path.join(parent_dir, "EthoGrid_latest")
        
        if os.path.exists(clone_path):
            self.log_message.emit(f"Removing existing folder: {clone_path}")
            shutil.rmtree(clone_path)

        subprocess.run(['git', 'clone', self.REPO_URL, clone_path], check=True, capture_output=True, cwd=parent_dir)
        self.log_message.emit("\nSUCCESS!")
        self.log_message.emit(f"The latest version has been downloaded to:\n{clone_path}")
        self.log_message.emit("\nPlease close this application and run the 'main.py' from the new folder.")
        
    def reset_repository(self):
        self.log_message.emit("Fetching latest information from remote repository...")
        subprocess.run(['git', 'fetch', 'origin'], check=True, capture_output=True, cwd=self.project_root)
        
        self.log_message.emit("Forcing local code to match remote 'main' branch...")
        self.log_message.emit("(This will discard all local changes)")
        
        reset_result = subprocess.run(['git', 'reset', '--hard', 'origin/main'], check=True, capture_output=True, text=True, cwd=self.project_root)
        self.log_message.emit(reset_result.stdout.strip())
        
        self.log_message.emit("\nUpdate successful! Application will restart shortly.")
        
        # Schedule the restart to happen after the event loop has a chance to close windows
        QTimer.singleShot(2000, self.restart_app)

    def restart_app(self):
        QApplication.quit()
        os.execl(sys.executable, sys.executable, *sys.argv)