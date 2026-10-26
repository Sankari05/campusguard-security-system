# =============================================================
# app/db/base.py
# Purpose : Declares the SQLAlchemy DeclarativeBase that ALL models extend.
# Pattern : Shared Base (standard SQLAlchemy enterprise pattern)
# =============================================================

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    All ORM model classes inherit from this Base.
    Equivalent to extending @Entity in Java JPA / Hibernate.
    """

    pass
