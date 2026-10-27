"""Motadata ServiceOps HelpDesk Python SDK."""

from .auth import APIKeyAuth, BaseAuth, BearerTokenAuth, OAuth2Auth
from .client import HelpDeskClient
from .enums import ConversationState, ConversationType, StatusEnum
from .exceptions import (
    HelpDeskAPIError,
    HelpDeskAuthError,
    HelpDeskError,
    HelpDeskNotFoundError,
    HelpDeskValidationError,
)
from .models import (
    Conversation,
    ConversationSearchResponse,
    HelpTicket,
    SearchResponse,
    Technician,
)
from .query_builder import QueryBuilder
from .templates import render_helpdesk_template

__version__ = "0.1.0"

__all__ = [
    "HelpDeskClient",
    "BaseAuth",
    "APIKeyAuth",
    "OAuth2Auth",
    "BearerTokenAuth",
    "QueryBuilder",
    "StatusEnum",
    "ConversationType",
    "ConversationState",
    "HelpDeskError",
    "HelpDeskAPIError",
    "HelpDeskAuthError",
    "HelpDeskNotFoundError",
    "HelpDeskValidationError",
    "Technician",
    "HelpTicket",
    "SearchResponse",
    "Conversation",
    "ConversationSearchResponse",
    "render_helpdesk_template",
    "__version__",
]
