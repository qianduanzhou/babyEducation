import json
import os

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import Base, engine, get_db, migrate_database
from .illustrations import (
    ImageRuntimeConfig,
    generate_story_illustrations_task,
    remove_story_illustrations,
    split_story_chapters,
)
from .llm import LLMRuntimeConfig, generate_story, generate_story_topics
from .models import AIConfig, Story, StoryIllustration, User
from .schemas import (
    AIConfigRead,
    AIConfigUpdate,
    AuthResponse,
    StoryCreate,
    StoryRead,
    StorySummary,
    StoryTopicsRead,
    UserCreate,
)
from .security import create_access_token, get_current_user, hash_password, verify_password


settings = get_settings()
Base.metadata.create_all(bind=engine)
migrate_database()
os.makedirs(settings.generated_images_dir, exist_ok=True)

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/api/media", StaticFiles(directory=settings.generated_images_dir), name="generated-images")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def default_ai_config() -> AIConfigRead:
    return AIConfigRead(
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        image_base_url="",
        image_model="gpt-image-2",
        image_headers="{}",
        headers="{}",
        extra_prompt="",
        has_api_key=False,
        has_image_api_key=False,
    )


def read_ai_config(config: AIConfig | None) -> AIConfigRead:
    if not config:
        return default_ai_config()
    return AIConfigRead(
        base_url=config.base_url,
        model=config.model,
        image_base_url=config.image_base_url,
        image_model=config.image_model,
        image_headers=config.image_headers,
        headers=config.headers,
        extra_prompt=config.extra_prompt,
        has_api_key=bool(config.api_key),
        has_image_api_key=bool(config.image_api_key),
    )


def runtime_ai_config(config: AIConfig | None) -> LLMRuntimeConfig:
    if not config:
        defaults = default_ai_config()
        return LLMRuntimeConfig(
            base_url=defaults.base_url,
            api_key="",
            model=defaults.model,
            headers=defaults.headers,
            extra_prompt=defaults.extra_prompt,
        )
    return LLMRuntimeConfig(
        base_url=config.base_url,
        api_key=config.api_key,
        model=config.model,
        headers=config.headers,
        extra_prompt=config.extra_prompt,
    )


def runtime_image_config(config: AIConfig) -> ImageRuntimeConfig:
    return ImageRuntimeConfig(
        base_url=config.image_base_url,
        api_key=config.image_api_key,
        model=config.image_model,
        headers=config.image_headers,
    )


def is_image_configured(config: AIConfig | None) -> bool:
    return bool(config and config.image_base_url.strip() and config.image_api_key.strip() and config.image_model.strip())


