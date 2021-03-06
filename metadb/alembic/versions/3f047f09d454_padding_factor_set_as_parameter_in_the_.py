"""
  The MIT License (MIT)
  Copyright (c) 2016 Intel Corporation

  Permission is hereby granted, free of charge, to any person obtaining a copy of 
  this software and associated documentation files (the "Software"), to deal in 
  the Software without restriction, including without limitation the rights to 
  use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of 
  the Software, and to permit persons to whom the Software is furnished to do so, 
  subject to the following conditions:

  The above copyright notice and this permission notice shall be included in all 
  copies or substantial portions of the Software.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS 
  FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR 
  COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER 
  IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN 
  CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

"""Padding factor set as parameter in the SQL table reference_set

Revision ID: 3f047f09d454
Revises: 2c637cb34186
Create Date: 2015-12-18 14:13:32.947444

"""

# revision identifiers, used by Alembic.
revision = '3f047f09d454'
down_revision = '2c637cb34186'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from metadb.models import get_tiledb_padded_reference_length_string, get_tiledb_padded_reference_length_string_default


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        'reference_set',
        sa.Column('tiledb_reference_offset_padding_factor', sa.Float(53), server_default=sa.text(u'1.10'), nullable=False))
    op.drop_column('reference_set', 'offset_factor')
    # drop and re-create trigger
    op.execute(
        'DROP TRIGGER IF EXISTS increment_next_column_in_reference_set ON reference CASCADE')
    padded_length = get_tiledb_padded_reference_length_string('NEW.length')
    op.execute('''\
    CREATE OR REPLACE FUNCTION increment_next_column_in_reference_set_pgsql()
      RETURNS trigger AS $increment_next_column_in_reference_set_pgsql$
    DECLARE
        updated_next_tiledb_column_offset bigint;
        padded_reference_length bigint;
    BEGIN
        padded_reference_length = %s;
        UPDATE reference_set SET next_tiledb_column_offset=
            CASE
                WHEN NEW.tiledb_column_offset IS NULL THEN next_tiledb_column_offset+padded_reference_length
                WHEN NEW.tiledb_column_offset+padded_reference_length>next_tiledb_column_offset THEN NEW.tiledb_column_offset+padded_reference_length
                ELSE next_tiledb_column_offset
            END
        WHERE id = NEW.reference_set_id RETURNING next_tiledb_column_offset INTO updated_next_tiledb_column_offset;
        IF NEW.tiledb_column_offset IS NULL THEN
            NEW.tiledb_column_offset = updated_next_tiledb_column_offset-padded_reference_length;
        END IF;
        RETURN NEW;
    END;
    $increment_next_column_in_reference_set_pgsql$ LANGUAGE plpgsql;
    CREATE TRIGGER increment_next_column_in_reference_set BEFORE INSERT ON reference
    FOR EACH ROW EXECUTE PROCEDURE increment_next_column_in_reference_set_pgsql();
    ''' % (padded_length))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    # Downgrade trigger by dropping the trigger and downgrading the trigger
    # function
    op.execute(
        'DROP TRIGGER IF EXISTS increment_next_column_in_reference_set ON reference CASCADE')
    padded_length = get_tiledb_padded_reference_length_string_default('NEW.length')
    op.execute('''\
    CREATE OR REPLACE FUNCTION increment_next_column_in_reference_set_pgsql()
      RETURNS trigger AS $increment_next_column_in_reference_set_pgsql$
    DECLARE
        updated_next_tiledb_column_offset bigint;
    BEGIN
        UPDATE reference_set SET next_tiledb_column_offset=
            CASE
                WHEN NEW.tiledb_column_offset IS NULL THEN next_tiledb_column_offset+%s
                WHEN NEW.tiledb_column_offset+%s>next_tiledb_column_offset THEN NEW.tiledb_column_offset+%s
                ELSE next_tiledb_column_offset
            END
        WHERE id = NEW.reference_set_id RETURNING next_tiledb_column_offset INTO updated_next_tiledb_column_offset;
        IF NEW.tiledb_column_offset IS NULL THEN
            NEW.tiledb_column_offset = updated_next_tiledb_column_offset-%s;
        END IF;
        RETURN NEW;
    END;
    $increment_next_column_in_reference_set_pgsql$ LANGUAGE plpgsql;
    CREATE TRIGGER increment_next_column_in_reference_set BEFORE INSERT ON reference
    FOR EACH ROW EXECUTE PROCEDURE increment_next_column_in_reference_set_pgsql();
    ''' % (padded_length, padded_length, padded_length, padded_length))

    op.add_column(
        'reference_set',
        sa.Column('offset_factor',sa.Float(53),autoincrement=False,nullable=True))
    op.drop_column('reference_set', 'tiledb_reference_offset_padding_factor')
    ### end Alembic commands ###
