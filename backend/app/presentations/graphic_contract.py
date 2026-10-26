"""Shared data-only contract used by the backend and the isolated browser worker."""
from typing import Literal
import unicodedata
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator

LEGACY_VERSION='antv-0.2.20-edu-1'
VERSION='antv-0.2.20-edu-2'
WIDTH=1100
HEIGHT=400
MAX_PNG=3*1024**2

class GraphicItem(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    label:str=Field(min_length=1,max_length=12)
    desc:str=Field(min_length=1,max_length=36)
    motif:Literal['none','leaf','leaf-shade','leaf-result','beaker','sun','energy','cell']='none'

    @field_validator('label','desc')
    @classmethod
    def plain_text(cls,value):
        if not value.strip() or any(c in value for c in '<>') or any(unicodedata.category(c).startswith('C') for c in value):raise ValueError('plain visible text required')
        if '://' in value:raise ValueError('URLs are not supported')
        return value

class GraphicSpec(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    kind:Literal['process','compare']
    items:list[GraphicItem]=Field(min_length=2,max_length=4)

    @model_validator(mode='after')
    def counts(self):
        if self.kind=='compare' and len(self.items)!=2:raise ValueError('compare requires two sides')
        return self
