# EthoGrid_App/core/dependency_checker.py

import sys
import subprocess
import re

# --- State Constants ---
STATUS_OK = "OK"
STATUS_MISSING_TORCH = "MISSING_TORCH"
STATUS_MISSING_CUDA = "MISSING_CUDA"
STATUS_NO_NVIDIA_GPU = "NO_NVIDIA_GPU"

def check_dependencies():
    """
    Checks for PyTorch and CUDA availability.
    Returns a status code and a message/command.
    """
    try:
        import torch
        print("PyTorch is installed.")
        
        if torch.cuda.is_available():
            print("CUDA is available and configured with PyTorch.")
            return STATUS_OK, "All dependencies are satisfied."
        else:
            print("PyTorch is installed, but CUDA is not available.")
            # Check for NVIDIA driver
            try:
                result = subprocess.run(['nvidia-smi', '--query-gpu=driver_version,cuda_version', '--format=csv,noheader'], 
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
                
                driver_version, cuda_version = result.stdout.strip().split(',')
                cuda_version = cuda_version.strip()
                print(f"NVIDIA Driver found. System supports CUDA Version: {cuda_version}")

                # Find major.minor version (e.g., "12.1")
                match = re.match(r"(\d+\.\d+)", cuda_version)
                if not match:
                    return STATUS_MISSING_CUDA, "Could not parse CUDA version from nvidia-smi."
                
                cuda_major_minor = match.group(1)
                
                # Construct the correct pip install command
                # Note: This command uninstalls the old CPU-only torch first.
                install_command = (
                    f"{sys.executable} -m pip uninstall -y torch torchvision torchaudio && "
                    f"{sys.executable} -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu{cuda_major_minor.replace('.', '')}"
                )
                
                message = (
                    "EthoGrid has detected an NVIDIA GPU but PyTorch is not configured to use it.\n\n"
                    "To enable high-speed GPU processing, the correct PyTorch libraries must be installed."
                )
                return STATUS_MISSING_CUDA, message, install_command

            except (FileNotFoundError, subprocess.CalledProcessError):
                print("nvidia-smi command not found. No NVIDIA GPU or drivers detected.")
                return STATUS_NO_NVIDIA_GPU, "No NVIDIA GPU or drivers were detected. The application will run in CPU-only mode."

    except ImportError:
        print("PyTorch is not installed.")
        # We can default to installing the CPU version or prompt for GPU. Let's prompt for GPU first.
        # Here we just signal that torch is missing, the dialog will handle the rest.
        return STATUS_MISSING_TORCH, "PyTorch libraries are not installed. They are required to run the AI features."