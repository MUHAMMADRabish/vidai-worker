FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

# Install system dependencies
RUN apt-get update -y && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install lightweight Python packages
RUN pip install --no-cache-dir \
    runpod \
    boto3 \
    edge-tts \
    TTS

# Install SadTalker
RUN git clone https://github.com/OpenTalker/SadTalker.git /SadTalker
WORKDIR /SadTalker
RUN pip install --no-cache-dir -r requirements.txt

# Download SadTalker checkpoints
RUN bash scripts/download_models.sh

# Copy handler
COPY handler.py /handler.py

WORKDIR /
CMD ["python", "-u", "handler.py"]