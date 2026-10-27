import logging
import os
import time
from typing import Dict, Optional

import requests
from requests.auth import AuthBase, HTTPBasicAuth

from .exceptions import HelpDeskAuthError

logger = logging.getLogger(__name__)


class BaseAuth(AuthBase):
    """Abstract base class for ServiceOps authentication."""

    def get_headers(
        self,
        base_url: str = "",
        session: Optional[requests.Session] = None,
    ) -> Dict[str, str]:
        """Return HTTP headers dictionary required for authentication."""
        raise NotImplementedError("Subclasses must implement get_headers()")

    def apply(
        self,
        headers: Dict[str, str],
        base_url: str = "",
        session: Optional[requests.Session] = None,
    ) -> None:
        """Inject authentication headers into an existing headers dictionary."""
        headers.update(self.get_headers(base_url=base_url, session=session))

    def __call__(self, r: requests.PreparedRequest) -> requests.PreparedRequest:
        """Allow using this auth class directly with requests sessions."""
        for key, value in self.get_headers().items():
            r.headers[key] = value
        return r


class APIKeyAuth(BaseAuth):
    """Authentication using Motadata ServiceOps API Key.

    Configured in ServiceOps Admin > Automation > Integrations > API Integration.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        prefix: str = "Apikey",
    ):
        self.api_key = api_key or os.getenv("MOTADATA_API_KEY") or os.getenv("API_KEY")
        self.prefix = prefix
        if not self.api_key:
            raise HelpDeskAuthError(
                "API key must be provided or set in MOTADATA_API_KEY / API_KEY."
            )

    def get_headers(
        self,
        base_url: str = "",
        session: Optional[requests.Session] = None,
    ) -> Dict[str, str]:
        prefix_part = f"{self.prefix} " if self.prefix else ""
        return {"Authorization": f"{prefix_part}{self.api_key}".strip()}

    def __repr__(self) -> str:
        return f"<APIKeyAuth prefix={self.prefix!r}>"


class OAuth2Auth(BaseAuth):
    """Authentication using OAuth 2.0 Password Grant with Client ID & Secret.

    Configured in ServiceOps Admin > Automation > Integrations > Rest Integration.
    Automatically retrieves, caches, and refreshes access tokens.
    """

    DEFAULT_TOKEN_AGE = 7200  # 2 hours

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        base_url: Optional[str] = None,
        token_age: int = DEFAULT_TOKEN_AGE,
        verify_ssl: bool = False,
        timeout: float = 30.0,
    ):
        self.client_id = client_id or os.getenv("MOTADATA_CLIENT_ID") or os.getenv("API_CLIENT_ID")
        self.client_secret = (
            client_secret or os.getenv("MOTADATA_CLIENT_SECRET") or os.getenv("API_CLIENT_SECRET")
        )
        self.username = username or os.getenv("MOTADATA_USERNAME") or os.getenv("API_USERNAME")
        self.password = password or os.getenv("MOTADATA_PASSWORD") or os.getenv("API_PASSWORD")
        self.base_url = (base_url or "").rstrip("/")
        self.token_age = token_age
        self.verify_ssl = verify_ssl
        self.timeout = timeout

        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[float] = None

    def _generate_token(
        self,
        base_url: str,
        session: Optional[requests.Session] = None,
    ) -> str:
        url_target = (base_url or self.base_url).rstrip("/")
        if not url_target:
            raise HelpDeskAuthError("base_url is required to acquire an OAuth2 token.")

        if not (self.username and self.password and self.client_id and self.client_secret):
            raise HelpDeskAuthError(
                "Missing OAuth2 credentials (username, password, client_id, client_secret) "
                "required to generate an access token."
            )

        auth_url = f"{url_target}/api/oauth/token"
        payload = {
            "username": self.username,
            "password": self.password,
            "grant_type": "password",
        }
        headers = {"Cookie": "Path=/"}
        basic_auth = HTTPBasicAuth(self.client_id, self.client_secret)
        req_session = session or requests.Session()

        try:
            response = req_session.post(
                auth_url,
                data=payload,
                auth=basic_auth,
                headers=headers,
                verify=self.verify_ssl,
                timeout=self.timeout,
            )
            response.raise_for_status()
            token_data = response.json()
            token = token_data.get("access_token")
            if not token:
                raise HelpDeskAuthError(
                    f"Authentication response missing 'access_token': {token_data}",
                    response=response,
                )
            return token
        except requests.HTTPError as exc:
            raise HelpDeskAuthError(
                f"Failed to acquire OAuth2 access token: {exc}",
                response=exc.response,
                status_code=exc.response.status_code if exc.response is not None else None,
            ) from exc
        except requests.RequestException as exc:
            raise HelpDeskAuthError(f"OAuth2 token request failed: {exc}") from exc

    def get_token(
        self,
        base_url: str = "",
        session: Optional[requests.Session] = None,
    ) -> str:
        """Get a valid access token, generating or refreshing if necessary."""
        effective_base_url = (base_url or self.base_url).rstrip("/")
        if not self._access_token or (
            self._token_expires_at and time.time() > self._token_expires_at
        ):
            self._access_token = self._generate_token(effective_base_url, session=session)
            self._token_expires_at = time.time() + self.token_age
        return self._access_token

    def get_headers(
        self,
        base_url: str = "",
        session: Optional[requests.Session] = None,
    ) -> Dict[str, str]:
        token = self.get_token(base_url=base_url, session=session)
        return {"Authorization": f"Bearer {token}"}

    def __repr__(self) -> str:
        return f"<OAuth2Auth username={self.username!r} client_id={self.client_id!r}>"


class BearerTokenAuth(BaseAuth):
    """Direct static Bearer token authentication."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("MOTADATA_ACCESS_TOKEN")
        if not self.token:
            raise HelpDeskAuthError(
                "Bearer token must be provided or set in MOTADATA_ACCESS_TOKEN."
            )

    def get_headers(
        self,
        base_url: str = "",
        session: Optional[requests.Session] = None,
    ) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def __repr__(self) -> str:
        return "<BearerTokenAuth token=***>"
