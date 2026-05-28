from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import settings

# Sqlalchemy - Py library 
#  Without wrtiing sql commands (write in python, sqlalchemy can understand and convert into sql commands and execute in database)
# ORM - Object Relational Mapping (Python object -> Sql Database)
# Create engine
#session -intract
# class
# object-do changing
# session.add(object) -> Save
# session.commit() -> Commit
# session.rollback() -> RollBack

# Parent class of User,Scan,Prediction,Scan,Report.
class Base(DeclarativeBase):
    pass

# Import all models to ensure they are registered on Base.metadata and relationship mappers resolve correctly
from app.models.user import User
from app.models.scan import Scan
from app.models.prediction import Prediction
from app.models.report import Report

# Initialize connection engine-  PY & Database 
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True
)


# ||Changes  -> Commit kiya jata  hai.
# RollBack -> To go back

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# FastAPI session dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
