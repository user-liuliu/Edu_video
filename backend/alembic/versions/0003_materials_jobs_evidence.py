"""Private materials, durable outbox jobs, evidence and preferences."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

def common(project=True):
    cols = [sa.Column('id',sa.Uuid(),nullable=False),sa.Column('owner_id',sa.Uuid(),nullable=False)]
    if project: cols.append(sa.Column('project_id',sa.Uuid(),nullable=False))
    return cols

def create(name, cols, project=True, extra=()):
    constraints = [sa.ForeignKeyConstraint(['owner_id'],['users.id'],name=f'fk_{name}_owner_id_users'),sa.PrimaryKeyConstraint('id',name=f'pk_{name}')]
    if project: constraints.append(sa.ForeignKeyConstraint(['project_id'],['video_projects.id'],ondelete='CASCADE',name=f'fk_{name}_project_id_video_projects'))
    op.create_table(name,*common(project),*cols,*constraints,*extra)
    op.create_index(f'ix_{name}_owner_id',name,['owner_id'])
    if project: op.create_index(f'ix_{name}_project_id',name,['project_id'])

def created(): return sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False)

def upgrade():
    create('materials',[
        sa.Column('filename',sa.String(255),nullable=False),sa.Column('object_key',sa.String(512),nullable=False),
        sa.Column('content_type',sa.String(128),nullable=False),sa.Column('size',sa.Integer(),nullable=False),
        sa.Column('status',sa.String(32),server_default='pending',nullable=False),sa.Column('error_message',sa.Text()),created(),
    ])
    create('material_chunks',[
        sa.Column('material_id',sa.Uuid(),nullable=False),sa.Column('position',sa.Integer(),nullable=False),
        sa.Column('location',sa.String(128),nullable=False),sa.Column('text',sa.Text(),nullable=False),sa.Column('image_key',sa.String(512)),
    ],extra=[sa.ForeignKeyConstraint(['material_id'],['materials.id'],ondelete='CASCADE',name='fk_material_chunks_material_id_materials')])
    op.create_index('ix_material_chunks_material_id','material_chunks',['material_id'])
    create('outline_jobs',[
        sa.Column('kind',sa.String(32),nullable=False),sa.Column('idempotency_key',sa.String(128),nullable=False),
        sa.Column('expected_revision',sa.Integer(),nullable=False),sa.Column('payload',JSONB(),server_default=sa.text("'{}'::jsonb"),nullable=False),
        sa.Column('status',sa.String(32),server_default='pending',nullable=False),sa.Column('stage',sa.String(64),server_default='等待处理',nullable=False),
        sa.Column('progress',sa.Integer(),server_default=sa.text('0'),nullable=False),sa.Column('attempts',sa.Integer(),server_default=sa.text('0'),nullable=False),
        sa.Column('error_message',sa.Text()),sa.Column('lease_token',sa.Uuid()),sa.Column('lease_until',sa.DateTime(timezone=True)),
        sa.Column('dispatched_at',sa.DateTime(timezone=True)),created(),sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
    ],extra=[sa.UniqueConstraint('owner_id','project_id','kind','idempotency_key',name='uq_outline_jobs_request')])
    create('evidence',[
        sa.Column('claim',sa.Text(),nullable=False),sa.Column('source_type',sa.String(32),nullable=False),sa.Column('source_ref',sa.Text(),nullable=False),
        sa.Column('location',sa.String(128),server_default='',nullable=False),sa.Column('excerpt',sa.Text(),nullable=False),
        sa.Column('source_grade',sa.String(32),nullable=False),sa.Column('verification_status',sa.String(32),server_default='unverified',nullable=False),
    ])
    create('preferences',[
        sa.Column('category',sa.String(32),nullable=False),sa.Column('value',sa.String(200),nullable=False),
        sa.Column('accepted',sa.Boolean(),server_default=sa.text('true'),nullable=False),created(),
    ],project=False)
    op.create_table('object_cleanup',sa.Column('id',sa.Uuid(),nullable=False),sa.Column('object_key',sa.String(512),nullable=False),created(),
        sa.PrimaryKeyConstraint('id',name='pk_object_cleanup'),sa.UniqueConstraint('object_key',name='uq_object_cleanup_object_key'))

def downgrade():
    for name in ('object_cleanup','preferences','evidence','outline_jobs','material_chunks','materials'): op.drop_table(name)
