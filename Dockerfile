FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install lightweight packages first
RUN pip install --no-cache-dir \
    runpod \
    boto3 \
    gTTS \
    opencv-python-headless \
    imageio \
    imageio-ffmpeg \
    scipy \
    requests

# Install torch separately
RUN pip install --no-cache-dir \
    torch==2.1.0 \
    torchvision==0.16.0 \
    torchaudio==2.1.0 \
    --index-url https://download.pytorch.org/whl/cpu

# Install SadTalker dependencies
RUN pip install --no-cache-dir \
    face-alignment==1.3.5 \
    facexlib \
    realesrgan

# Clone SadTalker
RUN git clone https://github.com/OpenTalker/SadTalker.git /SadTalker
WORKDIR /SadTalker
RUN pip install --no-cache-dir -r requirements.txt

# Download SadTalker checkpoints
RUN bash scripts/download_models.sh

# Copy handler
COPY handler.py /handler.py

WORKDIR /
CMD ["python", "-u", "handler.py"]