import os
import uuid
import json
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, UploadFile
from models import Meal
from schemas import AdviceResponse, MealRead, NutritionInfo
from services.user_service import get_user
from services.openai_service import call_openai
import base64
from datetime import date

# Set your OpenAI API key
openai_api_key = os.getenv("OPENAI_API_KEY")


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

    # Fetch today's meal history and prepare for next meal advice
    all_history = get_meal_history(db, user_id)
    today = date.today()
    todays_meals = []
    for m in all_history:
        if m.timestamp.date() == today:
            todays_meals.append({
                "timestamp": m.timestamp.isoformat(),
                "food_items": m.food_items,
                "nutrition_info": m.nutrition_info,
                "feedback": m.feedback.dict() if hasattr(m.feedback, "dict") else m.feedback
            })

    # Prepare prompt for AI
    user_profile = user.model_dump()
    prompt = (
        f"This is the user profile: {json.dumps(user_profile)}."
        f"The user had these meals today: {json.dumps(todays_meals)}."
        f"Current meal: {json.dumps(food_items)} with nutrition {json.dumps(nutrition_info)}."
        "taking into consideration the nutritional info of the meals the user had today, provide advice on the current meal the user is having, reason for that advice and the suggested next meal the user should had and why in a friendly, coach-like tone."
        "Speak like a friendly personal health coach."
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
