import base64
import binascii
from pydantic import BaseModel,ConfigDict,Field,model_validator
MAX_OUTPUT_BYTES=160*1024*1024
class StrictModel(BaseModel):
    model_config=ConfigDict(extra="forbid",allow_inf_nan=False)

class DirectHtmlRuntimeError(ValueError):
    """Repairable document execution failure; distinct from transport/encoding."""


def decoded(value,limit):
    try: data=base64.b64decode(value,validate=True)
    except (ValueError,binascii.Error): raise ValueError('媒体数据无效') from None
    if not data or len(data)>limit: raise ValueError('媒体大小超出范围')
    return data


class DirectRenderRequest(StrictModel):
    compiler_digest: str = Field(pattern=r'^[0-9a-f]{64}$')
    html: str = Field(max_length=1_500_000)
    manifest: dict
    audio_base64: str = Field(max_length=196*1024*1024)
    width: int = Field(default=1280,ge=240,le=1920)
    height: int = Field(default=720,ge=240,le=1920)
    fps: int = Field(default=30,ge=1,le=30)

    @model_validator(mode='after')
    def valid_film(self):
        import io, wave
        from .direct_html import validate_html, validate_manifest, MAX_AUDIO_BYTES
        validate_html(self.html);validate_manifest(self.manifest)
        if self.width%2 or self.height%2:raise ValueError('视频尺寸必须为偶数')
        data=decoded(self.audio_base64,MAX_AUDIO_BYTES)
        try:
            with wave.open(io.BytesIO(data),'rb') as audio:
                duration=audio.getnframes()/audio.getframerate()
                if audio.getcomptype()!='NONE' or abs(duration-self.manifest['duration'])>1/30:raise ValueError('整片音轨时长不一致')
        except (wave.Error,EOFError,ZeroDivisionError):raise ValueError('整片音轨格式无效') from None
        return self


