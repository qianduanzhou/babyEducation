from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    stories: Mapped[list["Story"]] = relationship("Story", back_populates="owner", cascade="all, delete-orphan")
    ai_config: Mapped["AIConfig | None"] = relationship(
        "AIConfig",
        back_populates="owner",
        cascade="all, delete-orphan",
        uselist=False,
    )


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    language: Mapped[str] = mapped_column(String(24), nullable=False)
    topic: Mapped[str] = mapped_column(String(220), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    owner: Mapped[User] = relationship("User", back_populates="stories")
    illustrations: Mapped[list["StoryIllustration"]] = relationship(
        "StoryIllustration",
        back_populates="story",
        cascade="all, delete-orphan",
        order_by="StoryIllustration.chapter_index",
    )


class StoryIllustration(Base):
    __tablename__ = "story_illustrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    story_id: Mapped[int] = mapped_column(ForeignKey("stories.id"), index=True, nullable=False)
    chapter_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chapter_text: Mapped[str] = mapped_column(Text, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)

    story: Mapped[Story] = relationship("Story", back_populates="illustrations")

    @property
    def image_url(self) -> str | None:
        return f"/api/media/{self.image_path}" if self.image_path else None


class AIConfig(Base):
    __tablename__ = "ai_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True, nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), default="https://api.openai.com/v1", nullable=False)
    api_key: Mapped[str] = mapped_column(Text, default="", nullable=False)
    model: Mapped[str] = mapped_column(String(160), default="gpt-4o-mini", nullable=False)
    image_base_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    image_api_key: Mapped[str] = mapped_column(Text, default="", nullable=False)
    image_model: Mapped[str] = mapped_column(String(160), default="gpt-image-2", nullable=False)
    image_headers: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    headers: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    extra_prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    owner: Mapped[User] = relationship("User", back_populates="ai_config")
