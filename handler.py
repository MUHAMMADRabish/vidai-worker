import sys
import subprocess
sys.setrecursionlimit(10000)

# Fix numpy/cv2 before loading anything else
subprocess.run(
    [sys.executable, "-m", "pip", "install", "--force-reinstall", "--quiet", "numpy==1.26.4"],
    check=False
)

try:
    import torchvision.transforms.functional_tensor
except ModuleNotFoundError:
    import torchvision.transforms.functional as functional_tensor
    sys.modules['torchvision.transforms.functional_tensor'] = functional_tensor

import torch
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"CUDA capability: {torch.cuda.get_device_capability(0)}")

import runpod
import base64
import os
import uuid
import subprocess
import time
import urllib.request
from pathlib import Path
import boto3
from botocore.config import Config
from PIL import Image
import io

# ── Cloudflare R2 setup ──────────────────────────────────────────
s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
    aws_access_key_id=os.environ["R2_ACCESS_KEY"],
    aws_secret_access_key=os.environ["R2_SECRET_KEY"],
    region_name="auto",
    config=Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"}
    )
)
BUCKET = os.environ["R2_BUCKET_NAME"]

def list_dir_recursive(path: str):
    """Print all files in a directory and its subdirectories."""
    for root, dirs, files in os.walk(path):
        level = root.replace(path, "").count(os.sep)
        indent = "  " * level
        print(f"{indent}{os.path.basename(root)}/")
        for f in files:
            fpath = os.path.join(root, f)
            size = os.path.getsize(fpath)
            print(f"{indent}  {f}  ({size} bytes)")

def upload_to_r2(file_path: str, key: str, max_attempts: int = 3) -> str:
    file_size = os.path.getsize(file_path)
    print(f"📦 R2 upload — bucket: {BUCKET}  key: {key}  file_size: {file_size} bytes")
    if file_size == 0:
        raise Exception(f"Video file is empty (0 bytes): {file_path}")

    with open(file_path, "rb") as f:
        file_data = f.read()

    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"⬆️  R2 upload attempt {attempt}/{max_attempts} ...")
            s3.put_object(
                Bucket=BUCKET,
                Key=key,
                Body=file_data,
                ContentType="video/mp4"
            )
            public_url = f"{os.environ['R2_PUBLIC_URL']}/{key}"
            print(f"✅ R2 upload succeeded on attempt {attempt}: {public_url}")
            return public_url
        except Exception as exc:
            last_exc = exc
            print(f"⚠️  R2 upload attempt {attempt} failed: {exc}")
            if attempt < max_attempts:
                print(f"   Retrying in 5 seconds ...")
                time.sleep(5)

    raise Exception(f"R2 upload failed after {max_attempts} attempts: {last_exc}")

