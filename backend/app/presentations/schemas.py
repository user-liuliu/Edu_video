from copy import deepcopy
from typing import Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Layout = Literal['cover','concept','image-text','compare','process','practice','summary']

class Slide(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    id: UUID = Field(default_factory=uuid4)
    layout: Layout = 'image-text'
    title: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=1, max_length=3000)
    slots: dict[str,str] = Field(default_factory=dict, max_length=30)

class Outline(BaseModel):
    model_config = ConfigDict(extra='forbid')
    slides: list[Slide] = Field(min_length=1, max_length=40)

    @model_validator(mode='after')
    def unique_ids(self):
        if len({s.id for s in self.slides}) != len(self.slides):
            raise ValueError('页面 ID 重复')
        return self

class ProjectInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title: str = Field(min_length=1,max_length=200)
    prompt: str = Field(min_length=1,max_length=20000)
    style: Literal['auto','clear-blue-teaching','lively-illustration','academic-formal'] = 'auto'
    web_search: bool = False
    revision: int = Field(default=0,ge=0)

class OutlineInput(Outline):
    revision: int = Field(ge=1)

class ConfirmInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=1)

class JobInput(BaseModel):
    model_config = ConfigDict(extra='forbid',str_strip_whitespace=True)
    revision: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1,max_length=128)
    slide_ids: list[UUID] = Field(default_factory=list,max_length=40)
    instruction: str = Field(default='',max_length=4000)

def apply_selected(original, ids, replacements):
    ids=[str(x) for x in ids]
    validated=Outline(slides=replacements).model_dump(mode='json')['slides']
    actual=[s['id'] for s in validated]
    if not ids or len(ids)!=len(set(ids)) or set(actual)!=set(ids):
        raise ValueError('模型返回页面与所选页面不一致')
    known={s['id'] for s in original}
    if not set(ids)<=known:
        raise ValueError('所选页面不存在')
    changed={s['id']:s for s in validated}
    return [deepcopy(changed.get(s['id'],s)) for s in original]


class TextPatch(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False)
    key:str=Field(pattern=r'^text-[0-9]{1,4}$')
    text:str|None=Field(default=None,min_length=1,max_length=2000)
    font_size:float|None=Field(default=None,ge=18,le=72)
    color:str|None=Field(default=None,pattern=r'^#[0-9a-fA-F]{6}$')
    bold:bool|None=None
    width:float|None=Field(default=None,ge=80,le=1200)
    height:float|None=Field(default=None,ge=24,le=720)
    x:float|None=Field(default=None,ge=0,le=1280)
    y:float|None=Field(default=None,ge=0,le=720)
    @model_validator(mode='after')
    def has_change(self):
        if not self.model_fields_set-{'key'} or any(getattr(self,k) is None for k in self.model_fields_set):raise ValueError('请填写修改内容')
        return self

class TextAddition(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    key:str=Field(pattern=r'^new-[0-9]{1,8}$')
    text:str=Field(min_length=1,max_length=2000)
    x:float=Field(ge=0,le=1280)
    y:float=Field(ge=0,le=720)
    width:float=Field(ge=80,le=1200)
    height:float|None=Field(default=None,ge=24,le=720)
    font_size:float=Field(default=28,ge=18,le=72)
    color:str=Field(default='#173359',pattern=r'^#[0-9a-fA-F]{6}$')
    bold:bool=False

class ObjectMove(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False)
    key:str=Field(pattern=r'^object-[0-9]{1,5}$')
    dx:float=Field(ge=-1280,le=1280)
    dy:float=Field(ge=-720,le=720)

class TextEditInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision:int=Field(ge=1)
    edits:list[TextPatch]=Field(default_factory=list,max_length=100)
    additions:list[TextAddition]=Field(default_factory=list,max_length=20)
    moves:list[ObjectMove]=Field(default_factory=list,max_length=200)
    @model_validator(mode='after')
    def nonempty(self):
        if not self.edits and not self.additions and not self.moves:raise ValueError('请先修改文字或添加文本框')
        return self
