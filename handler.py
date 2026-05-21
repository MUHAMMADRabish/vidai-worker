import sys
print("Handler starting up...")
print(f"Python version: {sys.version}")

import runpod
print("runpod imported OK")

def handler(job):
    print(f"Handler called with job: {job}")
    return {"status": "completed", "video_url": "test", "job_id": "test"}

print("Handler function defined, starting runpod serverless...")
runpod.serverless.start({"handler": handler})
