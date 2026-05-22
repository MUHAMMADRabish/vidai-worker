FROM runpod/pytorch:2.0.1-py3.10-cuda11.8.0-devel-ubuntu22.04

# System deps
RUN apt-get update -y && apt-get install -y ffmpeg libsndfile1 git wget && rm -rf /var/lib/apt/lists/*

# Install handler + MuseTalk Python deps
RUN pip install --no-cache-dir \
    runpod boto3 edge-tts Pillow nest_asyncio \
    diffusers==0.27.2 \
    accelerate \
    transformers \
    huggingface_hub \
    openmim \
    librosa \
    python_speech_features \
    gdown

# Install mmlab ecosystem
RUN mim install mmengine
RUN mim install "mmcv>=2.0.1"
RUN mim install "mmdet>=3.1.0"
RUN mim install "mmpose>=1.1.0"

# Clone MuseTalk and install its requirements
RUN git clone https://github.com/TMElyralab/MuseTalk.git /MuseTalk
WORKDIR /MuseTalk
RUN pip install --no-cache-dir -r requirements.txt

# Download MuseTalk pretrained models
RUN huggingface-cli download TMElyralab/MuseTalk --local-dir /MuseTalk/models

COPY handler.py /handler.py
WORKDIR /
CMD ["python", "-u", "/handler.py"]
