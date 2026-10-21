import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TitleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="Nova conversa", min_length=1, max_length=100)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value):
        if not value.strip():
            raise ValueError("Título vazio")
        return value.strip()


class SupportAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal[
        "instructor_known",
        "instructor_unknown",
        "instructor_select",
        "instructor_cancel",
        "instructor_resume",
        "card_select",
        "card_change",
    ]
    instructor_id: str | None = Field(default=None, max_length=80)
    benefit_code: str | None = Field(default=None, pattern=r"^\d{1,10}$")

    @model_validator(mode="after")
    def validate_selection(self):
        if (self.kind == "instructor_select") != bool(self.instructor_id):
            raise ValueError("O identificador deve ser enviado somente para seleção de instrutor")
        if (self.kind == "card_select") != bool(self.benefit_code):
            raise ValueError("O código é obrigatório somente na seleção de cartão")
        return self


class SendInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: uuid.UUID
    content: str | None = Field(default=None, min_length=1, max_length=4000)
    topic_id: str | None = Field(default=None, max_length=80)
    question_id: str | None = Field(default=None, max_length=120)
    action: SupportAction | None = None
    attachment_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5)

    @field_validator("content")
    @classmethod
    def clean_content(cls, value):
        if value is None:
            return value
        if not value.strip():
            raise ValueError("Mensagem vazia")
        return value.strip()


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    topic_id: str | None = None
    support_state: dict = Field(default_factory=dict)


class TopicInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_id: str | None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    role: str
    content: str
    status: str
    sources: list[dict]
    created_at: datetime
    outcome: str | None
    topic_id: str | None = None
    question_id: str | None = None


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    media_type: str
    size: int
    status: str
    message_id: uuid.UUID | None
