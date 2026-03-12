"""Add batch_number to purchase_orders

Revision ID: b3f92a1c0541
Revises: 8cb10265c120
Create Date: 2026-03-12 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b3f92a1c0541'
down_revision = '8cb10265c120'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('purchase_orders') as batch_op:
        batch_op.add_column(sa.Column('batch_number', sa.String(length=50), nullable=True))
        batch_op.create_index('ix_purchase_orders_batch_number', ['batch_number'])


def downgrade():
    with op.batch_alter_table('purchase_orders') as batch_op:
        batch_op.drop_index('ix_purchase_orders_batch_number')
        batch_op.drop_column('batch_number')
