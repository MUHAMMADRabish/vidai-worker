FROM continuumio/miniconda3:latest

# Install CUDA and system deps
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    wget \
    git \
    curl \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install CUDA toolkit
RUN conda install -y -c nvidia cuda-toolkit=11.8 || true

# Create Python 3.10 environment
RUN conda create -n musetalk python=3.10 -y

# Install PyTorch in musetalk env
RUN conda run -n musetalk pip install torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cu118

# Clone MuseTalk
RUN git clone https://github.com/TMElyralab/MuseTalk.git /MuseTalk
WORKDIR /MuseTalk

# Install MuseTalk requirements
RUN conda run -n musetalk pip install -r requirements.txt

# Install mmlab packages
RUN conda run -n musetalk pip install openmim
RUN conda run -n musetalk mim install mmengine
RUN conda run -n musetalk mim install "mmcv>=2.0.1"
RUN conda run -n musetalk mim install "mmdet>=3.1.0"
RUN conda run -n musetalk mim install "mmpose>=1.1.0"

# Download MuseTalk models
RUN conda run -n musetalk huggingface-cli download TMElyralab/MuseTalk --local-dir /MuseTalk/models

# Install handler dependencies
RUN conda run -n musetalk pip install runpod boto3 edge-tts Pillow nest_asyncio

# Copy handler
COPY handler.py /handler.py

WORKDIR /
CMD ["/opt/conda/envs/musetalk/bin/python", "-u", "/handler.py"]
