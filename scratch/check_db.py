import sqlalchemy as sa
from storage.database import engine
import json

def check_db():
    metadata = sa.MetaData()
    try:
        acc = sa.Table('hbl_account', metadata, autoload_with=engine)
        with engine.connect() as conn:
            cnt = conn.execute(sa.select(sa.func.count()).select_from(acc)).scalar()
            print(f"hbl_account count: {cnt}")
            rows = conn.execute(sa.select(acc).limit(2)).mappings().all()
            print(f"Sample rows: {rows}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_db()
