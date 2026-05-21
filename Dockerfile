FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

ENV TORCH_CUDA_ARCH_LIST="6.0 6.1 7.0 7.5 8.0 8.6 8.9 9.0 12.0"

# Install system dependencies
RUN apt-get update -y && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir runpod boto3 nest_asyncio edge-tts Pillow

# Fix basicsr/torchvision compatibility with PyTorch 2.4+
RUN pip install --no-cache-dir "basicsr @ git+https://github.com/XPixelGroup/BasicSR.git"
RUN pip install --no-cache-dir facexlib gfpgan

# Install SadTalker
RUN git clone https://github.com/OpenTalker/SadTalker.git /SadTalker
WORKDIR /SadTalker
RUN pip install --no-cache-dir -r requirements.txt

# Force-reinstall imageio after SadTalker deps to override any newer version
RUN pip install --no-cache-dir --force-reinstall imageio==2.31.1 imageio-ffmpeg==0.4.9
RUN pip install --no-cache-dir --force-reinstall numpy==1.26.4
RUN pip install --no-cache-dir --force-reinstall opencv-python-headless==4.8.1.78

# Download SadTalker checkpoints
RUN bash scripts/download_models.sh

# Copy handler
COPY handler.py /handler.py

WORKDIR /
CMD ["python", "-u", "handler.py"]