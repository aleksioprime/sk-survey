"""Matrix questions and options excluded from the comparison base."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('survey_questions', sa.Column('matrix_rows', JSONB, nullable=False, server_default='[]'))
    op.add_column('survey_answers', sa.Column('matrix_choices', JSONB, nullable=False, server_default='{}'))
    op.add_column(
        'survey_question_options',
        sa.Column('exclude_from_base', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('survey_question_options', 'exclude_from_base')
    op.drop_column('survey_answers', 'matrix_choices')
    op.drop_column('survey_questions', 'matrix_rows')