def model_error_message(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code == 502:
            return "故事生成失败：模型服务网关返回 502，通常是中转服务或上游模型服务暂时不可用，请稍后重试，或检查 AI 配置里的 Base URL、模型名称和 API Key。"
        if status_code == 401:
            return "故事生成失败：模型服务鉴权失败，请检查 API Key。"
        if status_code == 404:
            return "故事生成失败：模型接口不存在，请检查 Base URL 和模型名称。"
        if status_code == 429:
            return "故事生成失败：模型服务请求过多或额度不足，请稍后重试。"
        return f"故事生成失败：模型服务返回 HTTP {status_code}。"
    if isinstance(exc, httpx.TimeoutException):
        return "故事生成失败：模型服务响应超时，请稍后重试。"
    if isinstance(exc, httpx.RequestError):
        return "故事生成失败：无法连接模型服务，请检查 Base URL 或网络。"
    return f"故事生成失败：{exc}"


@app.post("/api/auth/register", response_model=AuthResponse)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> AuthResponse:
    username = payload.username.strip()
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")

    user = User(username=username, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return AuthResponse(access_token=create_access_token(user), user=user)


@app.post("/api/auth/login", response_model=AuthResponse)
def login(payload: UserCreate, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.scalar(select(User).where(User.username == payload.username.strip()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    return AuthResponse(access_token=create_access_token(user), user=user)


@app.get("/api/ai-config", response_model=AIConfigRead)
def get_ai_config(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AIConfigRead:
    config = db.scalar(select(AIConfig).where(AIConfig.user_id == user.id))
    return read_ai_config(config)


@app.put("/api/ai-config", response_model=AIConfigRead)
def save_ai_config(
    payload: AIConfigUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AIConfigRead:
    try:
        parsed_headers = json.loads(payload.headers or "{}")
        parsed_image_headers = json.loads(payload.image_headers or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="Headers 必须是合法的 JSON") from exc
    if not isinstance(parsed_headers, dict) or not isinstance(parsed_image_headers, dict):
        raise HTTPException(status_code=422, detail="Headers 必须是 JSON 对象")

    config = db.scalar(select(AIConfig).where(AIConfig.user_id == user.id))
    if not config:
        config = AIConfig(user_id=user.id)
        db.add(config)

    config.base_url = payload.base_url.strip().rstrip("/") or "https://api.openai.com/v1"
    config.model = payload.model.strip() or "gpt-4o-mini"
    config.image_base_url = payload.image_base_url.strip().rstrip("/")
    config.image_model = payload.image_model.strip() or "gpt-image-2"
    config.headers = json.dumps(parsed_headers, ensure_ascii=False)
    config.image_headers = json.dumps(parsed_image_headers, ensure_ascii=False)
    config.extra_prompt = payload.extra_prompt.strip()
    if payload.clear_api_key:
        config.api_key = ""
    elif payload.api_key is not None and payload.api_key.strip():
        config.api_key = payload.api_key.strip()
    if payload.clear_image_api_key:
        config.image_api_key = ""
    elif payload.image_api_key is not None and payload.image_api_key.strip():
        config.image_api_key = payload.image_api_key.strip()

    db.commit()
    db.refresh(config)
    return read_ai_config(config)


@app.get("/api/stories", response_model=list[StorySummary])
def list_stories(
    query: str = Query(default="", max_length=120),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Story]:
    statement = select(Story).where(Story.user_id == user.id)
    if query.strip():
        keyword = f"%{query.strip()}%"
        statement = statement.where(or_(Story.title.like(keyword), Story.topic.like(keyword)))
    statement = statement.order_by(Story.created_at.desc())
    return list(db.scalars(statement).all())


@app.get("/api/story-topics/random", response_model=StoryTopicsRead)
async def random_story_topics(
    count: int = Query(default=4, ge=2, le=6),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StoryTopicsRead:
    config = db.scalar(select(AIConfig).where(AIConfig.user_id == user.id))
    try:
        topics, source = await generate_story_topics(runtime_ai_config(config), count)
    except Exception:
        topics, source = await generate_story_topics(runtime_ai_config(None), count)
    return StoryTopicsRead(topics=topics, source=source)


@app.post("/api/stories", response_model=StoryRead)
async def create_story(
    payload: StoryCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Story:
    config = db.scalar(select(AIConfig).where(AIConfig.user_id == user.id))
    try:
        title, content = await generate_story(
            payload.topic.strip(),
            payload.language,
            payload.extra_prompt.strip(),
            runtime_ai_config(config),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=model_error_message(exc)) from exc

    story = Story(
        user_id=user.id,
        title=title,
        language=payload.language,
        topic=payload.topic.strip(),
        content=content,
    )
    db.add(story)
    db.commit()
    db.refresh(story)
    create_story_illustration_records(story, db, status="pending" if is_image_configured(config) else "unavailable")
    if is_image_configured(config):
        background_tasks.add_task(
            generate_story_illustrations_task,
            story.id,
            runtime_image_config(config),
        )
    return story


@app.get("/api/stories/{story_id}", response_model=StoryRead)
def get_story(
    story_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Story:
    story = db.scalar(select(Story).where(Story.id == story_id, Story.user_id == user.id))
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="故事不存在")
    synchronize_story_chapters(story, db, status="unavailable")
    return story


@app.post("/api/stories/{story_id}/illustrations", response_model=StoryRead)
def generate_story_illustrations(
    story_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Story:
    story = db.scalar(select(Story).where(Story.id == story_id, Story.user_id == user.id))
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="故事不存在")
    config = db.scalar(select(AIConfig).where(AIConfig.user_id == user.id))
    if not is_image_configured(config):
        raise HTTPException(status_code=422, detail="请先配置图像模型的 Base URL、API Key 和模型名称")
    if not synchronize_story_chapters(story, db):
        if not story.illustrations:
            create_story_illustration_records(story, db)
        else:
            for illustration in story.illustrations:
                illustration.status = "pending"
                illustration.image_path = None
                illustration.error = None
            db.commit()
    background_tasks.add_task(
        generate_story_illustrations_task,
        story.id,
        runtime_image_config(config),
    )
    db.refresh(story)
    return story


@app.patch("/api/stories/{story_id}/read", response_model=StoryRead)
def mark_story_read(
    story_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Story:
    story = db.scalar(select(Story).where(Story.id == story_id, Story.user_id == user.id))
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="故事不存在")
    story.is_read = True
    db.commit()
    db.refresh(story)
    return story


@app.delete("/api/stories/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_story(
    story_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    story = db.scalar(select(Story).where(Story.id == story_id, Story.user_id == user.id))
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="故事不存在")
    remove_story_illustrations(story.id)
    db.delete(story)
    db.commit()


def create_story_illustration_records(story: Story, db: Session, status: str = "pending") -> None:
    if story.illustrations:
        return
    for chapter_index, chapter_text in enumerate(split_story_chapters(story.content, language=story.language)):
        db.add(
            StoryIllustration(
                story_id=story.id,
                chapter_index=chapter_index,
                chapter_text=chapter_text,
                status=status,
            )
        )
    db.commit()
    db.refresh(story)


def synchronize_story_chapters(story: Story, db: Session, status: str = "pending") -> bool:
    chapters = split_story_chapters(story.content, language=story.language)
    stored_chapters = [illustration.chapter_text for illustration in story.illustrations]
    if stored_chapters == chapters:
        return False

    remove_story_illustrations(story.id)
    story.illustrations.clear()
    db.flush()
    create_story_illustration_records(story, db, status=status)
    return True
