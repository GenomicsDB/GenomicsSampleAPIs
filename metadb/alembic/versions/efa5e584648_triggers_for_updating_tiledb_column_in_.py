"""Triggers for updating tiledb_column in reference

Revision ID: efa5e584648
Revises: 183533b82112
Create Date: 2015-12-16 13:41:59.567423

"""

# revision identifiers, used by Alembic.
revision = 'efa5e584648'
down_revision = '183533b82112'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('reference_set', sa.Column(
        'next_tiledb_column_offset', sa.BigInteger(), nullable=False, default=0))
    op.add_column('reference', sa.Column(
        'tiledb_column_offset', sa.BigInteger(), nullable=True))
    op.alter_column('reference', 'length',
                    existing_type=sa.BIGINT(),
                    nullable=False)
    op.alter_column('reference', 'name',
                    existing_type=sa.TEXT(),
                    nullable=False)
    op.create_unique_constraint('unique_name_per_reference_set_constraint', 'reference', [
                                'reference_set_id', 'name'])
    op.create_index('unique_reference_set_id_offset_idx', 'reference', [
                    'reference_set_id', 'tiledb_column_offset'], unique=True)
    op.drop_column('reference', 'offset')
    # Trigger on reference insertion
    op.execute('''\
    CREATE OR REPLACE FUNCTION increment_next_column_in_reference_set_pgsql()
      RETURNS trigger AS $increment_next_column_in_reference_set_pgsql$
    BEGIN
      UPDATE reference SET tiledb_column_offset=(select next_tiledb_column_offset from reference_set where id=NEW.reference_set_id) where NEW.tiledb_column_offset IS NULL and id=NEW.id;
      UPDATE reference_set SET next_tiledb_column_offset=next_tiledb_column_offset+NEW.length WHERE id = NEW.reference_set_id;
      RETURN NEW;
    END;
    $increment_next_column_in_reference_set_pgsql$ LANGUAGE plpgsql;
    CREATE TRIGGER increment_next_column_in_reference_set AFTER INSERT ON reference
    FOR EACH ROW EXECUTE PROCEDURE increment_next_column_in_reference_set_pgsql();
    ''')
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    # Drop trigger
    op.execute(
        'DROP TRIGGER increment_next_column_in_reference_set ON reference CASCADE')
    op.add_column('reference', sa.Column(
        'offset', sa.BIGINT(), autoincrement=False, nullable=True))
    op.drop_index('unique_reference_set_id_offset_idx', table_name='reference')
    op.drop_constraint(
        'unique_name_per_reference_set_constraint', 'reference', type_='unique')
    op.alter_column('reference', 'name',
                    existing_type=sa.TEXT(),
                    nullable=True)
    op.alter_column('reference', 'length',
                    existing_type=sa.BIGINT(),
                    nullable=True)
    op.drop_column('reference', 'tiledb_column_offset')
    op.drop_column('reference_set', 'next_tiledb_column_offset')
    ### end Alembic commands ###
