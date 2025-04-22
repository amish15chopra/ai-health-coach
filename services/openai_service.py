import os
from typing import List, Dict, Any, Optional
from openai import OpenAI

# Initialize OpenAI Responses client
openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)

def call_openai(
    messages: List[Dict[str, Any]],
    schema: Dict[str, Any],
    name: str,
    temperature: float = 0.0,
    max_output_tokens: Optional[int] = None
) -> str:
    """
    Helper to call the OpenAI Responses API with structured JSON schema output.
    """
    params: Dict[str, Any] = {
        "model": "gpt-4o",
        "input": messages,
        "text": {"format": {"type": "json_schema", "name": name, "schema": schema, "strict": True}},
        "temperature": temperature,
    }
    if max_output_tokens is not None:
        params["max_output_tokens"] = max_output_tokens

    response = client.responses.create(**params)
    return response.output_text
