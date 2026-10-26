"""Wallets, targeted redemption codes and durable credit ledger."""
from alembic import op
import sqlalchemy as sa

revision='0007'
down_revision='0006'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('credit_wallets',
        sa.Column('owner_id',sa.Uuid(),sa.ForeignKey('users.id'),primary_key=True),
        sa.Column('balance',sa.Integer(),nullable=False,server_default=sa.text('0')),
        sa.CheckConstraint('balance >= 0',name=op.f('ck_credit_wallets_nonnegative_balance')))
    op.create_table('credit_codes',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('user_id',sa.Uuid(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('created_by',sa.Uuid(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('digest',sa.String(64),nullable=False,unique=True),
        sa.Column('suffix',sa.String(4),nullable=False),
        sa.Column('amount',sa.Integer(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('redeemed_at',sa.DateTime(timezone=True)),
        sa.Column('revoked_at',sa.DateTime(timezone=True)),
        sa.CheckConstraint('amount > 0 AND amount <= 1000000',name=op.f('ck_credit_codes_positive_amount')))
    op.create_index('ix_credit_codes_user_id','credit_codes',['user_id'])
    op.create_table('credit_transactions',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('owner_id',sa.Uuid(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('kind',sa.String(24),nullable=False),
        sa.Column('source_id',sa.Uuid(),nullable=False),
        sa.Column('description',sa.String(240),nullable=False),
        sa.Column('amount',sa.Integer(),nullable=False),
        sa.Column('balance_after',sa.Integer(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint('kind','source_id',name='uq_credit_transactions_source'))
    op.create_index('ix_credit_transactions_owner_id','credit_transactions',['owner_id'])
    op.create_table('credit_reservations',
        sa.Column('job_id',sa.Uuid(),sa.ForeignKey('outline_jobs.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('owner_id',sa.Uuid(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('amount',sa.Integer(),nullable=False),
        sa.Column('description',sa.String(240),nullable=False),
        sa.Column('state',sa.String(16),nullable=False,server_default='reserved'))
    op.create_index('ix_credit_reservations_owner_id','credit_reservations',['owner_id'])

def downgrade():
    op.drop_table('credit_reservations')
    op.drop_table('credit_transactions')
    op.drop_table('credit_codes')
    op.drop_table('credit_wallets')
