import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from fastapi import FastAPI, Header, HTTPException, Request as FastAPIRequest


def load_env_file(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_env_file()


class Settings:
    feishu_app_id = os.getenv("FEISHU_APP_ID", "").strip()
    feishu_app_secret = os.getenv("FEISHU_APP_SECRET", "").strip()
    feishu_verification_token = os.getenv("FEISHU_VERIFICATION_TOKEN", "").strip()
    feishu_encrypt_key = os.getenv("FEISHU_ENCRYPT_KEY", "").strip()
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    openai_model = os.getenv("OPENAI_MODEL", "").strip() or "gpt-4.1-mini"
    bot_system_prompt = os.getenv(
        "BOT_SYSTEM_PROMPT",
        "你是一个中文助手，回答简洁、准确、友好。",
    ).strip()
    memory_turns = int(os.getenv("MEMORY_TURNS", "12"))


settings = Settings()
app = FastAPI(title="Feishu OpenAI Bot")

_tenant_token: Dict[str, Any] = {"value": None, "expires_at": 0.0}
_conversation_memory: Dict[str, List[Dict[str, str]]] = {}


def _http_json(
    url: str,
    *,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    body = None
    request_headers = {"Content-Type": "application/json; charset=utf-8"}
    if headers:
        request_headers.update(headers)
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")

    req = Request(url, data=body, headers=request_headers, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            payload = resp.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise HTTPException(status_code=502, detail=f"Upstream error: {detail}") from exc

    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail=f"Invalid JSON from upstream: {payload[:500]}") from exc


def verify_feishu_signature(timestamp: str, nonce: str, body: bytes, signature: Optional[str]) -> bool:
    if not settings.feishu_encrypt_key:
        return True
    if not signature:
        return False
    content = timestamp.encode("utf-8") + nonce.encode("utf-8") + settings.feishu_encrypt_key.encode("utf-8") + body
    digest = hmac.new(settings.feishu_encrypt_key.encode("utf-8"), content, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


def get_tenant_access_token() -> str:
    now = time.time()
    if _tenant_token["value"] and now < _tenant_token["expires_at"]:
        return _tenant_token["value"]

    if not settings.feishu_app_id or not settings.feishu_app_secret:
        raise HTTPException(status_code=500, detail="Missing FEISHU_APP_ID or FEISHU_APP_SECRET")

    payload = {
        "app_id": settings.feishu_app_id,
        "app_secret": settings.feishu_app_secret,
    }
    data = _http_json(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        method="POST",
        data=payload,
    )
    token = data.get("tenant_access_token")
    if not token:
        raise HTTPException(status_code=502, detail=f"Failed to get Feishu token: {data}")

    expires_in = int(data.get("expire", 7200))
    _tenant_token["value"] = token
    _tenant_token["expires_at"] = now + max(expires_in - 60, 60)
    return token


def send_feishu_message(receive_id: str, text: str) -> Dict[str, Any]:
    token = get_tenant_access_token()
    return _http_json(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        method="POST",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "receive_id": receive_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        },
    )


def fetch_chat_name(chat_id: str) -> str:
    token = get_tenant_access_token()
    data = _http_json(
        f"https://open.feishu.cn/open-apis/im/v1/chats/{chat_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    return (data.get("data") or {}).get("name", "")


def should_reply(event: Dict[str, Any]) -> bool:
    message = event.get("message") or {}
    mentions = message.get("mentions") or []
    chat_type = message.get("chat_type")
    if chat_type == "p2p":
        return True
    return bool(mentions)


def parse_user_text(event: Dict[str, Any]) -> str:
    message = event.get("message") or {}
    content = message.get("content") or "{}"
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return ""
    text = (parsed.get("text") or "").strip()
    for mention in message.get("mentions") or []:
        key = mention.get("key")
        if key:
            text = text.replace(key, "").strip()
    return text


def get_memory(session_id: str) -> List[Dict[str, str]]:
    return _conversation_memory.setdefault(session_id, [])


def trim_memory(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    max_items = max(settings.memory_turns * 2, 2)
    return items[-max_items:]


def build_openai_input(session_id: str, user_text: str) -> List[Dict[str, Any]]:
    memory = get_memory(session_id)
    content: List[Dict[str, Any]] = [
        {"role": "system", "content": settings.bot_system_prompt},
    ]
    content.extend(memory)
    content.append({"role": "user", "content": user_text})
    return content


def extract_openai_text(data: Dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str) and data["output_text"].strip():
        return data["output_text"].strip()

    parts: List[str] = []
    for item in data.get("output", []):
        for part in item.get("content", []):
            if part.get("type") == "output_text":
                text = part.get("text", "")
                if text:
                    parts.append(text)
    return "\n".join(parts).strip()


def call_openai(messages: List[Dict[str, Any]]) -> str:
    if not settings.openai_api_key:
        raise HTTPException(status_code=500, detail="Missing OPENAI_API_KEY")

    data = _http_json(
        "https://api.openai.com/v1/responses",
        method="POST",
        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        data={
            "model": settings.openai_model,
            "input": messages,
        },
    )
    text = extract_openai_text(data)
    if not text:
        raise HTTPException(status_code=502, detail=f"Empty response from OpenAI: {data}")
    return text


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook/feishu")
async def feishu_webhook(
    request: FastAPIRequest,
    x_lark_request_timestamp: Optional[str] = Header(default=None),
    x_lark_request_nonce: Optional[str] = Header(default=None),
    x_lark_signature: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    body = await request.body()
    if not verify_feishu_signature(
        x_lark_request_timestamp or "",
        x_lark_request_nonce or "",
        body,
        x_lark_signature,
    ):
        raise HTTPException(status_code=401, detail="Invalid Feishu signature")

    payload = await request.json()

    if payload.get("type") == "url_verification":
        if settings.feishu_verification_token and payload.get("token") != settings.feishu_verification_token:
            raise HTTPException(status_code=401, detail="Invalid verification token")
        return {"challenge": payload.get("challenge")}

    header = payload.get("header") or {}
    event = payload.get("event") or {}
    if header.get("event_type") != "im.message.receive_v1":
        return {"ok": True}

    if settings.feishu_verification_token and payload.get("token") != settings.feishu_verification_token:
        raise HTTPException(status_code=401, detail="Invalid verification token")

    if not should_reply(event):
        return {"ok": True}

    user_text = parse_user_text(event)
    if not user_text:
        return {"ok": True}

    message = event.get("message") or {}
    chat_id = message.get("chat_id")
    if not chat_id:
        return {"ok": True}

    messages = build_openai_input(chat_id, user_text)
    reply = call_openai(messages)

    memory = get_memory(chat_id)
    memory.append({"role": "user", "content": user_text})
    memory.append({"role": "assistant", "content": reply})
    _conversation_memory[chat_id] = trim_memory(memory)

    send_feishu_message(chat_id, reply)
    return {"ok": True}
