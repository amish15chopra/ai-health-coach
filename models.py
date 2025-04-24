from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    age = Column(Integer, nullable=False)
    weight = Column(Float, nullable=False)
    health_conditions = Column(String, nullable=True)
    diet_preferences = Column(String, nullable=True)
    goals = Column(String, nullable=True)
    # Daily macro goals per user
    daily_calories = Column(Integer, nullable=False, default=2000)
    daily_protein = Column(Integer, nullable=False, default=75)
    daily_carbs = Column(Integer, nullable=False, default=250)
    daily_fat = Column(Integer, nullable=False, default=70)

class Meal(Base):
    __tablename__ = "meals"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    image_path = Column(String, nullable=False)
    food_items = Column(JSON, nullable=False)
    nutrition_info = Column(JSON, nullable=False)
    feedback = Column(JSON, nullable=False)
