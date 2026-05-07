"""
storage/database.py
Backwards compatibility shim — re-exports from core/database.py.
"""
from core.database import engine, SessionLocal, Base, get_db

__all__ = ["engine", "SessionLocal", "Base", "get_db"]
