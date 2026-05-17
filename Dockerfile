FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages with timeout increase
RUN pip install --no-cache-dir --timeout=300 \
    runpod \
    boto3 \
    opencv-python-headless \
    imageio \
    imageio-ffmpeg \
    scipy \
    face-alignment

# Install TTS separately with longer timeout
RUN pip install --no-cache-dir --timeout=600 TTS

# Install SadTalker
RUN git clone https://github.com/OpenTalker/SadTalker.git /SadTalker
WORKDIR /SadTalker
RUN pip install --no-cache-dir --timeout=300 -r requirements.txt

# Download SadTalker checkpoints
RUN bash scripts/download_models.sh

# Pre-download XTTS model
RUN python -c "from TTS.api import TTS; TTS('tts_models/multilingual/multi-dataset/xtts_v2')"

# Copy handler
COPY handler.py /handler.py

WORKDIR /
CMD ["python", "-u", "handler.py"]