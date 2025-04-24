import os
import uuid
import json
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, UploadFile
from models import Meal
from schemas import AdviceResponse, MealRead, NutritionInfo, MealSuggestion
from services.user_service import get_user
from services.openai_service import call_openai
import base64
from datetime import date

# GPT API integration uses call_openai; key is loaded by openai_service

DAILY_CALORIES = int(os.getenv("DAILY_CALORIES", "2000"))
DAILY_PROTEIN = int(os.getenv("DAILY_PROTEIN", "75"))
DAILY_CARBS = int(os.getenv("DAILY_CARBS", "250"))
DAILY_FAT = int(os.getenv("DAILY_FAT", "70"))

# Utility to filter today's meals
def _get_todays_meals(all_history: List[MealRead]) -> List[Dict[str, Any]]:
    today = date.today()
    return [
        {
            "timestamp": m.timestamp.isoformat(),
            "food_items": m.food_items,
            "nutrition_info": m.nutrition_info,
            "feedback": m.feedback if not hasattr(m.feedback, "dict") else m.feedback.dict(),
        }
        for m in all_history
        if m.timestamp.date() == today
    ]

# Utility to build user profile summary
def _build_profile_str(user) -> str:
    profile = user.model_dump()
    return (
        f"Age: {profile['age']} yrs, "
        f"Weight: {profile['weight']} kg, "
        f"Health cond.: {profile.get('health_conditions','none')}, "
        f"Diet prefs: {profile.get('diet_preferences','none')}, "
        f"Goals: {profile.get('goals','none')}."
    )

