"""Data contract between the planner, the segment code and the film runtime.

Pure pydantic/stdlib: the renderer image imports this module without edge_tts.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.studio.words import Word

POSITION_TOLERANCE = 2.0  # px
SCALE_TOLERANCE = 0.01
ANGLE_TOLERANCE = 2.0  # degrees

Number = Annotated[float, Field(allow_inf_nan=False)]


class _Model(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ActorState(_Model):
    x: Number
    y: Number
    scale: Number = 1
    flip: bool = False
    pose: dict[str, Number] = Field(default_factory=dict)  # part name -> rotation in degrees


class Camera(_Model):
    x: Number = 640
    y: Number = 360
    zoom: Number = 1


class StageState(_Model):
    camera: Camera = Field(default_factory=Camera)
    actors: dict[str, ActorState] = Field(default_factory=dict)
    keep: list[str] = Field(default_factory=list)  # element labels kept for the next segment


class Seam(_Model):
    kind: Literal['continue', 'transition']
    transition: Literal['push', 'wipe', 'zoom', 'match', 'fade'] | None = None
    duration: Number

    @model_validator(mode='after')
    def _check_kind(self):
        if self.kind == 'continue':
            if self.transition is not None:
                raise ValueError('continue 接缝不能指定转场')
            if not 0 <= self.duration <= 0.6:
                raise ValueError('continue 接缝的时长必须在 0 到 0.6 秒之间')
        else:
            if self.transition is None:
                raise ValueError('transition 接缝必须写明转场方式')
            if not 0.3 <= self.duration <= 1.5:
                raise ValueError('transition 接缝的时长必须在 0.3 到 1.5 秒之间')
        return self


class Highlight(_Model):
    phrase: str = Field(min_length=1)
    occurrence: int = Field(default=1, ge=1)
    target: str = Field(min_length=1)  # data-edu-id in the segment code


class Segment(_Model):
    id: str = Field(pattern=r'^[a-z0-9-]{1,40}$')
    code: str = Field(max_length=200_000)
    duration: Number = Field(ge=0.5, le=120)
    words: list[Word]
    narration: str
    highlights: list[Highlight] = Field(default_factory=list)
    start_state: StageState
    end_state: StageState


def angle_difference(a: float, b: float) -> float:
    """Smallest signed difference a - b in degrees, in [-180, 180)."""
    return (a - b + 180) % 360 - 180


def state_diff(a: StageState, b: StageState) -> list[str]:
    """Chinese descriptions of every difference between two stage states; [] when equal."""
    diffs: list[str] = []

    def number(label: str, left: float, right: float, tolerance: float) -> None:
        if abs(left - right) > tolerance:
            diffs.append(f'{label}不一致：{left:g} 对 {right:g}')

    number('镜头 x', a.camera.x, b.camera.x, POSITION_TOLERANCE)
    number('镜头 y', a.camera.y, b.camera.y, POSITION_TOLERANCE)
    number('镜头缩放', a.camera.zoom, b.camera.zoom, SCALE_TOLERANCE)

    for name in sorted(set(a.actors) - set(b.actors)):
        diffs.append(f'角色 {name} 只出现在前一个状态里')
    for name in sorted(set(b.actors) - set(a.actors)):
        diffs.append(f'角色 {name} 只出现在后一个状态里')
    for name in sorted(set(a.actors) & set(b.actors)):
        left, right = a.actors[name], b.actors[name]
        number(f'角色 {name} 的 x', left.x, right.x, POSITION_TOLERANCE)
        number(f'角色 {name} 的 y', left.y, right.y, POSITION_TOLERANCE)
        number(f'角色 {name} 的缩放', left.scale, right.scale, SCALE_TOLERANCE)
        if left.flip != right.flip:
            diffs.append(f'角色 {name} 的朝向不一致')
        for part in sorted(set(left.pose) | set(right.pose)):
            l_deg, r_deg = left.pose.get(part, 0), right.pose.get(part, 0)
            # Angles are compared on the circle: the runtime reads poses back with atan2
            # (-180..180), so a declared 200 is measured as -160.
            if abs(angle_difference(l_deg, r_deg)) > ANGLE_TOLERANCE:
                diffs.append(f'角色 {name} 的 {part} 角度不一致：{l_deg:g} 对 {r_deg:g}')

    if sorted(a.keep) != sorted(b.keep):
        diffs.append(f'保留元素不一致：{sorted(a.keep)} 对 {sorted(b.keep)}')
    return diffs
