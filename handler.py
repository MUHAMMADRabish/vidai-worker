import runpod
import base64
import os
import uuid
import subprocess
import boto3
from pathlib import Path

# ── Cloudflare R2 setup ──────────────────────────────────────────
s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
    aws_access_key_id=os.environ["R2_ACCESS_KEY"],
    aws_secret_access_key=os.environ["R2_SECRET_KEY"],
)
BUCKET = os.environ["R2_BUCKET_NAME"]

def upload_to_r2(file_path: str, key: str) -> str:
    s3.upload_file(file_path, BUCKET, key, ExtraArgs={"ContentType": "video/mp4"})
    return f"https://{os.environ['R2_PUBLIC_URL']}/{key}"

# ── Main handler ─────────────────────────────────────────────────
def handler(job):
    job_input = job["input"]
    
    script     = job_input.get("script", "")
    photo_b64  = job_input.get("photo_base64", "")
    voice_id   = job_input.get("voice_id", "en-us-female")
    job_id     = job_input.get("job_id", str(uuid.uuid4()))

    work_dir = f"/tmp/{job_id}"
    os.makedirs(work_dir, exist_ok=True)

    try:
        # ── Step 1: Save photo ───────────────────────────────────
        photo_path = f"{work_dir}/photo.jpg"
        with open(photo_path, "wb") as f:
            f.write(base64.b64decode(photo_b64))
        print(f"✅ Photo saved: {photo_path}")

        # ── Step 2: Generate audio with Coqui TTS ───────────────
        audio_path = f"{work_dir}/audio.wav"
        lang = "en"
        if "es" in voice_id:   lang = "es"
        elif "fr" in voice_id: lang = "fr"
        elif "de" in voice_id: lang = "de"
        elif "hi" in voice_id: lang = "hi"

        tts_cmd = [
            "tts",
            "--text", script,
            "--model_name", "tts_models/multilingual/multi-dataset/xtts_v2",
            "--language_idx", lang,
            "--out_path", audio_path,
        ]
        subprocess.run(tts_cmd, check=True)
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
            "--enhancer", "gfpgan",
        ]
        subprocess.run(sadtalker_cmd, check=True, cwd="/SadTalker")
        print(f"✅ Video generated")

        # ── Step 4: Find output video ────────────────────────────
        video_files = list(Path(output_dir).glob("*.mp4"))
        if not video_files:
            raise Exception("No video file generated")
        video_path = str(video_files[0])

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
        # Cleanup temp files
        import shutil
        shutil.rmtree(work_dir, ignore_errors=True)

runpod.serverless.start({"handler": handler}) 
