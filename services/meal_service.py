import os
import uuid
import json
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, UploadFile
from models import Meal
from schemas import AdviceResponse, MealRead
from services.user_service import get_user
import openai

# Set your OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

import base64

def detect_food_items(image_path: str) -> List[str]:
    """
    Uses OpenAI GPT-4o API to detect food items in the image.
    """
    with open(image_path, "rb") as img_file:
        image_bytes = img_file.read()
    image_b64 = base64.b64encode(image_bytes).decode()
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "List all food items you see in this photo. Respond ONLY with a JSON array of strings. Do not include any explanation or markdown."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                ]
            }
        ],
        max_tokens=200,
    )
    message = response.choices[0].message.content
    import re
    try:
        items = json.loads(message)
        if isinstance(items, list):
            return items
        if isinstance(items, dict):
            for key in ["items", "foods", "food_items"]:
                if key in items and isinstance(items[key], list):
                    return items[key]
        raise ValueError("Unexpected response format")
    except Exception:
        # Try to extract a JSON array using regex
        match = re.search(r'(\[.*?\])', message, re.DOTALL)
        if match:
            try:
                items = json.loads(match.group(1))
                if isinstance(items, list):
                    return items
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Failed to parse food items from AI vision response: {message}")


def estimate_nutrition(food_items: List[str]) -> Dict[str, Any]:
    """
    Uses OpenAI GPT-4o to estimate nutrition for given food items with fallback.
    """
    try:
        prompt = (
            f"Estimate the total nutrition for these food items: {food_items}. "
            "Respond only with a JSON object with keys: calories (kcal), protein (grams), carbs (grams), fat (grams)."
        )
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a knowledgeable nutrition assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )
        data = json.loads(response.choices[0].message.content)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    # Fallback simple estimation
    calories = len(food_items) * 200
    protein = len(food_items) * 10
    carbs = len(food_items) * 30
    fat = len(food_items) * 5
    return {"calories": calories, "protein": protein, "carbs": carbs, "fat": fat}


async def analyze_meal(db: Session, user_id: int, file: UploadFile) -> MealRead:
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

    # Prepare prompt for AI
    user_profile = user.dict()
    prompt = (
        f"User profile: {json.dumps(user_profile)}."
        f" Food items: {json.dumps(food_items)}."
        f" Nutrition info: {json.dumps(nutrition_info)}."
        " Based on this, provide dietary advice in a friendly, coach-like tone. "
        "Speak like a personal health coach. "
        "Respond strictly in JSON with keys: advice, reason, next_meal."
    )
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a friendly personal health coach. Speak with empathy and encouragement."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
    )
    message = response.choices[0].message.content
    try:
        feedback = json.loads(message)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to parse AI response")

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
    return MealRead.from_orm(meal)


def get_meal_history(db: Session, user_id: int) -> List[MealRead]:
    meals = db.query(Meal).filter(Meal.user_id == user_id).order_by(Meal.timestamp.desc()).all()
    return [MealRead.from_orm(m) for m in meals]
