from sqlalchemy.orm import Session
from models import User
from schemas import UserCreate, UserRead
from fastapi import HTTPException

def create_or_update_user(db: Session, user: UserCreate) -> UserRead:
    db_user = db.query(User).filter(User.id == user.id).first() if user.id else None
    if db_user:
        for key, value in user.dict(exclude_unset=True).items():
            setattr(db_user, key, value)
    else:
        db_user = User(**user.dict(exclude={"id"}))
        db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return UserRead.from_orm(db_user)


def get_user(db: Session, user_id: int) -> UserRead:
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserRead.from_orm(db_user)
