"""Local offline Mandarin speech; no network or model credentials."""
import asyncio
import io
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import wave
from app.model_configs.schemas import ResolvedConfig,Voice
from app.purposes import Purpose

SYSTEM_VOICE='system:zh-CN'
SYSTEM_LABEL='系统配音（离线普通话）'

def available():
    return bool(shutil.which('espeak-ng') and shutil.which('ffmpeg'))

def config():
    if not available():raise ValueError('系统配音组件不可用，请联系管理员')
    return ResolvedConfig(Purpose.tts,'system://offline','','espeak-ng-cmn-1',{'voices':[{'speaker_id':SYSTEM_VOICE,'label':SYSTEM_LABEL}]})

async def voice_options(db,box):
    from app.model_configs import resolve,list_voices
    voices=await list_voices(db) if await resolve(db,box,Purpose.tts) else []
    voices=[v for v in voices if not v.speaker_id.startswith('system:')]
    if available():voices.append(Voice(speaker_id=SYSTEM_VOICE,label=SYSTEM_LABEL))
    return voices

def _generate(text,instruction):
    from .speech import Narration,MAX_AUDIO_BYTES
    if not available():raise ValueError('系统配音组件不可用，请联系管理员')
    # Only explicit speed hints affect this fixed offline voice; never speak instructions.
    rate=155 if re.search(r'慢|舒缓',instruction) else 210 if re.search(r'快|紧凑',instruction) else 180
    sentences=re.findall(r'[^。！？!?]*[。！？!?]+|[^。！？!?]+$',text)
    parts=[];captions=[];frames=0
    try:
        with tempfile.TemporaryDirectory(prefix='edu-speech-') as folder:
            source=Path(folder)/'sentence.wav';target=Path(folder)/'pcm.wav'
            for sentence in sentences:
                if not sentence.strip():continue
                subprocess.run(['espeak-ng','-v','cmn','-s',str(rate),'-w',str(source),'--stdin'],input=sentence.encode('utf-8'),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30,check=True)
                subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-i',str(source),'-ar','48000','-ac','1','-c:a','pcm_s16le',str(target)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30,check=True)
                if target.stat().st_size>MAX_AUDIO_BYTES:raise ValueError('系统配音音频过大')
                with wave.open(str(target),'rb') as audio:
                    if (audio.getnchannels(),audio.getsampwidth(),audio.getframerate())!=(1,2,48000):raise ValueError('系统配音格式无效')
                    pcm=audio.readframes(audio.getnframes())
                count=len(pcm)//2
                if not count or frames+count>48000*120:raise ValueError('单片段系统配音超过120秒，请缩短讲稿')
                captions.append({'start':frames/48000,'end':(frames+count)/48000,'text':sentence})
                frames+=count;parts.append(pcm)
    except (OSError,subprocess.SubprocessError):raise ValueError('系统配音生成失败，请稍后重试或联系管理员') from None
    if not parts:raise ValueError('系统配音讲稿为空')
    output=io.BytesIO()
    with wave.open(output,'wb') as audio:
        audio.setparams((1,2,48000,0,'NONE','not compressed'));audio.writeframes(b''.join(parts))
    return Narration(output.getvalue(),captions)

async def synthesize(text,*,speaker,instruction=''):
    if speaker!=SYSTEM_VOICE:raise ValueError('所选系统配音音色不可用，请重新选择')
    if not text.strip() or len(text)>2000:raise ValueError('单次配音讲稿长度不符合要求')
    return await asyncio.to_thread(_generate,text,instruction)
