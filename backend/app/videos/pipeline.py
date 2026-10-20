"""Shared guards for the single whole-HTML pipeline."""
import io
import wave
from datetime import UTC,datetime
from sqlalchemy import select
from app.models import OutlineJob,VideoProject,User
from app.materials.storage import MaterialStorage
from .service import config_fingerprint
from .speech import synthesize_narration,NARRATION_PROTOCOL_VERSION
from .render_client import RendererClient

def wav_duration(data):
    try:
        with wave.open(io.BytesIO(data),'rb') as audio:
            if audio.getcomptype()!='NONE' or audio.getnframes()<=0: raise ValueError
            duration=audio.getnframes()/audio.getframerate()
    except (wave.Error,ValueError,EOFError): raise ValueError('配音必须为可解码的WAV音频') from None
    if not 0<duration<=120: raise ValueError('单片段配音时长超过限制')
    return duration


async def guard(db,job_id,token,project_id,revision):
    job=await db.scalar(select(OutlineJob).where(OutlineJob.id==job_id).with_for_update().execution_options(populate_existing=True))
    if not job or job.lease_token!=token or job.status!='running' or not job.lease_until or job.lease_until<=datetime.now(UTC):
        raise ValueError('任务已由其他进程接管或终止')
    project=await db.scalar(select(VideoProject).where(VideoProject.id==project_id,VideoProject.owner_id==job.owner_id).with_for_update().execution_options(populate_existing=True))
    owner=await db.get(User,job.owner_id,populate_existing=True)
    if not owner or owner.status!='active': raise ValueError('账号状态已变化，无法继续执行')
    if not project or project.revision!=revision: raise ValueError('项目版本已变化，请重新提交视频任务')
    return project


async def execute_video_job(db,job,settings):
    from .direct_pipeline import execute_direct_job
    return await execute_direct_job(db,job,settings)
