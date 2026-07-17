"""DARKSELF Render Proxy

Stateless relay for per-member Cloudflare Workers AI credentials.
It never writes API tokens/account IDs to disk or logs request bodies.

Security note:
- PROXY_SECRET is optional because the owner requested no required secret.
- If it is set as a Render environment variable, requests must include X-Proxy-Secret.
- Leaving it empty makes this a public relay URL; use the per-account rate limit below.
"""
import base64
import hashlib
import os
import subprocess
import tempfile
import time
from collections import defaultdict, deque

import edge_tts
import httpx
import imageio_ffmpeg
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

PROXY_SECRET = os.environ.get("PROXY_SECRET", "").strip()
ALLOWED_MODELS = {
    "@cf/meta/llama-4-scout-17b-16e-instruct",
    "@cf/meta/llama-3.1-8b-instruct-fast",
    "@cf/black-forest-labs/flux-1-schnell",
    "@cf/black-forest-labs/flux-2-klein-4b",
    "@cf/openai/whisper-large-v3-turbo",
}
# Per Cloudflare account, not per source IP: all Hugging Face users may share one IP.
RATE_WINDOW_SECONDS = 60
RATE_MAX_REQUESTS = 50
_rate_buckets: dict[str, deque] = defaultdict(deque)


def _authorized(request: Request) -> bool:
    if not PROXY_SECRET:
        return True
    return request.headers.get("x-proxy-secret", "") == PROXY_SECRET


def _validate_input(data: dict):
    account_id = str(data.get("account_id", "")).strip()
    api_token = str(data.get("api_token", "")).strip()
    if api_token.lower().startswith("bearer "):
        api_token = api_token.split(" ", 1)[1].strip()
    if not (16 <= len(account_id) <= 64 and account_id.replace("-", "").replace("_", "").isalnum()):
        raise HTTPException(400, "Invalid account_id")
    if len(api_token) < 20 or any(ch.isspace() for ch in api_token):
        raise HTTPException(400, "Invalid api_token")
    return account_id, api_token


def _rate_allowed(account_id: str):
    key = hashlib.sha256(account_id.encode()).hexdigest()
    now = time.monotonic()
    bucket = _rate_buckets[key]
    while bucket and now - bucket[0] > RATE_WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= RATE_MAX_REQUESTS:
        raise HTTPException(429, "Proxy rate limit reached for this account")
    bucket.append(now)


def _safe_response(upstream: httpx.Response) -> Response:
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
        headers={"Cache-Control": "no-store"},
    )


@app.get("/")
async def root():
    return JSONResponse({"ok": True, "service": "darkself-render-proxy", "status": "running"})


@app.get("/health")
async def health():
    return JSONResponse({"ok": True, "service": "darkself-render-proxy"})


@app.post("/verify")
async def verify(request: Request):
    if not _authorized(request):
        raise HTTPException(403, "Unauthorized proxy request")
    data = await request.json()
    _account_id, api_token = _validate_input(data)
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            upstream = await client.get(
                "https://api.cloudflare.com/client/v4/user/tokens/verify",
                headers={"Authorization": f"Bearer {api_token}"},
            )
        return _safe_response(upstream)
    except httpx.TimeoutException:
        raise HTTPException(504, "Cloudflare token verification timed out")
    except httpx.HTTPError:
        raise HTTPException(502, "Could not reach Cloudflare API")


@app.post("/tts")
async def text_to_speech(request: Request):
    """Persian male TTS. Stateless and does not require member Cloudflare credentials."""
    if not _authorized(request):
        raise HTTPException(403, "Unauthorized proxy request")
    data = await request.json()
    text = str(data.get("text", "")).strip()
    if not text or len(text) > 1200:
        raise HTTPException(400, "Text must be between 1 and 1200 characters")
    try:
        voice = str(data.get("voice") or "fa-IR-FaridNeural")
        if voice not in {"fa-IR-FaridNeural", "fa-IR-DilaraNeural"}:
            voice = "fa-IR-FaridNeural"
        rate = str(data.get("rate") or "+0%")
        pitch = str(data.get("pitch") or "+0Hz")
        # edge-tts returns MP3 in this version. Convert it to OGG/Opus so Telegram
        # displays a real voice message rather than a music/audio file.
        communicate = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
        mp3_audio = bytearray()
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio":
                mp3_audio.extend(chunk.get("data", b""))
        if not mp3_audio:
            raise HTTPException(502, "TTS returned no audio")
        with tempfile.TemporaryDirectory() as temp_dir:
            source = os.path.join(temp_dir, "speech.mp3")
            target = os.path.join(temp_dir, "speech.ogg")
            with open(source, "wb") as f:
                f.write(mp3_audio)
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            converted = subprocess.run(
                [ffmpeg, "-y", "-i", source, "-c:a", "libopus", "-b:a", "32k", target],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=30,
                check=False,
            )
            if converted.returncode != 0 or not os.path.exists(target):
                raise HTTPException(502, "TTS audio conversion failed")
            with open(target, "rb") as f:
                ogg_audio = f.read()
        return JSONResponse({"success": True, "audio": base64.b64encode(ogg_audio).decode("ascii")})
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(502, f"TTS error: {str(error)[:180]}")


