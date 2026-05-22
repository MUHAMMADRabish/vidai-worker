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

# Install MuseTalk dependencies
# Skip torch/torchvision/torchaudio — base image already provides PyTorch 2.4.0 + CUDA 12.4
# Skip tensorflow — not required for inference, and conflicts with CUDA 12.4
RUN pip install --no-cache-dir \
    diffusers==0.30.2 \
    accelerate==0.28.0 \
    soundfile==0.12.1 \
    transformers==4.39.2 \
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

# Upgrade transformers to a version that natively supports huggingface-hub 1.x
RUN pip install --no-cache-dir --force-reinstall "transformers>=4.40.0"

# Patch versions.py in all known Python package locations
RUN for dir in /usr/local/lib /usr/lib /opt /root; do \
      find "$dir" -path "*/transformers/utils/versions.py" 2>/dev/null \
        -exec sed -i 's/huggingface-hub>=0.19.3,<1.0/huggingface-hub>=0.19.3/g' {} \; ; \
    done || true

# Verify both packages are importable and print their versions
RUN python -c "import transformers; print('transformers version:', transformers.__version__)" || true
RUN python -c "import huggingface_hub; print('huggingface_hub version:', huggingface_hub.__version__)" || true

# Pin numpy to MuseTalk's required version (must come after all other installs)
RUN pip install --no-cache-dir --force-reinstall numpy==1.23.5

COPY handler.py /handler.py

WORKDIR /
CMD ["python", "-u", "handler.py"]
