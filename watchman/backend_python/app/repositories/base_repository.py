# =============================================================
# app/repositories/base_repository.py
# Purpose : Generic CRUD repository that ALL other repositories inherit.
# Pattern : Generic Repository (used at Uber, Airbnb internally)
# Benefit : Write CRUD once, inherit everywhere. DRY principle.
# =============================================================

from typing import Generic, Optional, Type, TypeVar

from sqlalchemy.orm import Session

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Provides get, list, create, update, delete operations for any ORM model.
    Subclasses can add domain-specific query methods on top of these.
    """

    def __init__(self, model: Type[ModelType], db: Session) -> None:
        self.model = model
        self.db = db

    def get_by_id(self, record_id: int) -> Optional[ModelType]:
        """Fetch a single record by primary key. Returns None if not found."""
        return self.db.query(self.model).filter(self.model.id == record_id).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> list[ModelType]:
        """Fetch all records with optional pagination."""
        return self.db.query(self.model).offset(skip).limit(limit).all()

    def create(self, obj: ModelType) -> ModelType:
        """Persist a new record and return it with its generated ID."""
        self.db.add(obj)
        self.db.flush()  # Flush to DB to get the auto-generated ID
        self.db.refresh(obj)
        return obj

    def update(self, obj: ModelType) -> ModelType:
        """Persist changes to an existing record."""
        self.db.flush()
        self.db.refresh(obj)
        return obj

    def delete(self, record_id: int) -> bool:
        """Delete a record by ID. Returns True if deleted, False if not found."""
        obj = self.get_by_id(record_id)
        if obj is None:
            return False
        self.db.delete(obj)
        self.db.flush()
        return True
