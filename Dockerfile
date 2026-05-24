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

# Download all MuseTalk models (unet, face-parse-bisent, whisper, configs)
RUN huggingface-cli download TMElyralab/MuseTalk \
    --local-dir /MuseTalk/models \
    --local-dir-use-symlinks False

# Download sd-vae model
RUN huggingface-cli download stabilityai/sd-vae-ft-mse \
    --local-dir /MuseTalk/models/sd-vae \
    --local-dir-use-symlinks False

# Download dwpose models (pose estimator + person detector)
RUN huggingface-cli download yzd-v/DWPose \
    --local-dir /MuseTalk/models/dwpose \
    --local-dir-use-symlinks False

# Download whisper model
RUN huggingface-cli download openai/whisper-tiny \
    --local-dir /MuseTalk/models/whisper \
    --local-dir-use-symlinks False

# Download face-parse-bisent models
RUN mkdir -p /MuseTalk/models/face-parse-bisent

# 79999_iter.pth — try Google Drive first, fall back to jonathandinu/face-parsing on HF
RUN wget -q --tries=3 -O /MuseTalk/models/face-parse-bisent/79999_iter.pth \
    "https://drive.google.com/uc?id=154JgKpzCPW82qINcVieuPH3fZ2e0P812" || \
    huggingface-cli download jonathandinu/face-parsing \
    79999_iter.pth \
    --local-dir /MuseTalk/models/face-parse-bisent \
    --local-dir-use-symlinks False

# resnet18-5c106cde.pth — standard PyTorch pretrained backbone from pytorch.org
RUN wget -q --tries=3 -O /MuseTalk/models/face-parse-bisent/resnet18-5c106cde.pth \
    "https://download.pytorch.org/models/resnet18-5c106cde.pth"

# Verify face-parse-bisent contents
RUN ls -la /MuseTalk/models/face-parse-bisent/

# Verify all model directories are present
RUN ls -la /MuseTalk/models/

# Show inference config to confirm expected model paths
RUN cat /MuseTalk/configs/inference/default.yaml 2>/dev/null || \
    find /MuseTalk -name "*.yaml" | head -5 | xargs cat

COPY handler.py /handler.py
WORKDIR /
CMD ["python", "-u", "/handler.py"]
