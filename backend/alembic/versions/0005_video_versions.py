"""Private video versions and immutable teaching paragraph mappings."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('video_versions',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('owner_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('project_id', sa.Uuid(), sa.ForeignKey('video_projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('job_id', sa.Uuid(), sa.ForeignKey('outline_jobs.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('source_version_id', sa.Uuid(), sa.ForeignKey('video_versions.id', ondelete='SET NULL')),
        sa.Column('number', sa.Integer(), nullable=False),
        sa.Column('outline_revision', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(32), nullable=False, server_default='queued'),
        sa.Column('snapshot', JSONB(), nullable=False),
        sa.Column('media_key', sa.String(512)),
        sa.Column('duration', sa.Float()),
        sa.Column('asset_keys', JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('project_id', 'number', name='uq_video_version_number'),
    )
    for field in ('owner_id', 'project_id'): op.create_index(f'ix_video_versions_{field}', 'video_versions', [field])
    op.create_table('video_segments',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('version_id', sa.Uuid(), sa.ForeignKey('video_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('outline_segment_id', sa.Uuid(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('narration', sa.Text(), nullable=False),
        sa.Column('start', sa.Float()), sa.Column('end', sa.Float()),
        sa.Column('fingerprint', sa.String(64), nullable=False, server_default=''),
        sa.Column('assets', JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint('version_id', 'position', name='uq_video_segment_position'),
    )
    op.create_index('ix_video_segments_version_id', 'video_segments', ['version_id'])


def downgrade():
    op.drop_table('video_segments')
    op.drop_table('video_versions')
