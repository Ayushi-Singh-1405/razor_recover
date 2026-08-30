#!/usr/bin/env python3
"""LLM Provider module for structured decisions with provider fallback.

Provider chain (in order):
    1. OpenRouter - OPENROUTER_API_KEY / OPENROUTER_BASE_URL / OPENROUTER_MODEL

Puter and AgentRouter were previously configured as primary providers but
have been removed from the chain (dead endpoints: Puter requires a paid
subscription, AgentRouter rejects the configured key). The chain itself
stays provider-agnostic: re-enabling a provider is a config-block change
in _get_provider_configs(), not a code change elsewhere.

get_structured_decision(prompt, schema) tries each configured provider in
order. Every response is validated against the caller's JSON schema
before being returned; the first valid structured decision wins. If all
configured providers fail, an LLMProviderError summarizing the failures
(without secrets) is raised.

Scope note: this module is responsible for obtaining and validating an
LLM decision only. What the agent/policy layer does when every LLM
attempt fails (safe gated override, escalation, etc.) is decided in
run_agent.py and intentionally NOT handled here.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30  # seconds

# OpenRouter (OpenAI-compatible endpoint)
OPENROUTER_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
# Default cheap/free model supporting structured JSON. Used only when
# OPENROUTER_MODEL is unset (kept for backward compatibility).
DEFAULT_MODEL = "google/gemini-2.0-flash-001"

COMPLETIONS_PATH = "/chat/completions"

# Human-readable labels used in aggregated error summaries.
PROVIDER_LABELS = {
    "openrouter": "OpenRouter failed",
}


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    pass


class LLMAPIError(LLMProviderError):
    """Raised when a provider API call fails (network, auth, HTTP errors)."""
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


def _build_system_instruction(schema: Dict[str, Any]) -> str:
    """Build the system instruction enforcing strict JSON output."""
    return (
        "You are a structured decision engine for RecoverAI. "
        "You must respond with ONLY a valid JSON object strictly conforming to the following JSON schema:\n"
        f"{json.dumps(schema, indent=2)}\n\n"
        "Rules:\n"
        "1. Output valid JSON only.\n"
        "2. Do NOT wrap in markdown fences or backticks (e.g. no ```json).\n"
        "3. Do NOT include explanations, preamble, or commentary outside the JSON.\n"
        "4. Include all required keys and match all specified types and enums exactly."
    )


def _call_provider(
    provider_name: str,
    api_key: str,
    base_url: str,
    model: str,
    prompt: str,
    schema: Dict[str, Any],
) -> Dict[str, Any]:
    """Send one structured-decision request to a single OpenAI-compatible provider.

    Performs, in order:
      1. build the request (system instruction embeds the JSON schema)
      2. send the request
      3. extract message.content from the response wrapper
      4. clean markdown JSON fences
      5. parse JSON
      6. validate against the schema
      7. return the validated dict

    Args:
        provider_name: Logical provider identifier (e.g. 'agentrouter').
        api_key: Bearer token for the provider. Never logged.
        base_url: OpenAI-compatible base URL (e.g. https://co.agentrouter.org/v1).
        model: Model identifier to request.
        prompt: The task instruction and context for the LLM.
        schema: The JSON schema definition that the response must conform to.

    Returns:
        Validated dictionary matching the schema.

    Raises:
        LLMAPIError: On network failure, timeout, non-200 response, or
            unparseable/empty response wrapper.
        LLMJSONDecodeError: If the model output cannot be parsed as JSON.
        LLMSchemaValidationError: If the parsed output violates the schema.
    """
    url = base_url.rstrip("/") + COMPLETIONS_PATH

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/RecoverAI",
        "X-Title": "RecoverAI Decision Engine",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _build_system_instruction(schema)},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        # json_object mode + local schema validation: neither provider is
        # assumed to support arbitrary JSON Schema response formats.
        "response_format": {
            "type": "json_object"
        },
    }

    logger.info("LLM provider=%s model=%s", provider_name, model)

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.Timeout as e:
        raise LLMAPIError(
            f"{provider_name} API request timed out after {REQUEST_TIMEOUT}s: {e}"
        ) from e
    except requests.exceptions.RequestException as e:
        raise LLMAPIError(f"{provider_name} API request failed: {e}") from e

    if response.status_code != 200:
        error_detail = response.text
        try:
            err_json = response.json()
            if "error" in err_json:
                error_detail = err_json["error"].get("message", response.text)
        except Exception:
            pass
        raise LLMAPIError(
            f"{provider_name} API returned HTTP {response.status_code} (model={model}): {error_detail}"
        )

    try:
        resp_json = response.json()
    except Exception as e:
        raise LLMAPIError(f"Failed to parse {provider_name} response wrapper as JSON: {e}") from e

    choices = resp_json.get("choices", [])
    if not choices or not choices[0].get("message", {}).get("content"):
        raise LLMAPIError(f"{provider_name} returned empty choices in response: {resp_json}")

    raw_content = choices[0]["message"]["content"]
    cleaned_content = _clean_json_text(raw_content)

    try:
        parsed_data = json.loads(cleaned_content)
    except json.JSONDecodeError as e:
        raise LLMJSONDecodeError(
            f"[{provider_name}] Failed to parse LLM output as JSON: {e}\nRaw content:\n{raw_content}"
        ) from e

    if not isinstance(parsed_data, dict):
        raise LLMSchemaValidationError(
            f"[{provider_name}] Expected JSON object output, got {type(parsed_data).__name__}: {parsed_data}"
        )

    validate_response_schema(parsed_data, schema)

    return parsed_data


def _get_provider_configs() -> List[Dict[str, str]]:
    """Build the ordered provider chain from environment configuration.

    Currently OpenRouter only. Puter and AgentRouter were removed as dead
    endpoints; re-enabling a provider means appending a config block here.
    Providers without credentials are skipped (with a logged warning).
    """
    configs: List[Dict[str, str]] = []

    or_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if or_key:
        configs.append({
            "name": "openrouter",
            "api_key": or_key,
            "base_url": os.getenv("OPENROUTER_BASE_URL", "").strip() or OPENROUTER_DEFAULT_BASE_URL,
            "model": os.getenv("OPENROUTER_MODEL", "").strip() or DEFAULT_MODEL,
        })
    else:
        logger.warning("LLM provider=openrouter skipped: OPENROUTER_API_KEY is not set")

    return configs


def get_structured_decision(prompt: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    """Request a structured JSON decision via the provider chain and validate it.

    Tries each configured provider in order (currently OpenRouter only).
    The first provider that returns a schema-valid JSON object wins;
    remaining providers are not called. Schema validation is enforced on
    every provider's response - invalid JSON or schema violations never
    pass silently; they trigger fallback (if another provider is
    configured).

    Args:
        prompt: The task instruction and context for the LLM.
        schema: The JSON schema definition that the response must conform to.

    Returns:
        Validated dictionary matching the schema.

    Raises:
        LLMAPIError: If no provider is configured, or if the only configured
            provider fails at the API/transport level (missing key, network
            failure, timeout, non-200 response).
        LLMProviderError: If multiple providers are configured and all of
            them fail; the message summarizes each failure without secrets.
        LLMJSONDecodeError: If a single configured provider returns
            unparseable model output (preserved for backward compatibility).
        LLMSchemaValidationError: If a single configured provider returns
            schema-violating output (preserved for backward compatibility).
    """
    providers = _get_provider_configs()
    if not providers:
        raise LLMAPIError(
            "No LLM provider configured: set AGENTROUTER_API_KEY (primary) "
            "and/or OPENROUTER_API_KEY (fallback) in your environment or .env file."
        )

    failures: List[str] = []
    last_error: Optional[LLMProviderError] = None

    for idx, cfg in enumerate(providers):
        try:
            decision = _call_provider(
                provider_name=cfg["name"],
                api_key=cfg["api_key"],
                base_url=cfg["base_url"],
                model=cfg["model"],
                prompt=prompt,
                schema=schema,
            )
            logger.info("LLM provider=%s succeeded", cfg["name"])
            return decision
        except LLMProviderError as err:
            last_error = err
            label = PROVIDER_LABELS.get(cfg["name"], f"{cfg['name']} failed")
            failures.append(f"{label}: {err}")
            logger.warning("LLM provider=%s failed: %s", cfg["name"], err)
            remaining = providers[idx + 1:]
            if remaining:
                logger.info("Falling back to %s", remaining[0]["name"])

    if len(failures) == 1:
        # Single-provider chain: re-raise the original error type/message
        # so existing callers keep seeing LLMAPIError / LLMJSONDecodeError /
        # LLMSchemaValidationError exactly as before.
        raise last_error

    raise LLMProviderError("All LLM providers failed.\n" + "\n".join(failures))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
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

    or_set = bool(os.getenv("OPENROUTER_API_KEY", "").strip())
    print(f"OpenRouter configured:  {or_set} "
          f"(model={os.getenv('OPENROUTER_MODEL', '').strip() or DEFAULT_MODEL})")

    print("\nTesting schema validator with synthetic samples...")
    sample_valid = {
        "sentiment": "positive",
        "confidence": 0.98,
        "reason": "Customer expressed satisfaction with swift recovery link",
    }
    validate_response_schema(sample_valid, test_schema)
    print("Schema validation passed for synthetic sample!")

    sample_invalid = {"sentiment": "unknown", "confidence": "high"}
    try:
        validate_response_schema(sample_invalid, test_schema)
        print("ERROR: Invalid sample did not fail validation")
    except LLMSchemaValidationError as err:
        print(f"Schema validator correctly rejected invalid sample: {err}")

    if not (ar_set or or_set):
        print("\nNo provider API keys set - offline validation only.")
        print("Set AGENTROUTER_API_KEY and/or OPENROUTER_API_KEY in .env and rerun for a live test.")
    else:
        print("\nSending ONE test prompt through the provider chain (primary -> fallback)...")
        try:
            result = get_structured_decision(test_prompt, test_schema)
            print("\nLive Result:")
            print(json.dumps(result, indent=2))
            print("\nSUCCESS: Structured decision received and schema validated.")
        except LLMProviderError as err:
            print(f"\nLLM Provider Error: {err}")
