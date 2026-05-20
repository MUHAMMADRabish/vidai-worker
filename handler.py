import runpod
import base64
import os
import uuid
import subprocess
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

    script           = job_input.get("script", "")
    photo_b64        = job_input.get("photo_base64", "")
    voice_id         = job_input.get("voice_id", "en-us-female")
    voice_sample_url = job_input.get("voice_sample_url", "")
    job_id           = job_input.get("job_id", str(uuid.uuid4()))

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

        # ── Step 2: Generate audio ───────────────────────────────
        if voice_sample_url:
            # XTTS v2 voice cloning
            audio_path = f"{work_dir}/audio.wav"
            voice_sample_path = f"{work_dir}/voice_sample.wav"

            urllib.request.urlretrieve(voice_sample_url, voice_sample_path)
            print(f"✅ Voice sample downloaded: {voice_sample_path}")

            xtts_lang_map = {
                "en": "en", "es": "es", "fr": "fr", "de": "de",
                "ar": "ar", "hi": "hi", "zh": "zh-cn", "ja": "ja",
                "pt": "pt", "it": "it",
            }
            lang = xtts_lang_map.get(voice_id.split("-")[0], "en")

            from TTS.api import TTS as CoquiTTS
            tts_model = CoquiTTS("tts_models/multilingual/multi-dataset/xtts_v2")
            tts_model.tts_to_file(
                text=script,
                speaker_wav=voice_sample_path,
                language=lang,
                file_path=audio_path
            )
            print(f"✅ Audio generated with XTTS v2: {audio_path}")
        else:
            # edge-tts fallback
            audio_path = f"{work_dir}/audio.mp3"

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
            print(f"✅ Audio generated with edge-tts: {audio_path}")

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