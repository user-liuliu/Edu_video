"""Keep generated PPTs as drafts until a successful explicit full export."""
from alembic import op
import sqlalchemy as sa
revision='0009'
down_revision='0008'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('ppt_projects',sa.Column('exported_revision',sa.Integer(),nullable=True))

def downgrade():
    op.drop_column('ppt_projects','exported_revision')
