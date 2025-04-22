from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class UserBase(BaseModel):
    class Config:
        from_attributes = True
    age: int
    weight: float
    health_conditions: Optional[str] = None
    diet_preferences: Optional[str] = None
    goals: Optional[str] = None

class UserCreate(UserBase):
    id: Optional[int] = None

class UserRead(UserBase):
    id: int

    class Config:
        from_attributes = True

class AdviceResponse(BaseModel):
    advice: str
    reason: str
    next_meal: str

class NutritionInfo(BaseModel):
    calories: int
    protein: int
    carbs: int
    fat: int

    class Config:
        from_attributes = True

class MealRead(BaseModel):
    id: int
    user_id: int
    timestamp: datetime
    image_path: str
    food_items: Dict[str, Any]
    nutrition_info: Dict[str, Any]
    feedback: Dict[str, Any]

    class Config:
        from_attributes = True
