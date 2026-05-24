FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

ENV TORCH_CUDA_ARCH_LIST="6.0 6.1 7.0 7.5 8.0 8.6 8.9 9.0 12.0"

RUN apt-get update -y && apt-get install -y ffmpeg libsndfile1 git wget && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir runpod boto3 edge-tts Pillow nest_asyncio

RUN git clone https://github.com/bytedance/LatentSync.git /LatentSync
WORKDIR /LatentSync
RUN pip install --no-cache-dir -r requirements.txt

RUN huggingface-cli download chunyu-li/LatentSync \
    --local-dir /LatentSync/checkpoints \
    --local-dir-use-symlinks False

COPY handler.py /handler.py
WORKDIR /
CMD ["python", "-u", "/handler.py"]
