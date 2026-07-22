from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=5, max_length=128)


class UserRead(BaseModel):
    id: int
    username: str

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class StoryCreate(BaseModel):
    language: str = Field(default="bilingual", pattern="^(zh|en|bilingual)$")
    topic: str = Field(min_length=1, max_length=220)
    extra_prompt: str = Field(default="", max_length=1200)


class StoryRead(BaseModel):
    id: int
    title: str
    language: str
    topic: str
    content: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class StorySummary(BaseModel):
    id: int
    title: str
    language: str
    topic: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class StoryTopicRead(BaseModel):
    topic: str
    source: str


class StoryTopicsRead(BaseModel):
    topics: list[str] = Field(min_length=2, max_length=6)
    source: str


class AIConfigRead(BaseModel):
    base_url: str
    model: str
    headers: str
    extra_prompt: str
    has_api_key: bool


class AIConfigUpdate(BaseModel):
    base_url: str = Field(default="https://api.openai.com/v1", min_length=1, max_length=500)
    api_key: str | None = Field(default=None, max_length=4096)
    model: str = Field(default="gpt-4o-mini", min_length=1, max_length=160)
    headers: str = Field(default="{}", max_length=4000)
    extra_prompt: str = Field(default="", max_length=2000)
    clear_api_key: bool = False
