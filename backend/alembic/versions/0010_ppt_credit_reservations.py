"""PPT generation holds share the account wallet without changing existing video holds."""
from alembic import op
import sqlalchemy as sa
revision='0010'
down_revision='0009'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('ppt_credit_reservations',
        sa.Column('job_id',sa.Uuid(),sa.ForeignKey('ppt_jobs.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('owner_id',sa.Uuid(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('amount',sa.Integer(),nullable=False),
        sa.Column('description',sa.String(240),nullable=False),
        sa.Column('state',sa.String(16),nullable=False,server_default='reserved'))
    op.create_index('ix_ppt_credit_reservations_owner_id','ppt_credit_reservations',['owner_id'])

def downgrade():
    op.drop_table('ppt_credit_reservations')
