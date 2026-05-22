FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

# Install system dependencies
RUN apt-get update && apt-get install -y ffmpeg libsndfile1 wget git && rm -rf /var/lib/apt/lists/*

# Install miniconda
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /miniconda.sh && \
    bash /miniconda.sh -b -p /opt/conda && \
    rm /miniconda.sh
ENV PATH="/opt/conda/bin:$PATH"

# Initialize conda and switch to login shell so conda is available
RUN /opt/conda/bin/conda init bash
SHELL ["/bin/bash", "--login", "-c"]

# Create conda env with Python 3.10 exactly as MuseTalk README specifies
RUN /opt/conda/bin/conda create -n musetalk python=3.10 -y

# Install torch in conda env (cu118 wheels matched to MuseTalk requirements)
RUN /opt/conda/bin/conda run -n musetalk pip install \
    torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 \
    --index-url https://download.pytorch.org/whl/cu118

# Clone MuseTalk
RUN git clone https://github.com/TMElyralab/MuseTalk.git /MuseTalk
WORKDIR /MuseTalk

# Install MuseTalk requirements in conda env
RUN /opt/conda/bin/conda run -n musetalk pip install -r requirements.txt

# Install mmlab packages in conda env
RUN /opt/conda/bin/conda run -n musetalk pip install openmim && \
    /opt/conda/bin/conda run -n musetalk mim install mmengine && \
    /opt/conda/bin/conda run -n musetalk mim install "mmcv>=2.0.1" && \
    /opt/conda/bin/conda run -n musetalk mim install "mmdet>=3.1.0" && \
    /opt/conda/bin/conda run -n musetalk mim install "mmpose>=1.1.0"

# Download MuseTalk pretrained models from HuggingFace
RUN /opt/conda/bin/conda run -n musetalk pip install huggingface_hub && \
    /opt/conda/bin/conda run -n musetalk huggingface-cli download TMElyralab/MuseTalk --local-dir /MuseTalk/models

# Install runpod and handler dependencies in conda env
RUN /opt/conda/bin/conda run -n musetalk pip install runpod boto3 edge-tts Pillow nest_asyncio

COPY handler.py /handler.py

WORKDIR /
CMD ["/opt/conda/bin/conda", "run", "--no-capture-output", "-n", "musetalk", "python", "-u", "/handler.py"]
