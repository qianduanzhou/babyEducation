import asyncio
import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path

import httpx
from sqlalchemy import select

from .config import get_settings
from .database import SessionLocal
from .llm import parse_headers
from .models import StoryIllustration


_CJK_CHARACTER = re.compile(r"[\u4e00-\u9fff]")
_ENGLISH_WORD = re.compile(r"[A-Za-z]{3,}")


@dataclass
class ImageRuntimeConfig:
    base_url: str
    api_key: str
    model: str
    headers: str


def split_story_chapters(
    content: str,
    language: str | None = None,
) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in content.splitlines() if paragraph.strip()]
    if not paragraphs:
        return [content.strip()] if content.strip() else []

    if language != "bilingual":
        return paragraphs
    return _pair_bilingual_paragraphs(paragraphs)


def _pair_bilingual_paragraphs(paragraphs: list[str]) -> list[str]:
    """Make each Chinese plot paragraph and its following translation one chapter."""
    paragraphs = [paragraph for paragraph in paragraphs if paragraph not in {"---", "***", "___"}]

    # Some older model responses include an English translation of the title as
    # the first body paragraph. It is not a story chapter.
    if (
        len(paragraphs) >= 3
        and _is_english_paragraph(paragraphs[0])
        and _is_chinese_paragraph(paragraphs[1])
        and _is_english_paragraph(paragraphs[2])
    ):
        paragraphs = paragraphs[1:]

    chapters: list[str] = []
    pending_chinese: str | None = None
    for paragraph in paragraphs:
        if _is_chinese_paragraph(paragraph):
            if pending_chinese:
                chapters.append(pending_chinese)
            pending_chinese = paragraph
        elif _is_english_paragraph(paragraph) and pending_chinese:
            chapters.append(f"{pending_chinese}\n\n{paragraph}")
            pending_chinese = None
        else:
            if pending_chinese:
                chapters.append(pending_chinese)
                pending_chinese = None
            chapters.append(paragraph)

    if pending_chinese:
        chapters.append(pending_chinese)
    return chapters


def _is_chinese_paragraph(paragraph: str) -> bool:
    chinese_character_count = len(_CJK_CHARACTER.findall(paragraph))
    english_word_count = len(_ENGLISH_WORD.findall(paragraph))
    return chinese_character_count >= 2 and chinese_character_count >= english_word_count


def _is_english_paragraph(paragraph: str) -> bool:
    return bool(_ENGLISH_WORD.search(paragraph)) and not _CJK_CHARACTER.search(paragraph)


def build_illustration_prompt(title: str, topic: str, chapter_text: str, chapter_index: int) -> str:
    return f"""
Use case: illustration-story
Asset type: a full-bleed background for chapter {chapter_index + 1} of a prenatal and early-childhood story reader.
Story title: {title}
Story topic: {topic}
Chapter plot: {chapter_text}
Primary request: portray the specific action, setting, and emotion of this chapter, not a generic animal scene.
Style/medium: warm hand-painted children's book illustration, soft paper texture, gentle natural light, calm joyful mood, rich but restrained colors.
Composition/framing: wide landscape scene with the main action visible in the center and enough quieter space for readable text overlay.
Constraints: safe and soothing for prenatal and young-child reading; preserve character continuity with the rest of the story; no written words, letters, captions, logos, watermark, frame, frightening content, injury, weapons, or harsh conflict.
""".strip()


