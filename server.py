"""
ZIT Prompt Generator — Render Proxy Server
Проксі між клієнтом (GitHub Pages) та Groq API.
API key зберігається лише тут у змінній середовища GROQ_API_KEY.

Endpoints:
  GET  /health      — warm-up ping (викликається при старті Mini App)
  POST /proxy/groq  — проксі до api.groq.com (генерація + vision)
"""

import os
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(title="ZIT Proxy", version="1.0.0")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"

ALLOWED_ORIGINS = [
    "https://konst-andre.github.io",   # покриває обидва репо:
                                        # /zit-prompt-generator/
                                        # /zit-prompt-tg/
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=600,
)


@app.get("/health")
def health():
    """Warm-up endpoint. Mini App пінгує при відкритті — сервер не засинає."""
    return {"status": "ok", "service": "zit-proxy"}


@app.post("/proxy/groq")
async def proxy_groq(request: Request):
    """
    Проксі до Groq API.
    Клієнт надсилає тільки body (без Authorization).
    Сервер підставляє GROQ_API_KEY із .env.
    """
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")

    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Empty request body")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                GROQ_URL,
                content=body,
                headers={
                    "Content-Type":  "application/json",
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                },
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Groq API timeout")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Groq API unreachable: {str(e)}")

    try:
        data = resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail="Invalid JSON from Groq API")

    return JSONResponse(content=data, status_code=resp.status_code)
