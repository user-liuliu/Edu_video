"""Add user profile fields and avatar object key."""

from alembic import op
import sqlalchemy as sa


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("display_name", sa.String(length=40), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "gender",
            sa.Enum(
                "unspecified", "male", "female", "undisclosed",
                name="usergender", native_enum=False, create_constraint=False, length=16,
            ),
            server_default="unspecified",
            nullable=False,
        ),
    )
    op.add_column("users", sa.Column("school", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("avatar_key", sa.String(length=512), nullable=True))


def downgrade():
    op.drop_column("users", "avatar_key")
    op.drop_column("users", "school")
    op.drop_column("users", "gender")
    op.drop_column("users", "display_name")