def detect_food_items(image_path: str) -> List[str]:
    """
    Uses OpenAI GPT-4o with Structured Outputs to detect food items as a JSON array.
    """
    with open(image_path, "rb") as img_file:
        image_bytes = img_file.read()
    image_b64 = base64.b64encode(image_bytes).decode()
    schema = {
        "type": "object",
        "properties": {
            "food_items": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "required": ["food_items"],
        "additionalProperties": False,
    }
    messages = [{
        "role": "user",
        "content": [
            {"type": "input_text", "text": "List all food items you see in this photo."},
            {"type": "input_image", "image_url": f"data:image/jpeg;base64,{image_b64}"}
        ]
    }]
    content = call_openai(messages, schema, "food_items", max_output_tokens=200)
    try:
        obj = json.loads(content)
        return obj["food_items"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse food items: {e}")


def estimate_nutrition(food_items: List[str]) -> Dict[str, Any]:
    """
    Uses OpenAI GPT-4o with Structured Outputs (JSON Schema) to estimate nutrition.
    """
    # Prepare JSON schema
    schema = {
        "type": "object",
        "properties": {
            "calories": {"type": "integer"},
            "protein": {"type": "integer"},
            "carbs": {"type": "integer"},
            "fat": {"type": "integer"},
        },
        "required": ["calories", "protein", "carbs", "fat"],
        "additionalProperties": False,
    }
    messages = [
        {"role": "system", "content": "You are a knowledgeable nutrition assistant."},
        {"role": "user", "content": f"Estimate total nutrition for these items as accurately as possible: {food_items}."}
    ]
    content = call_openai(messages, schema, "nutrition_info", temperature=0.2)
    try:
        nutrition = NutritionInfo.model_validate_json(content)
        return nutrition.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Nutrition JSON validation failed: {e}")


async def analyze_meal(db: Session, user_id: int, file: UploadFile) -> Dict[str, Any]:
    # Validate user exists
    user = get_user(db, user_id)

    # Save uploaded image
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(upload_dir, filename)
    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    # Detect food items and estimate nutrition
    items = detect_food_items(file_path)
    food_items = {"items": items}
    nutrition_info = estimate_nutrition(items)

    # Prepare today's meals for next meal advice
    todays_meals = _get_todays_meals(get_meal_history(db, user_id))

    # Build profile summary
    profile_str = _build_profile_str(user)

    # Summarize macro totals
    macro_totals = {
        "calories": sum(m["nutrition_info"]["calories"] for m in todays_meals),
        "protein": sum(m["nutrition_info"]["protein"] for m in todays_meals),
        "carbs":    sum(m["nutrition_info"]["carbs"] for m in todays_meals),
        "fat":      sum(m["nutrition_info"]["fat"] for m in todays_meals)
    }

    # Compute remaining macros based on daily goals
    daily_goals = {
        "calories": DAILY_CALORIES,
        "protein": DAILY_PROTEIN,
        "carbs": DAILY_CARBS,
        "fat": DAILY_FAT,
    }
    macro_remaining = {k: daily_goals[k] - macro_totals[k] for k in macro_totals}

    # Prepare prompt for AI
    prompt = (
        "You are NutriCoach, your friendly personal nutrition coach. "
        f"{profile_str} "
        f"Daily goals: {json.dumps(daily_goals)}. "
        f"Intake so far: {json.dumps(macro_totals)}. "
        f"Remaining macros: {json.dumps(macro_remaining)}. "
        f"Meals today so far: {json.dumps(todays_meals)}. "
        f"Your current meal: {json.dumps(food_items)} with nutrition {json.dumps(nutrition_info)}. "
        "First, acknowledge this meal—highlight positives, remind about mindful eating, and how it fits into the day's macro balance. "
        "Next, recommend the next meal: specify foods, approximate portions, and explain how it optimally balances the remaining macros and supports personal goals. "
        "Respond strictly in JSON with keys: advice, reason, next_meal."
    )

    # Generate advice using Structured Outputs (JSON Schema)
    advice_schema = {
        "type": "object",
        "properties": {
            "advice": {"type": "string"},
            "reason": {"type": "string"},
            "next_meal": {"type": "string"},
        },
        "required": ["advice", "reason", "next_meal"],
        "additionalProperties": False,
    }
    messages = [
        {"role": "system", "content": "You are a friendly personal health coach. Speak with empathy and encouragement."},
        {"role": "user", "content": prompt}
    ]
    content = call_openai(messages, advice_schema, "advice_response", temperature=0.7)
    try:
        feedback = AdviceResponse.model_validate_json(content).model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Advice JSON validation failed: {e}")

    # Persist meal record
    meal = Meal(
        user_id=user_id,
        image_path=file_path,
        food_items=food_items,
        nutrition_info=nutrition_info,
        feedback=feedback,
    )
    db.add(meal)
    db.commit()
    db.refresh(meal)
    return {
        "id": meal.id,
        "user_id": meal.user_id,
        "timestamp": meal.timestamp.isoformat(),
        "image_path": meal.image_path,
        "food_items": meal.food_items,
        "nutrition_info": meal.nutrition_info,
        "feedback": meal.feedback
    }


def get_meal_history(db: Session, user_id: int) -> List[MealRead]:
    meals = db.query(Meal).filter(Meal.user_id == user_id).order_by(Meal.timestamp.desc()).all()
    return [MealRead.from_orm(m) for m in meals]


# Suggest meal using fridge items and meal history
def suggest_meal(db: Session, user_id: int, fridge_items: List[str]) -> Dict[str, Any]:
    # Validate user exists
    user = get_user(db, user_id)
    # Prepare today's meal history
    all_history = get_meal_history(db, user_id)
    todays_meals = _get_todays_meals(all_history)
    # Build user profile summary
    profile_str = _build_profile_str(user)
    # Construct prompt
    prompt = (
        "You are NutriCoach, your friendly personal nutrition coach. "
        f"{profile_str} "
        f"Meals today so far: {json.dumps(todays_meals)}. "
        f"Available ingredients in fridge: {json.dumps(fridge_items)}. "
        "Suggest a meal that uses as many available items as possible, "
        "and list any missing ingredients you recommend ordering. "
        "Respond strictly in JSON with keys: recommendation, missing_ingredients, reason."
    )
    # Define output schema
    suggestion_schema = {
        "type": "object",
        "properties": {
            "recommendation": {"type": "string"},
            "missing_ingredients": {"type": "array", "items": {"type": "string"}},
            "reason": {"type": "string"},
        },
        "required": ["recommendation", "missing_ingredients", "reason"],
        "additionalProperties": False,
    }
    messages = [
        {"role": "system", "content": "You are a friendly personal health coach. Speak with empathy and encouragement."},
        {"role": "user", "content": prompt}
    ]
    content = call_openai(messages, suggestion_schema, "meal_suggestion", temperature=0.7)
    try:
        suggestion = MealSuggestion.model_validate_json(content).model_dump()
        return suggestion
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Meal suggestion JSON validation failed: {e}")
