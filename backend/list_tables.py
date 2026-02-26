from sqlalchemy import create_engine, inspect
engine = create_engine("postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres")
inspector = inspect(engine)
print(inspector.get_table_names())
