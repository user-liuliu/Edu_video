from typing import Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator


# 模型有时会使用更具体的视觉名称，但渲染层只支持这五个稳定类别。
VISUAL_KIND_ALIASES = {
    '对比图': '学科示意图',
    '动画示意图': '学科示意图',
    '电路图': '学科示意图',
    '示意图': '学科示意图',
    '流程图': '学科示意图',
    '实验示意图': '学科示意图',
}


def normalize_outline_visual_kinds(data: dict) -> dict:
    """将模型常见的视觉类型别名收敛到渲染层的固定类别。"""
    segments = data.get('segments') if isinstance(data, dict) else None
    if not isinstance(segments, list):
        return data
    for segment in segments:
        visuals = segment.get('visuals') if isinstance(segment, dict) else None
        if not isinstance(visuals, list):
            continue
        for visual in visuals:
            if not isinstance(visual, dict) or not isinstance(visual.get('kind'), str):
                continue
            kind = visual['kind'].strip()
            visual['kind'] = VISUAL_KIND_ALIASES.get(kind, kind)
    return data

class Visual(BaseModel):
    kind: Literal['插图','数学图形','公式','学科示意图','文字卡']
    description: str = Field(min_length=1,max_length=2000)

class OutlineSegment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    position: int = Field(default=0,ge=0)
    title: str = Field(min_length=1,max_length=200)
    objective: str = Field(min_length=1,max_length=2000)
    narration: str = Field(min_length=1,max_length=12000)
    visuals: list[Visual] = Field(min_length=1,max_length=12)
    evidence_ids: list[UUID] = Field(default_factory=list,max_length=30)
    content_kind: Literal['knowledge','fact','reenactment'] = 'knowledge'
    review_notes: list[str] = Field(default_factory=list,max_length=30)
    review_passed: bool | None = None
    review_issues: list[str] = Field(default_factory=list,max_length=30)
    estimated_duration_seconds: int = Field(default=1,ge=1,le=7200)
    content_revision: int = Field(default=1,ge=1)
    reviewed_revision: int = Field(default=0,ge=0)

class OutlineData(BaseModel):
    segments: list[OutlineSegment] = Field(min_length=1,max_length=100)
    @model_validator(mode='after')
    def unique_ids(self):
        if len({s.id for s in self.segments}) != len(self.segments): raise ValueError('段落 ID 不能重复')
        return self

class RevisionBody(BaseModel):
    revision: int = Field(ge=1)

class OutlineSave(OutlineData,RevisionBody): pass

class JobRequest(RevisionBody):
    idempotency_key: str = Field(min_length=1,max_length=128)
    form_version: str | None = None
    segment_ids: list[UUID] = Field(default_factory=list,max_length=100)
    instruction: str = Field(default='',max_length=2000)

class OutlineView(BaseModel):
    project_id: UUID
    title: str
    revision: int
    status: str
    segments: list[OutlineSegment]
    job_id: UUID | None = None
    needs_regeneration: bool = False
    needs_save: bool = True
    material_warnings: list[dict[str,str]] = Field(default_factory=list)
