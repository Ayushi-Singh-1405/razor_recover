#!/usr/bin/env python3
"""LLM Provider module for structured decisions using OpenRouter.

Provides get_structured_decision(prompt, schema) which requests and validates
structured JSON output from OpenRouter's OpenAI-compatible chat completion API.
"""

import json
import os
import re
from typing import Any, Dict

import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Default cheap/free model supporting structured JSON.
# Can be swapped via OPENROUTER_MODEL environment variable without code changes
# (e.g., 'google/gemini-2.0-flash-001', 'meta-llama/llama-3.3-70b-instruct:free', etc.)
DEFAULT_MODEL = "google/gemini-2.0-flash-001"
REQUEST_TIMEOUT = 30  # seconds


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    pass


class LLMAPIError(LLMProviderError):
    """Raised when the OpenRouter API call fails (network, auth, HTTP errors)."""
    pass


class LLMJSONDecodeError(LLMProviderError):
    """Raised when the model response is not valid JSON."""
    pass


class LLMSchemaValidationError(LLMProviderError):
    """Raised when the model response fails schema validation."""
    pass


def _validate_value(key_path: str, val: Any, prop_def: Dict[str, Any]) -> None:
    """Validate a single value against a property definition in JSON schema."""
    expected_type = prop_def.get("type")
    
    if expected_type == "string":
        if not isinstance(val, str):
            raise LLMSchemaValidationError(
                f"Field '{key_path}' expected string, got {type(val).__name__} ({val!r})"
            )
    elif expected_type == "number":
        # In Python, bool is a subclass of int, so check not bool
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise LLMSchemaValidationError(
                f"Field '{key_path}' expected number, got {type(val).__name__} ({val!r})"
            )
    elif expected_type == "integer":
        if isinstance(val, bool) or not isinstance(val, int):
            raise LLMSchemaValidationError(
                f"Field '{key_path}' expected integer, got {type(val).__name__} ({val!r})"
            )
    elif expected_type == "boolean":
        if not isinstance(val, bool):
            raise LLMSchemaValidationError(
                f"Field '{key_path}' expected boolean, got {type(val).__name__} ({val!r})"
            )
    elif expected_type == "array":
        if not isinstance(val, list):
            raise LLMSchemaValidationError(
                f"Field '{key_path}' expected array, got {type(val).__name__} ({val!r})"
            )
        item_schema = prop_def.get("items")
        if item_schema and isinstance(item_schema, dict):
            for i, item in enumerate(val):
                _validate_value(f"{key_path}[{i}]", item, item_schema)
    elif expected_type == "object":
        if not isinstance(val, dict):
            raise LLMSchemaValidationError(
                f"Field '{key_path}' expected object, got {type(val).__name__} ({val!r})"
            )
        _validate_object(val, prop_def, key_path)

    # Enum check
    enum_values = prop_def.get("enum")
    if enum_values is not None:
        if val not in enum_values:
            raise LLMSchemaValidationError(
                f"Field '{key_path}' value {val!r} not in allowed enum: {enum_values}"
            )


def _validate_object(data: Dict[str, Any], schema: Dict[str, Any], prefix: str = "") -> None:
    """Validate a dictionary against an object schema."""
    if not isinstance(data, dict):
        raise LLMSchemaValidationError(
            f"Expected JSON object at '{prefix or 'root'}', got {type(data).__name__}"
        )

    required = schema.get("required", [])
    for req_key in required:
        if req_key not in data:
            path = f"{prefix}.{req_key}" if prefix else req_key
            raise LLMSchemaValidationError(f"Missing required field '{path}' in LLM response")

    properties = schema.get("properties", {})
    for key, prop_def in properties.items():
        if key in data and isinstance(prop_def, dict):
            path = f"{prefix}.{key}" if prefix else key
            _validate_value(path, data[key], prop_def)


def validate_response_schema(data: Any, schema: Dict[str, Any]) -> None:
    """Validate parsed JSON data against the given JSON schema."""
    if schema.get("type") == "object" or "properties" in schema:
        _validate_object(data, schema)
    else:
        _validate_value("root", data, schema)


def _clean_json_text(text: str) -> str:
    """Strip markdown code block fences and trailing text from LLM response."""
    text = text.strip()
    # Match ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text


