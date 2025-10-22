# Use NVIDIA CUDA base for GPU + Ultralytics support
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV QT_X11_NO_MITSHM=1

# Install system dependencies for PyQt5 + OpenCV + GUI
# Added Acquire::Check-Date=false to bypass timestamp issues inside Docker/WSL2
RUN apt-get -o Acquire::Check-Valid-Until=false -o Acquire::Check-Date=false update && \
    apt-get install -y --no-install-recommends \
    git python3 python3-pip python3-dev \
    libgl1-mesa-glx libglib2.0-0 \
    libxkbcommon-x11-0 \
    x11-apps \
    && rm -rf /var/lib/apt/lists/*

# Set python alias
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1

# Clone your GitHub repo into /app
WORKDIR /app
RUN git clone https://github.com/yousaf2018/EthoGrid.git .

# Install Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Default command: run your PyQt5 GUI app
CMD ["python", "main.py"]
