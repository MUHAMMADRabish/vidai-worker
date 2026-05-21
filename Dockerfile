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

# Patch SadTalker to use modern numpy aliases (np.float/int/complex/bool removed in 1.24+)
RUN find /SadTalker -name "*.py" -exec sed -i 's/np\.float\b/np.float64/g' {} \;
RUN find /SadTalker -name "*.py" -exec sed -i 's/np\.int\b/np.int64/g' {} \;
RUN find /SadTalker -name "*.py" -exec sed -i 's/np\.complex\b/np.complex128/g' {} \;
RUN find /SadTalker -name "*.py" -exec sed -i 's/np\.bool\b/np.bool_/g' {} \;

# Fix inhomogeneous array shape error in preprocess.py (numpy 1.26 stricter about mixed types)
RUN sed -i 's/trans_params = np\.array(\[w0, h0, s, t\[0\], t\[1\]\])/trans_params = np.array([w0, h0, s, float(t[0]), float(t[1])])/g' /SadTalker/src/face3d/util/preprocess.py
RUN find /SadTalker -name "*.py" -exec sed -i 's/np\.array(\[w0, h0, s, t\[0\], t\[1\]\])/np.array([w0, h0, s, float(t[0]), float(t[1])])/g' {} \;

# Pin compatible versions after all deps are installed
RUN pip install --no-cache-dir --force-reinstall imageio==2.31.1 imageio-ffmpeg==0.4.9
RUN pip uninstall -y opencv-python opencv-python-headless opencv-contrib-python 2>/dev/null || true
RUN pip uninstall -y numpy 2>/dev/null || true
RUN pip install --no-cache-dir numpy==1.26.4
RUN pip install --no-cache-dir opencv-python-headless==4.8.1.78

# Download SadTalker checkpoints
RUN bash scripts/download_models.sh

# Copy handler
COPY handler.py /handler.py

WORKDIR /
CMD ["python", "-u", "handler.py"]