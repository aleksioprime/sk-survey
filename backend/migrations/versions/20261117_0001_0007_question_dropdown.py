"""Dropdown display for single-choice questions."""

import sqlalchemy as sa
from alembic import op

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('survey_questions', sa.Column('is_dropdown', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column('survey_questions', 'is_dropdown')
