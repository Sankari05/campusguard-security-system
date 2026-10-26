# app/repositories/user_repository.py
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: Session) -> None:
        super().__init__(User, db)

    def find_by_username(self, username: str) -> Optional[User]:
        return self.db.query(User).filter(User.username == username).first()

    def find_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def find_by_username_or_email(self, identifier: str) -> Optional[User]:
        return (
            self.db.query(User)
            .filter((User.username == identifier) | (User.email == identifier))
            .first()
        )
