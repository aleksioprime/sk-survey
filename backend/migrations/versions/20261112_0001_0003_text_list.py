"""Text list questions and answer rows."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('survey_questions', sa.Column('min_rows', sa.Integer(), nullable=True))
    op.add_column('survey_questions', sa.Column('max_rows', sa.Integer(), nullable=True))
    op.add_column('survey_answers', sa.Column('text_rows', JSONB, nullable=False, server_default='[]'))


def downgrade() -> None:
    op.drop_column('survey_answers', 'text_rows')
    op.drop_column('survey_questions', 'max_rows')
    op.drop_column('survey_questions', 'min_rows')
