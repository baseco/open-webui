"""add message count to users

Revision ID: add_message_count
Revises: 3781e22d8b01
Create Date: 2025-04-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_message_count'
down_revision = '3781e22d8b01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add message_count column to user table with default 0
    # Using batch_alter_table for SQLite compatibility
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('message_count', sa.BigInteger(), nullable=True, server_default='0'))


def downgrade() -> None:
    # Remove message_count column from user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('message_count')