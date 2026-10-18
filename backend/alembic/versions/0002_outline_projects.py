"""Teacher video projects and editable drafts."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('video_projects',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('owner_id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('form_values', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('status', sa.String(32), server_default='draft', nullable=False),
        sa.Column('revision', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('outline', postgresql.JSONB(), nullable=True),
        sa.Column('needs_regeneration',sa.Boolean(),server_default=sa.text('false'),nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name='fk_video_projects_owner_id_users'),
        sa.PrimaryKeyConstraint('id', name='pk_video_projects'))
    op.create_index('ix_video_projects_owner_id', 'video_projects', ['owner_id'])


def downgrade():
    op.drop_table('video_projects')
