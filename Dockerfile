FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

ENV TORCH_CUDA_ARCH_LIST="6.0 6.1 7.0 7.5 8.0 8.6 8.9 9.0 12.0"

# Install system dependencies (libsndfile1 required by soundfile/librosa)
RUN apt-get update -y && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    libsndfile1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install core runpod packages
RUN pip install --no-cache-dir runpod boto3 nest_asyncio edge-tts Pillow

# Clone MuseTalk
RUN git clone https://github.com/TMElyralab/MuseTalk.git /MuseTalk
WORKDIR /MuseTalk

# Pre-pin HuggingFace packages before MuseTalk requirements can override them
RUN pip install --no-cache-dir "huggingface-hub==0.23.0" "transformers==4.40.0"

# Install MuseTalk dependencies
# Skip torch/torchvision/torchaudio — base image already provides PyTorch 2.4.0 + CUDA 12.4
# Skip tensorflow — not required for inference, and conflicts with CUDA 12.4
RUN pip install --no-cache-dir \
    diffusers==0.30.2 \
    accelerate==0.28.0 \
    soundfile==0.12.1 \
    transformers==4.39.2 \
    "huggingface_hub==0.30.2" \
    librosa==0.11.0 \
    einops==0.8.1 \
    gdown \
    omegaconf \
    ffmpeg-python \
    moviepy \
    "imageio[ffmpeg]"

# Install OpenMIM then MMlab ecosystem
# Use cu121 prebuilt wheels — compatible with CUDA 12.4 via CUDA backward compatibility
RUN pip install --no-cache-dir openmim
RUN mim install mmengine
RUN pip install --no-cache-dir mmcv==2.1.0 \
    -f https://download.openmmlab.com/mmcv/dist/cu121/torch2.4/index.html
RUN mim install "mmdet==3.1.0" "mmpose==1.1.0"

# Download MuseTalk pretrained models (unet, whisper, sd-vae, dwpose, face-parse)
RUN bash download_weights.sh

# Force exact HuggingFace versions last so they win over everything
RUN pip install --no-cache-dir --force-reinstall "huggingface-hub==0.23.0"
RUN pip install --no-cache-dir --force-reinstall "transformers==4.40.0"
RUN pip install --no-cache-dir --force-reinstall "accelerate==0.29.0"

# Pin numpy to MuseTalk's required version (must come after all other installs)
RUN pip install --no-cache-dir --force-reinstall numpy==1.23.5

COPY handler.py /handler.py

WORKDIR /
CMD ["python", "-u", "handler.py"]