@app.post("/openai-image")
async def openai_image(request: Request):
    """Generate or edit one image using the caller's own OpenAI API key."""
    if not _authorized(request):
        raise HTTPException(403, "Unauthorized proxy request")
    data = await request.json()
    api_key = str(data.get("api_key", "")).strip()
    prompt = str(data.get("prompt", "")).strip()
    image_b64 = str(data.get("image_b64", "")).strip()
    image_mime = str(data.get("image_mime", "image/jpeg")).strip()
    if len(api_key) < 20 or not api_key.startswith("sk-"):
        raise HTTPException(400, "Invalid OpenAI API key")
    if not prompt or len(prompt) > 3000:
        raise HTTPException(400, "Prompt must be between 1 and 3000 characters")
    _rate_allowed(hashlib.sha256(api_key.encode()).hexdigest())
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            if image_b64:
                try:
                    image_bytes = base64.b64decode(image_b64)
                except Exception:
                    raise HTTPException(400, "Invalid image payload")
                if len(image_bytes) > 12 * 1024 * 1024:
                    raise HTTPException(400, "Image is too large")
                upstream = await client.post(
                    "https://api.openai.com/v1/images/edits",
                    headers=headers,
                    data={"model": "gpt-image-1", "prompt": prompt, "size": "1024x1024", "quality": "medium"},
                    files={"image": ("source.jpg", image_bytes, image_mime)},
                )
            else:
                upstream = await client.post(
                    "https://api.openai.com/v1/images/generations",
                    headers={**headers, "Content-Type": "application/json"},
                    json={"model": "gpt-image-1", "prompt": prompt, "size": "1024x1024", "quality": "medium", "n": 1},
                )
        return _safe_response(upstream)
    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(504, "OpenAI image request timed out")
    except httpx.HTTPError:
        raise HTTPException(502, "Could not reach OpenAI image API")


@app.post("/run")
async def run_ai(request: Request):
    if not _authorized(request):
        raise HTTPException(403, "Unauthorized proxy request")
    data = await request.json()
    account_id, api_token = _validate_input(data)
    model = str(data.get("model", ""))
    payload = data.get("payload")
    if model not in ALLOWED_MODELS:
        raise HTTPException(400, "Model is not allowed")
    if not isinstance(payload, dict):
        raise HTTPException(400, "Invalid AI payload")
    if model.startswith("@cf/meta/") and not isinstance(payload.get("messages"), list):
        raise HTTPException(400, "Invalid chat payload")
    if model == "@cf/black-forest-labs/flux-1-schnell" and not str(payload.get("prompt", "")).strip():
        raise HTTPException(400, "Image prompt is required")
    if model == "@cf/black-forest-labs/flux-2-klein-4b":
        if not str(payload.get("prompt", "")).strip() or not str(payload.get("input_image_b64", "")).strip():
            raise HTTPException(400, "Image edit prompt and input image are required")
    if model == "@cf/openai/whisper-large-v3-turbo" and not str(payload.get("audio", "")).strip():
        raise HTTPException(400, "Audio is required")
    _rate_allowed(account_id)

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            endpoint = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
            headers = {"Authorization": f"Bearer {api_token}"}
            if model == "@cf/black-forest-labs/flux-2-klein-4b":
                try:
                    source = base64.b64decode(payload["input_image_b64"])
                except Exception:
                    raise HTTPException(400, "Invalid input image")
                if len(source) > 2 * 1024 * 1024:
                    raise HTTPException(400, "Input image is too large")
                upstream = await client.post(
                    endpoint,
                    headers=headers,
                    data={"prompt": str(payload["prompt"]), "width": "1024", "height": "1024"},
                    files={"input_image_0": ("source.jpg", source, str(payload.get("input_image_mime") or "image/jpeg"))},
                )
            else:
                upstream = await client.post(
                    endpoint,
                    headers={**headers, "Content-Type": "application/json"},
                    json=payload,
                )
        return _safe_response(upstream)
    except httpx.TimeoutException:
        raise HTTPException(504, "Cloudflare AI request timed out")
    except httpx.HTTPError:
        raise HTTPException(502, "Could not reach Cloudflare AI")


# Allows Render's default `python main.py` start command to work too.
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
