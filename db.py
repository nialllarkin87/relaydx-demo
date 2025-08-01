# relaydx_demo/db.py

from sqlmodel import SQLModel, create_engine, Session

# This will create a file relaydx_demo.db next to your code
DATABASE_URL = "sqlite:///relaydx_demo.db"

# Create the SQLModel engine
engine = create_engine(DATABASE_URL, echo=True)

def init_db():
    """
    Create all tables in the database.
    Call this once at application startup.
    """
    SQLModel.metadata.create_all(engine)

def get_session():
    """
    Return a new SQLModel Session.
    Use this to read/write LabResult records.
    """
    return Session(engine)
