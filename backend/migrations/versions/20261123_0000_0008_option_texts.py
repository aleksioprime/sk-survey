"""Optional text for selected choices."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'survey_question_options', sa.Column('allows_text', sa.Boolean(), server_default=sa.false(), nullable=False)
    )
    op.add_column('survey_answers', sa.Column('option_texts', JSONB(), server_default='{}', nullable=False))


def downgrade() -> None:
    op.drop_column('survey_answers', 'option_texts')
    op.drop_column('survey_question_options', 'allows_text')
