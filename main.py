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
import time
from collections import defaultdict, deque

import edge_tts
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

PROXY_SECRET = os.environ.get("PROXY_SECRET", "").strip()
ALLOWED_MODELS = {
    "@cf/meta/llama-4-scout-17b-16e-instruct",
    "@cf/meta/llama-3.1-8b-instruct-fast",
    "@cf/black-forest-labs/flux-1-schnell",
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
        # Only the intended Persian male voice is accepted in the public no-secret mode.
        if voice != "fa-IR-FaridNeural":
            voice = "fa-IR-FaridNeural"
        communicate = edge_tts.Communicate(
            text,
            voice=voice,
            output_format="ogg-24khz-16bit-mono-opus",
        )
        audio = bytearray()
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio":
                audio.extend(chunk.get("data", b""))
        if not audio:
            raise HTTPException(502, "TTS returned no audio")
        return JSONResponse({"success": True, "audio": base64.b64encode(bytes(audio)).decode("ascii")})
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(502, f"TTS error: {str(error)[:180]}")


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
    if model == "@cf/openai/whisper-large-v3-turbo" and not str(payload.get("audio", "")).strip():
        raise HTTPException(400, "Audio is required")
    _rate_allowed(account_id)

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            upstream = await client.post(
                f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}",
                headers={
                    "Authorization": f"Bearer {api_token}",
                    "Content-Type": "application/json",
                },
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
