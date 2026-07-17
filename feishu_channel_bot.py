import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from lark_oapi.channel import FeishuChannel, InboundMessage


def load_env_file(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()


class Settings:
    feishu_app_id = os.getenv("FEISHU_APP_ID", "").strip()
    feishu_app_secret = os.getenv("FEISHU_APP_SECRET", "").strip()
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    openai_model = os.getenv("OPENAI_MODEL", "").strip() or "gpt-4.1-mini"
    bot_system_prompt = os.getenv(
        "BOT_SYSTEM_PROMPT",
        "你是一个中文助手，回答简洁、准确、友好。",
    ).strip()
    memory_turns = int(os.getenv("MEMORY_TURNS", "12"))


settings = Settings()
memory_store: Dict[str, List[Dict[str, str]]] = {}


def require_settings() -> None:
    missing = []
    if not settings.feishu_app_id:
        missing.append("FEISHU_APP_ID")
    if not settings.feishu_app_secret:
        missing.append("FEISHU_APP_SECRET")
    if not settings.openai_api_key:
        missing.append("OPENAI_API_KEY")
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")


def trim_memory(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    max_items = max(settings.memory_turns * 2, 2)
    return items[-max_items:]


def sanitize_text(msg: InboundMessage) -> str:
    text = (msg.content_text or "").strip()
    for mention in msg.mentions or []:
        if mention.name:
            text = text.replace(f"@{mention.name}", "").strip()
        if mention.key:
            text = text.replace(mention.key, "").strip()
    return text


def should_reply(msg: InboundMessage) -> bool:
    if msg.chat_type == "p2p":
        return True
    return bool(msg.mentioned_bot)


def build_openai_input(session_id: str, user_text: str) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": settings.bot_system_prompt},
    ]
    messages.extend(memory_store.get(session_id, []))
    messages.append({"role": "user", "content": user_text})
    return messages


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
    body = json.dumps(
        {"model": settings.openai_model, "input": messages},
        ensure_ascii=False,
    ).encode("utf-8")
    req = Request(
        "https://api.openai.com/v1/responses",
        data=body,
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=60) as resp:
            payload = resp.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"OpenAI API error: {detail}") from exc

    data = json.loads(payload)
    text = extract_openai_text(data)
    if not text:
        raise RuntimeError(f"Empty OpenAI response: {payload[:500]}")
    return text


async def main() -> None:
    require_settings()
    channel = FeishuChannel(
        app_id=settings.feishu_app_id,
        app_secret=settings.feishu_app_secret,
    )

    async def on_message(msg: InboundMessage) -> None:
        if not should_reply(msg):
            return

        user_text = sanitize_text(msg)
        if not user_text:
            if msg.chat_type != "p2p":
                return
            user_text = "你好"

        session_id = msg.chat_id
        messages = build_openai_input(session_id, user_text)
        try:
            reply = await asyncio.to_thread(call_openai, messages)
        except Exception as exc:
            reply = f"处理消息时出错：{exc}"

        history = memory_store.setdefault(session_id, [])
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": reply})
        memory_store[session_id] = trim_memory(history)

        await channel.send(msg.chat_id, {"text": reply})

    channel.on("message", on_message)
    print("Feishu long-connection bot is starting...")
    await channel.connect()


if __name__ == "__main__":
    asyncio.run(main())