def get_structured_decision(prompt: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    """Request a structured JSON decision from OpenRouter and validate it against schema.

    Args:
        prompt: The task instruction and context for the LLM.
        schema: The JSON schema definition that the response must conform to.

    Returns:
        Validated dictionary matching the schema.

    Raises:
        LLMAPIError: On missing API key, network failure, timeout, or non-200 response.
        LLMJSONDecodeError: If response text cannot be parsed as JSON.
        LLMSchemaValidationError: If parsed JSON violates required keys, types, or enums.
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise LLMAPIError(
            "OPENROUTER_API_KEY environment variable is not set. "
            "Please set OPENROUTER_API_KEY in your environment or .env file."
        )

    model = os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/RecoverAI",
        "X-Title": "RecoverAI Decision Engine",
    }

    system_instruction = (
        "You are a structured decision engine for RecoverAI. "
        "You must respond with ONLY a valid JSON object strictly conforming to the following JSON schema:\n"
        f"{json.dumps(schema, indent=2)}\n\n"
        "Rules:\n"
        "1. Output valid JSON only.\n"
        "2. Do NOT wrap in markdown fences or backticks (e.g. no ```json).\n"
        "3. Do NOT include explanations, preamble, or commentary outside the JSON.\n"
        "4. Include all required keys and match all specified types and enums exactly."
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        # Use json_schema response_format if possible, fallback to json_object
        "response_format": {
            "type": "json_object"
        },
    }

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.Timeout as e:
        raise LLMAPIError(f"OpenRouter API request timed out after {REQUEST_TIMEOUT}s: {e}") from e
    except requests.exceptions.RequestException as e:
        raise LLMAPIError(f"OpenRouter API request failed: {e}") from e

    if response.status_code != 200:
        error_detail = response.text
        try:
            err_json = response.json()
            if "error" in err_json:
                error_detail = err_json["error"].get("message", response.text)
        except Exception:
            pass
        raise LLMAPIError(
            f"OpenRouter API returned HTTP {response.status_code} ({model}): {error_detail}"
        )

    try:
        resp_json = response.json()
    except Exception as e:
        raise LLMAPIError(f"Failed to parse OpenRouter response wrapper as JSON: {e}") from e

    choices = resp_json.get("choices", [])
    if not choices or not choices[0].get("message", {}).get("content"):
        raise LLMAPIError(f"OpenRouter returned empty choices in response: {resp_json}")

    raw_content = choices[0]["message"]["content"]
    cleaned_content = _clean_json_text(raw_content)

    try:
        parsed_data = json.loads(cleaned_content)
    except json.JSONDecodeError as e:
        raise LLMJSONDecodeError(
            f"Failed to parse LLM output as JSON: {e}\nRaw content:\n{raw_content}"
        ) from e

    if not isinstance(parsed_data, dict):
        raise LLMSchemaValidationError(
            f"Expected JSON object output, got {type(parsed_data).__name__}: {parsed_data}"
        )

    validate_response_schema(parsed_data, schema)

    return parsed_data


if __name__ == "__main__":
    print("--- Testing backend/llm_provider.py ---")

    test_schema = {
        "type": "object",
        "properties": {
            "sentiment": {
                "type": "string",
                "enum": ["positive", "negative", "neutral"],
                "description": "Classification of sentiment",
            },
            "confidence": {
                "type": "number",
                "description": "Confidence score between 0.0 and 1.0",
            },
            "reason": {
                "type": "string",
                "description": "Brief explanation for the rating",
            },
        },
        "required": ["sentiment", "confidence", "reason"],
    }

    test_prompt = (
        "Classify the sentiment of the following customer feedback:\n"
        "'The recovery payment link arrived immediately and resolved my checkout issue in seconds!'"
    )

    api_key_set = bool(os.getenv("OPENROUTER_API_KEY", "").strip())
    model_name = os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)
    print(f"Model: {model_name}")
    print(f"OPENROUTER_API_KEY set: {api_key_set}")

    if not api_key_set:
        print("\nNote: OPENROUTER_API_KEY is not set.")
        print("Testing schema validator with synthetic sample...")
        sample_valid = {
            "sentiment": "positive",
            "confidence": 0.98,
            "reason": "Customer expressed satisfaction with swift recovery link",
        }
        validate_response_schema(sample_valid, test_schema)
        print("Schema validation passed for synthetic sample!")

        # Verify invalid sample raises exception
        sample_invalid = {"sentiment": "unknown", "confidence": "high"}
        try:
            validate_response_schema(sample_invalid, test_schema)
            print("ERROR: Invalid sample did not fail validation")
        except LLMSchemaValidationError as err:
            print(f"Schema validator correctly rejected invalid sample: {err}")

        print("\nTo test live LLM call, set OPENROUTER_API_KEY in .env and rerun.")
    else:
        print("\nSending test prompt to OpenRouter...")
        try:
            result = get_structured_decision(test_prompt, test_schema)
            print("\nLive OpenRouter Result:")
            print(json.dumps(result, indent=2))
            print("\nSUCCESS: Structured decision received and schema validated.")
        except LLMProviderError as err:
            print(f"\nLLM Provider Error: {err}")
