from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import api_error
from app.models import VideoProject


async def get_owned_project(db: AsyncSession, owner_id: UUID, project_id: UUID, *, lock: bool = False) -> VideoProject:
    stmt = select(VideoProject).where(VideoProject.id == project_id, VideoProject.owner_id == owner_id).execution_options(populate_existing=True)
    if lock:
        stmt = stmt.with_for_update()
    project = (await db.execute(stmt)).scalar_one_or_none()
    if project is None:
        raise api_error(404, 'project_not_found', '项目不存在')
    return project


def check_revision(project: VideoProject, revision: int) -> None:
    if project.revision != revision:
        raise api_error(409, 'revision_conflict', '项目已在其他页面更新，请刷新后重试')
