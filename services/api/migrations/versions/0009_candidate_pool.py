"""Session-owned, bounded assistant candidates; old conversations start empty."""
import sqlalchemy as sa
from alembic import op

revision = '0009_candidate_pool'
down_revision = '0008_account_preferences'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('account_conversations', sa.Column('search_state', sa.JSON(), nullable=False,
                                                   server_default=sa.text("'{}'")))


def downgrade():
    op.drop_column('account_conversations', 'search_state')
