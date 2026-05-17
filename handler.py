import runpod
import base64
import os
import uuid
import subprocess
from pathlib import Path
from gtts import gTTS
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

def upload_to_r2(file_path: str, key: str) -> str:
    with open(file_path, "rb") as f:
        file_data = f.read()
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=file_data,
        ContentType="video/mp4"
    )
    return f"{os.environ['R2_PUBLIC_URL']}/{key}"

# ── Main handler ─────────────────────────────────────────────────
def handler(job):
    job_input = job["input"]

    script    = job_input.get("script", "")
    photo_b64 = job_input.get("photo_base64", "")
    voice_id  = job_input.get("voice_id", "en-us-female")
    job_id    = job_input.get("job_id", str(uuid.uuid4()))

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

        # Save using PIL to ensure valid image format
        img = Image.open(io.BytesIO(photo_data))
        img = img.convert("RGB")

        # Resize if too large for SadTalker
        if img.width > 512 or img.height > 512:
            img.thumbnail((512, 512), Image.LANCZOS)

        img.save(photo_path, "PNG")
        print(f"✅ Photo saved: {photo_path} size: {img.size}")

        # ── Step 2: Generate audio with gTTS ────────────────────
        audio_path = f"{work_dir}/audio.mp3"

        lang = "en"
        if "es" in voice_id:   lang = "es"
        elif "fr" in voice_id: lang = "fr"
        elif "de" in voice_id: lang = "de"
        elif "hi" in voice_id: lang = "hi"
        elif "pt" in voice_id: lang = "pt"
        elif "it" in voice_id: lang = "it"
        elif "ja" in voice_id: lang = "ja"
        elif "ko" in voice_id: lang = "ko"
        elif "zh" in voice_id: lang = "zh"
        elif "ar" in voice_id: lang = "ar"

        tts = gTTS(text=script, lang=lang, slow=False)
        tts.save(audio_path)
        print(f"✅ Audio generated: {audio_path}")

        # ── Step 3: Generate video with SadTalker ────────────────
        output_dir = f"{work_dir}/output"
        os.makedirs(output_dir, exist_ok=True)

        sadtalker_cmd = [
            "python", "/SadTalker/inference.py",
            "--driven_audio", audio_path,
            "--source_image", photo_path,
            "--result_dir", output_dir,
            "--still",
            "--preprocess", "full",
            "--size", "256",
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

        print(f"✅ Video generated")

        # ── Step 4: Find output video ────────────────────────────
        video_files = list(Path(output_dir).glob("*.mp4"))
        if not video_files:
            raise Exception("No video file generated")
        video_path = str(video_files[0])
        print(f"✅ Video found: {video_path}")

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