async def generate_illustration_image(
    config: ImageRuntimeConfig,
    prompt: str,
) -> bytes:
    if not config.api_key:
        raise ValueError("An API key is required before chapter illustrations can be generated")
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
        **parse_headers(config.headers),
    }
    payload = {
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    settings = get_settings()
    base_url = config.base_url.rstrip("/")
    if base_url.endswith("/chat/completions"):
        image_endpoint = base_url
    elif base_url.endswith("/v1"):
        image_endpoint = f"{base_url}/chat/completions"
    else:
        image_endpoint = f"{base_url}/v1/chat/completions"
    async with httpx.AsyncClient(timeout=settings.image_request_timeout_seconds) as client:
        response = await client.post(image_endpoint, headers=headers, json=payload)
        if response.is_error:
            detail = response.text.strip().replace("\n", " ")
            raise ValueError(f"Image chat request failed (HTTP {response.status_code}): {detail[:800]}")
        response.raise_for_status()
        image_reference = extract_chat_image(response.json())
        if isinstance(image_reference, bytes):
            return image_reference
        if image_reference:
            download = await client.get(image_reference)
            download.raise_for_status()
            return download.content
    raise ValueError("The image model did not return a URL or base64 image in its chat response")


def extract_chat_image(payload: dict) -> bytes | str | None:
    choices = payload.get("choices") or []
    if not choices:
        return None
    message = choices[0].get("message") or {}
    candidates = [message.get("image_url"), *(message.get("images") or []), message.get("content")]
    for candidate in candidates:
        result = extract_image_candidate(candidate)
        if result:
            return result
    return None


def extract_image_candidate(candidate: object) -> bytes | str | None:
    if isinstance(candidate, dict):
        for key in ("b64_json", "base64", "image_base64"):
            value = candidate.get(key)
            if isinstance(value, str) and value:
                return base64.b64decode(value)
        candidate = candidate.get("url") or candidate.get("image_url") or candidate.get("text")
    if isinstance(candidate, list):
        for item in candidate:
            result = extract_image_candidate(item)
            if result:
                return result
        return None
    if not isinstance(candidate, str):
        return None
    value = candidate.strip()
    if value.startswith("data:image/") and "," in value:
        return base64.b64decode(value.split(",", 1)[1])
    data_uri = re.search(r"data:image/[^;,]+;base64,([A-Za-z0-9+/=\s]+)", value)
    if data_uri:
        return base64.b64decode(re.sub(r"\s+", "", data_uri.group(1)))
    if value.startswith("```"):
        value = re.sub(r"^```(?:svg|xml)?\s*|\s*```$", "", value, flags=re.IGNORECASE).strip()
    svg_start = value.lower().find("<svg")
    if svg_start >= 0:
        return value[svg_start:].encode("utf-8")
    if value.startswith("{"):
        try:
            return extract_image_candidate(json.loads(value))
        except json.JSONDecodeError:
            return None
    match = re.search(r"https?://[^\s)\]]+", value)
    return match.group(0) if match else None


async def _generate_story_illustrations(story_id: int, config: ImageRuntimeConfig) -> None:
    settings = get_settings()
    output_root = Path(settings.generated_images_dir)
    database = SessionLocal()
    try:
        illustrations = list(database.scalars(
            select(StoryIllustration).where(StoryIllustration.story_id == story_id).order_by(StoryIllustration.chapter_index)
        ))
        for illustration in illustrations:
            illustration.status = "generating"
            illustration.error = None
            database.commit()
            try:
                prompt = build_illustration_prompt(
                    illustration.story.title,
                    illustration.story.topic,
                    illustration.chapter_text,
                    illustration.chapter_index,
                )
                illustration.prompt = prompt
                database.commit()
                image_bytes = await generate_illustration_image(config, prompt)
                extension = "svg" if image_bytes.lstrip().startswith(b"<svg") else "png"
                relative_path = Path(f"story-{story_id}") / f"chapter-{illustration.chapter_index + 1}.{extension}"
                destination = output_root / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(image_bytes)
                illustration.image_path = relative_path.as_posix()
                illustration.status = "ready"
                illustration.error = None
            except Exception as exc:
                illustration.status = "failed"
                illustration.error = str(exc)[:500]
            database.commit()
    finally:
        database.close()


def generate_story_illustrations_task(story_id: int, config: ImageRuntimeConfig) -> None:
    asyncio.run(_generate_story_illustrations(story_id, config))


def remove_story_illustrations(story_id: int) -> None:
    root = Path(get_settings().generated_images_dir) / f"story-{story_id}"
    if not root.exists():
        return
    for file_path in root.glob("*"):
        if file_path.is_file():
            file_path.unlink()
    root.rmdir()
