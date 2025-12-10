"""
Constants for Copilot integration
"""
import re
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

import httpx

from litellm.llms.base_llm.chat.transformation import BaseLLMException

# Constants
COPILOT_VERSION = "0.26.7"
EDITOR_PLUGIN_VERSION = f"copilot-chat/{COPILOT_VERSION}"
USER_AGENT = f"GitHubCopilotChat/{COPILOT_VERSION}"
API_VERSION = "2025-04-01"
GITHUB_COPILOT_API_BASE = "https://api.githubcopilot.com"

class GithubCopilotError(BaseLLMException):
    def __init__(
        self,
        status_code,
        message,
        request: Optional[httpx.Request] = None,
        response: Optional[httpx.Response] = None,
        headers: Optional[Union[httpx.Headers, dict]] = None,
        body: Optional[dict] = None,
    ):
        super().__init__(
            status_code=status_code,
            message=message,
            request=request,
            response=response,
            headers=headers,
            body=body,
        )


class GetDeviceCodeError(GithubCopilotError):
    pass


class GetAccessTokenError(GithubCopilotError):
    pass


class APIKeyExpiredError(GithubCopilotError):
    pass


class RefreshAPIKeyError(GithubCopilotError):
    pass


class GetAPIKeyError(GithubCopilotError):
    pass


def get_copilot_default_headers(api_key: str) -> dict:
    """
    Get default headers for GitHub Copilot Responses API.

    Based on copilot-api's header configuration.
    """
    return {
        "Authorization": f"Bearer {api_key}",
        "content-type": "application/json",
        "copilot-integration-id": "vscode-chat",
        "editor-version": "vscode/1.95.0",  # Fixed version for stability
        "editor-plugin-version": EDITOR_PLUGIN_VERSION,
        "user-agent": USER_AGENT,
        "openai-intent": "conversation-panel",
        "x-github-api-version": API_VERSION,
        "x-request-id": str(uuid4()),
        "x-vscode-user-agent-library-version": "electron-fetch",
    }


def sanitize_surrogate_characters(text: str) -> str:
    """
    Remove invalid UTF-16 surrogate characters from a string.

    Surrogate characters (U+D800 to U+DFFF) are used in UTF-16 encoding to represent
    characters outside the Basic Multilingual Plane (BMP). However, lone surrogates
    (high surrogates without low surrogates or vice versa) are invalid in UTF-8.

    This function removes:
    - High surrogates (U+D800-U+DBFF) not followed by low surrogates
    - Low surrogates (U+DC00-U+DFFF) not preceded by high surrogates

    Args:
        text: The string to sanitize

    Returns:
        The sanitized string with invalid surrogates removed
    """
    # Remove high surrogates not followed by low surrogates
    text = re.sub(r"[\uD800-\uDBFF](?![\uDC00-\uDFFF])", "", text)
    # Remove low surrogates not preceded by high surrogates
    text = re.sub(r"(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]", "", text)
    return text


def sanitize_messages_for_json_encoding(
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Sanitize message content to remove invalid surrogate characters that would
    cause JSON encoding errors when sending to GitHub Copilot.

    This handles the error:
    'utf-8' codec can't encode character '\\ud83c' in position X: surrogates not allowed

    Args:
        messages: List of message dictionaries with potential surrogate characters

    Returns:
        Messages with surrogate characters removed from string content
    """
    sanitized_messages: List[Dict[str, Any]] = []

    for message in messages:
        sanitized_message = _sanitize_message_content(message)
        sanitized_messages.append(sanitized_message)

    return sanitized_messages


def _sanitize_message_content(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively sanitize a single message's content for surrogate characters.

    Args:
        message: A message dictionary

    Returns:
        A new message dictionary with sanitized content
    """
    sanitized: Dict[str, Any] = {}

    for key, value in message.items():
        if key == "content":
            sanitized[key] = _sanitize_content_value(value)
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_message_content(value)
        elif isinstance(value, list):
            sanitized[key] = _sanitize_list_value(value)
        elif isinstance(value, str):
            sanitized[key] = sanitize_surrogate_characters(value)
        else:
            sanitized[key] = value

    return sanitized


def _sanitize_content_value(content: Any) -> Any:
    """
    Sanitize a content field value which can be a string, list, or other type.

    Args:
        content: The content value to sanitize

    Returns:
        Sanitized content value
    """
    if isinstance(content, str):
        return sanitize_surrogate_characters(content)
    elif isinstance(content, list):
        return _sanitize_list_value(content)
    elif isinstance(content, dict):
        return _sanitize_message_content(content)
    return content


def _sanitize_list_value(items: List[Any]) -> List[Any]:
    """
    Sanitize a list of items, handling content blocks recursively.

    Args:
        items: List of items to sanitize

    Returns:
        Sanitized list of items
    """
    sanitized_items: List[Any] = []

    for item in items:
        if isinstance(item, dict):
            sanitized_items.append(_sanitize_message_content(item))
        elif isinstance(item, str):
            sanitized_items.append(sanitize_surrogate_characters(item))
        elif isinstance(item, list):
            sanitized_items.append(_sanitize_list_value(item))
        else:
            sanitized_items.append(item)

    return sanitized_items
