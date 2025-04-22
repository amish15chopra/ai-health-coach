import os
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv
from typing import List
from schemas import UserCreate, UserRead, MealRead
from models import Base
from services.user_service import create_or_update_user, get_user
from services.meal_service import analyze_meal, get_meal_history

# Load environment variables
load_dotenv()

db_url = os.getenv("DATABASE_URL")
if not db_url:
    raise RuntimeError("DATABASE_URL is not set")

# Database setup
engine = create_engine(db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

@app.post("/user", response_model=UserRead)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    return create_or_update_user(db, user)

@app.get("/user/{user_id}", response_model=UserRead)
def get_user_profile(user_id: int, db: Session = Depends(get_db)):
    return get_user(db, user_id)

@app.post("/analyze_meal", response_model=MealRead)
async def analyze_meal_route(user_id: int = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        result = await analyze_meal(db, user_id, file)
        return jsonable_encoder(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/meal_history/{user_id}", response_model=List[MealRead])
def meal_history_route(user_id: int, db: Session = Depends(get_db)):
    return get_meal_history(db, user_id)

@app.get("/", response_class=HTMLResponse)
def read_root():
    with open("frontend/index.html") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content, status_code=200)