# ── Main handler ─────────────────────────────────────────────────
def handler(job):
    job_input = job["input"]

    script           = job_input.get("script", "")
    photo_b64        = job_input.get("photo_base64", "")
    voice_id         = job_input.get("voice_id", "en-us-female")
    voice_sample_url = job_input.get("voice_sample_url", "")
    audio_url        = job_input.get("audio_url", "")   # pre-generated audio (e.g. ElevenLabs)
    job_id           = job_input.get("job_id", str(uuid.uuid4()))

    print(f"🔧 Job {job_id} — audio_url={'[SET]' if audio_url else '[NONE]'}  voice_id={voice_id}")

    work_dir = f"/tmp/{job_id}"
    os.makedirs(work_dir, exist_ok=True)

    try:
        # ── Step 1: Save photo ───────────────────────────────────
        photo_path = f"{work_dir}/photo.png"

        # Strip data URL prefix if present
        if "," in photo_b64:
            photo_b64 = photo_b64.split(",")[1]

        # Fix base64 padding
        photo_b64 = photo_b64.strip()
        padding = 4 - len(photo_b64) % 4
        if padding != 4:
            photo_b64 += "=" * padding

        photo_data = base64.b64decode(photo_b64)

        # Save using PIL
        img = Image.open(io.BytesIO(photo_data))
        img = img.convert("RGB")

        # Keep larger size for body visibility
        # Only resize if extremely large
        if img.width > 1024 or img.height > 1024:
            img.thumbnail((1024, 1024), Image.LANCZOS)

        img.save(photo_path, "PNG")
        print(f"✅ Photo saved: {photo_path} size: {img.size}")

        # ── Step 2: Obtain audio ─────────────────────────────────
        # Use pre-generated audio (e.g. from ElevenLabs) when audio_url is
        # provided, otherwise fall back to edge-tts synthesis.
        audio_path = f"{work_dir}/audio.mp3"

        if audio_url:
            print(f"⬇️  Downloading ElevenLabs audio from: {audio_url}")
            try:
                req = urllib.request.Request(
                    audio_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; VidAI/1.0)",
                        "Accept": "*/*",
                    }
                )
                with urllib.request.urlopen(req) as response:
                    with open(audio_path, "wb") as f:
                        f.write(response.read())
            except Exception as dl_err:
                raise Exception(f"Failed to download audio_url ({audio_url}): {dl_err}")
            audio_size = os.path.getsize(audio_path)
            print(f"✅ Audio downloaded: {audio_path}  size: {audio_size} bytes")
            if audio_size == 0:
                raise Exception(f"Downloaded audio file is empty: {audio_url}")
        else:
            if voice_sample_url:
                print(f"ℹ️ voice_sample_url provided but voice cloning not yet implemented — using edge-tts voice match")

            voice_name_map = {
                "en-us-male":   "en-US-GuyNeural",
                "en-us-female": "en-US-JennyNeural",
                "en-gb-male":   "en-GB-RyanNeural",
                "en-gb-female": "en-GB-SoniaNeural",
                "en-au-male":   "en-AU-WilliamNeural",
                "en-au-female": "en-AU-NatashaNeural",
                "en-in-male":   "en-IN-PrabhatNeural",
                "en-in-female": "en-IN-NeerjaNeural",
                "es-es-male":   "es-ES-AlvaroNeural",
                "es-es-female": "es-ES-ElviraNeural",
                "es-mx-male":   "es-MX-JorgeNeural",
                "es-mx-female": "es-MX-DaliaNeural",
                "fr-fr-male":   "fr-FR-HenriNeural",
                "fr-fr-female": "fr-FR-DeniseNeural",
                "de-de-male":   "de-DE-ConradNeural",
                "de-de-female": "de-DE-KatjaNeural",
                "ar-male":      "ar-SA-HamedNeural",
                "ar-female":    "ar-SA-ZariyahNeural",
                "hi-male":      "hi-IN-MadhurNeural",
                "hi-female":    "hi-IN-SwaraNeural",
                "zh-male":      "zh-CN-YunxiNeural",
                "zh-female":    "zh-CN-XiaoxiaoNeural",
                "ja-male":      "ja-JP-KeitaNeural",
                "ja-female":    "ja-JP-NanamiNeural",
                "pt-br-male":   "pt-BR-AntonioNeural",
                "pt-br-female": "pt-BR-FranciscaNeural",
                "it-male":      "it-IT-DiegoNeural",
                "it-female":    "it-IT-ElsaNeural",
            }
            voice_name = voice_name_map.get(voice_id, "en-US-JennyNeural")

            tts_result = subprocess.run(
                ["edge-tts", "--voice", voice_name, "--text", script, "--write-media", audio_path],
                capture_output=True,
                text=True
            )
            if tts_result.returncode != 0:
                raise Exception(f"edge-tts failed: {tts_result.stderr}")
            print(f"✅ Audio generated via edge-tts: {audio_path}  size: {os.path.getsize(audio_path)} bytes")

        # ── Step 3: Generate video with SadTalker ────────────────
        output_dir = f"{work_dir}/output"
        os.makedirs(output_dir, exist_ok=True)

        sadtalker_cmd = [
            "python", "/SadTalker/inference.py",
            "--driven_audio", audio_path,
            "--source_image", photo_path,
            "--result_dir", output_dir,
            "--still",
            "--preprocess", "extfull",
            "--size", "512",
        ]

        result = subprocess.run(
            sadtalker_cmd,
            cwd="/SadTalker",
            capture_output=True,
            text=True
        )

        print(f"SadTalker stdout: {result.stdout[-1000:]}")
        print(f"SadTalker stderr: {result.stderr[-1000:]}")

        if result.returncode != 0:
            raise Exception(f"SadTalker failed: {result.stderr[-500:]}")

        print(f"✅ SadTalker process completed")

        # ── List all files produced by SadTalker ─────────────────
        print(f"📂 Contents of output_dir ({output_dir}):")
        list_dir_recursive(output_dir)

        # ── Step 4: Find output video ────────────────────────────
        # Search recursively — SadTalker sometimes writes into a dated sub-dir
        video_files = list(Path(output_dir).rglob("*.mp4"))
        print(f"🔍 MP4 files found (recursive): {[str(v) for v in video_files]}")
        if not video_files:
            raise Exception(f"No .mp4 file found anywhere under {output_dir}")
        # Prefer the largest file to avoid picking a tiny intermediate clip
        video_path = str(max(video_files, key=lambda p: p.stat().st_size))
        video_size = os.path.getsize(video_path)
        print(f"✅ Video selected: {video_path}  size: {video_size} bytes")

        # ── Step 5: Upload to Cloudflare R2 ─────────────────────
        r2_key = f"videos/{job_id}.mp4"
        video_url = upload_to_r2(video_path, r2_key)
        print(f"✅ Uploaded to R2: {video_url}")

        return {
            "status": "completed",
            "video_url": video_url,
            "job_id": job_id,
        }

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return {
            "status": "failed",
            "error": str(e),
            "job_id": job_id,
        }
    finally:
        import shutil
        shutil.rmtree(work_dir, ignore_errors=True)

runpod.serverless.start({"handler": handler})