from typing import Optional

import requests


class HelpDeskError(Exception):
    """Base exception for all Motadata HelpDesk client errors."""


class HelpDeskValidationError(HelpDeskError, ValueError):
    """Raised when request parameters or data validation fails locally."""


class HelpDeskAPIError(HelpDeskError, requests.HTTPError):
    """Raised when an API request returns an HTTP error response.

    Subclasses requests.HTTPError for full backwards-compatibility with
    code catching requests.HTTPError.
    """

    def __init__(
        self,
        message: str,
        response: Optional[requests.Response] = None,
        status_code: Optional[int] = None,
        error_details: Optional[dict] = None,
    ):
        super().__init__(message, response=response)
        self.message = message
        self.response = response
        self.status_code = status_code or (response.status_code if response is not None else None)
        self.error_details = error_details or {}

    def __str__(self) -> str:
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message


class HelpDeskAuthError(HelpDeskAPIError):
    """Raised when authentication fails (invalid credentials, expired token, etc.)."""


class HelpDeskNotFoundError(HelpDeskAPIError):
    """Raised when the requested resource (ticket, conversation, technician) is not found."""
