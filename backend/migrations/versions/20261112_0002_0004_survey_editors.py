"""Merge survey owners into editors."""

from alembic import op

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE survey_members SET role = 'editor' WHERE role = 'owner'")


def downgrade() -> None:
    # При откате выбираем создателя из действующих редакторов, иначе редактора с наименьшим ID.
    op.execute("""
        WITH owners AS (
            SELECT DISTINCT ON (m.survey_id) m.survey_id, m.user_id
            FROM survey_members m
            JOIN surveys s ON s.id = m.survey_id
            ORDER BY m.survey_id, (m.user_id = s.created_by_id) DESC NULLS LAST, m.user_id
        )
        UPDATE survey_members m
        SET role = 'owner'
        FROM owners
        WHERE m.survey_id = owners.survey_id AND m.user_id = owners.user_id
    """)
