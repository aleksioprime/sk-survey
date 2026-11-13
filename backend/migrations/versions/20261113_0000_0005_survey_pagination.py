"""Add survey pagination and section heading settings."""

import sqlalchemy as sa
from alembic import op

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('surveys', sa.Column('one_question_per_page', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('survey_sections', sa.Column('show_heading', sa.Boolean(), server_default=sa.true(), nullable=False))


def downgrade() -> None:
    op.drop_column('survey_sections', 'show_heading')
    op.drop_column('surveys', 'one_question_per_page')
