from sqlalchemy import create_engine, inspect
engine = create_engine("postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres")
inspector = inspect(engine)
columns = inspector.get_columns('teams')
for column in columns:
    print(column['name'])
