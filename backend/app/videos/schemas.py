from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.jobs.service import JobView


class VideoRequest(BaseModel):
    revision: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=128, pattern=r'\S')
    retry_version_id: UUID | None = None


class VisualRevisionRequest(VideoRequest):
    mode: Literal['visual','voice'] = 'visual'
    segment_ids: list[UUID] = Field(min_length=1, max_length=1000)
    instruction: str = Field(min_length=1, max_length=2000, pattern=r'\S')


class SegmentView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    outline_segment_id: UUID
    position: int
    title: str
    narration: str
    start: float | None
    end: float | None
    media_url: str | None = None
    html_url: str | None = None
    audio_url: str | None = None


class VersionView(BaseModel):
    id: UUID
    project_id: UUID
    number: int
    outline_revision: int
    source_version_id: UUID | None
    status: Literal['queued', 'running', 'preview_ready', 'succeeded', 'failed']
    workflow: str = 'html-preview-1'
    aspect_ratio: str = '16:9'
    export_status: str | None = None
    export_job: JobView | None = None
    duration: float | None
    target_duration: float | None = None
    duration_notice: str | None = None
    created_at: datetime
    style: dict
    job: JobView
    segments: list[SegmentView]
    media_url: str | None = None
    playback_mode: str = 'whole_html'
    html_url: str | None = None
    audio_url: str | None = None


class ExportRequest(BaseModel):
    idempotency_key: str = Field(min_length=1,max_length=128,pattern=r'\S')
