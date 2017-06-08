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

"""Add padding in triggers for tiledb_column_offset

Revision ID: 2c637cb34186
Revises: 323f2c3ccf2f
Create Date: 2015-12-18 11:35:11.282313

"""

# revision identifiers, used by Alembic.
revision = '2c637cb34186'
down_revision = '323f2c3ccf2f'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from metadb.models import get_tiledb_padded_reference_length_string


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    # drop and re-create trigger
    op.execute(
        'DROP TRIGGER IF EXISTS increment_next_column_in_reference_set ON reference CASCADE')
    padded_length = get_tiledb_padded_reference_length_string('NEW.length')
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
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    # Don't downgrade updated trigger function that adds padding
    pass
    ### end Alembic commands ###