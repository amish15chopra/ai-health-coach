from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

class UserBase(BaseModel):
    class Config:
        from_attributes = True
    age: int
    weight: float
    health_conditions: Optional[str] = None
    diet_preferences: Optional[str] = None
    goals: Optional[str] = None
    # per-user daily macro goals
    daily_calories: int = 2000
    daily_protein: int = 75
    daily_carbs: int = 250
    daily_fat: int = 70

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

# Request schema for meal suggestion based on fridge ingredients
class SuggestRequest(BaseModel):
    user_id: int
    fridge_items: List[str] = []

# Response schema for meal suggestion
class MealSuggestion(BaseModel):
    recommendation: str
    missing_ingredients: List[str]
    reason: str

    class Config:
        from_attributes = True
