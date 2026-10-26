"""Independent editable presentation projects, materials and job outbox."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision='0008'
down_revision='0007'
branch_labels=None
depends_on=None

def timestamps():
    return [sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now())]

def upgrade():
    op.create_table('ppt_projects',
        sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('owner_id',sa.Uuid(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('title',sa.String(200),nullable=False),sa.Column('prompt',sa.Text(),nullable=False),
        sa.Column('style',sa.String(64),nullable=False),sa.Column('web_search',sa.Boolean(),nullable=False),
        sa.Column('template_id',sa.String(64),nullable=False),sa.Column('template_version',sa.String(16),nullable=False),
        sa.Column('status',sa.String(32),nullable=False),sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('confirmed_revision',sa.Integer()),sa.Column('rendered_revision',sa.Integer()),
        sa.Column('outline',JSONB()),sa.Column('pages',JSONB(),nullable=False),sa.Column('history',JSONB(),nullable=False),sa.Column('warnings',JSONB(),nullable=False),*timestamps())
    op.create_index('ix_ppt_projects_owner_id','ppt_projects',['owner_id'])
    op.create_table('ppt_materials',
        sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('owner_id',sa.Uuid(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('project_id',sa.Uuid(),sa.ForeignKey('ppt_projects.id',ondelete='CASCADE'),nullable=False),
        sa.Column('filename',sa.String(255),nullable=False),sa.Column('object_key',sa.String(512),nullable=False),
        sa.Column('content_type',sa.String(128),nullable=False),sa.Column('size',sa.Integer(),nullable=False),
        sa.Column('status',sa.String(32),nullable=False),sa.Column('error_message',sa.Text()),
        sa.Column('chunks',JSONB(),nullable=False),sa.Column('parse_warnings',JSONB(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_index('ix_ppt_materials_project_id','ppt_materials',['project_id'])
    op.create_table('ppt_jobs',
        sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('owner_id',sa.Uuid(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('project_id',sa.Uuid(),sa.ForeignKey('ppt_projects.id',ondelete='CASCADE'),nullable=False),
        sa.Column('kind',sa.String(32),nullable=False),sa.Column('idempotency_key',sa.String(128),nullable=False),
        sa.Column('expected_revision',sa.Integer(),nullable=False),sa.Column('payload',JSONB(),nullable=False),sa.Column('checkpoint',JSONB(),nullable=False),
        sa.Column('status',sa.String(32),nullable=False),sa.Column('stage',sa.String(64),nullable=False),
        sa.Column('progress',sa.Integer(),nullable=False),sa.Column('attempts',sa.Integer(),nullable=False),
        sa.Column('error_message',sa.Text()),sa.Column('lease_token',sa.Uuid()),sa.Column('lease_until',sa.DateTime(timezone=True)),sa.Column('dispatched_at',sa.DateTime(timezone=True)),
        sa.UniqueConstraint('owner_id','project_id','kind','idempotency_key',name='uq_ppt_jobs_request'),*timestamps())
    for col in ['owner_id','project_id','status']:op.create_index('ix_ppt_jobs_'+col,'ppt_jobs',[col])

def downgrade():
    for table in ['ppt_jobs','ppt_materials','ppt_projects']:op.drop_table(table)
