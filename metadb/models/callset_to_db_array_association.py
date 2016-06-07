from ..models import _Base, BigInteger
import sqlalchemy as sa
from sqlalchemy import UniqueConstraint
from sqlalchemy import PrimaryKeyConstraint
from sqlalchemy.orm import relationship, backref
from sqlalchemy.schema import CreateSequence, Sequence

class CallSetToDBArrayAssociation(_Base):
    __tablename__ = "callset_to_db_array_association"

    callset_id = sa.Column(BigInteger, sa.ForeignKey('callset.id'), nullable=False);
    db_array_id = sa.Column(BigInteger, sa.ForeignKey('db_array.id'), nullable=False)
    #If tile_row_id is null, gets assigned by the trigger
    tile_row_id = sa.Column(BigInteger)

    db_array = relationship("DBArray", backref="member_callset_associations")
    __table_args__ = ( 
        PrimaryKeyConstraint('callset_id', 'db_array_id', name='primary_key'),
        )
    #Ensure that (db_array_id, tile_row_id) combination is unique, if tile_row_id != NULL
    sa.Index('db_array_id_tile_row_id_idx', db_array_id, tile_row_id, unique=True);

increment_num_rows_in_db_array_sqlite = sa.DDL('''\
    CREATE TRIGGER increment_num_rows_in_db_array AFTER INSERT ON callset_to_db_array_association
    BEGIN
      UPDATE db_array SET num_rows=
          CASE
               WHEN NEW.tile_row_id IS NULL THEN num_rows+1
               WHEN NEW.tile_row_id >= num_rows THEN NEW.tile_row_id+1
               ELSE num_rows
          END
      WHERE id=NEW.db_array_id;
      UPDATE callset_to_db_array_association SET tile_row_id=(select num_rows from db_array where id=NEW.db_array_id)-1 where NEW.tile_row_id IS NULL and db_array_id=NEW.db_array_id and callset_id=NEW.callset_id;
    END;''')
sa.event.listen(CallSetToDBArrayAssociation.__table__, 'after_create', increment_num_rows_in_db_array_sqlite.execute_if(dialect='sqlite'))

increment_num_rows_in_db_array_pgsql = sa.DDL('''\
    CREATE OR REPLACE FUNCTION increment_num_rows_in_db_array_pgsql()
      RETURNS trigger AS $increment_num_rows_in_db_array_pgsql$
    DECLARE
        updated_num_rows bigint;
    BEGIN
        UPDATE db_array SET num_rows=
            CASE
               WHEN NEW.tile_row_id IS NULL THEN num_rows+1
               WHEN NEW.tile_row_id >= num_rows THEN NEW.tile_row_id+1
               ELSE num_rows
            END
        WHERE id=NEW.db_array_id RETURNING num_rows INTO updated_num_rows;
        IF NEW.tile_row_id IS NULL THEN
            NEW.tile_row_id = updated_num_rows-1;
        END IF;
        RETURN NEW;
    END;
    $increment_num_rows_in_db_array_pgsql$ LANGUAGE plpgsql;
    CREATE TRIGGER increment_num_rows_in_db_array BEFORE INSERT ON callset_to_db_array_association
    FOR EACH ROW EXECUTE PROCEDURE increment_num_rows_in_db_array_pgsql();
    ''')
sa.event.listen(CallSetToDBArrayAssociation.__table__, 'after_create', increment_num_rows_in_db_array_pgsql.execute_if(dialect='postgresql'))
