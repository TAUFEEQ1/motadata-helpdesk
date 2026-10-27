import logging
import os
from typing import Any, Dict, List, Optional, Union

import requests
import urllib3

from .auth import APIKeyAuth, BaseAuth, BearerTokenAuth, OAuth2Auth
from .enums import ConversationState, ConversationType
from .exceptions import (
    HelpDeskAPIError,
    HelpDeskAuthError,
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

logger = logging.getLogger(__name__)

# Suppress insecure request warnings if verify_ssl is disabled
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class HelpDeskClient:
    """Client for Motadata ServiceOps REST API.

    Provides high-level methods for ticket management, conversation threads,
    technician details, query building, and response template rendering.

    Authentication supports:
      - Dedicated auth objects: APIKeyAuth, OAuth2Auth, BearerTokenAuth
      - Automatic auth resolution from client arguments or environment variables
    """

    DEFAULT_TOKEN_AGE = 7200  # 2 hours

    def __init__(
        self,
        base_url: Optional[str] = None,
        auth: Optional[BaseAuth] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        api_key: Optional[str] = None,
        access_token: Optional[str] = None,
        verify_ssl: Optional[bool] = None,
        timeout: float = 30.0,
        token_age: int = DEFAULT_TOKEN_AGE,
        session: Optional[requests.Session] = None,
    ):
        raw_url = (
            base_url
            or os.getenv("MOTADATA_BASE_URL")
            or os.getenv("MOTADATA_API_URL")
            or os.getenv("TICKET_API_URL")
            or ""
        )
        self.base_url = raw_url.rstrip("/")

        if verify_ssl is not None:
            self.verify_ssl = verify_ssl
        else:
            env_ssl = os.getenv("MOTADATA_VERIFY_SSL")
            self.verify_ssl = (
                False
                if env_ssl in ("0", "false", "False", "no")
                else (env_ssl is None or env_ssl in ("1", "true", "True", "yes"))
            )

        self.timeout = timeout
        self.token_age = token_age
        self.session = session or requests.Session()

        # Resolve authentication handler
        if auth is not None:
            self.auth: Optional[BaseAuth] = auth
        elif api_key or os.getenv("MOTADATA_API_KEY") or os.getenv("API_KEY"):
            self.auth = APIKeyAuth(api_key=api_key)
        elif access_token or os.getenv("MOTADATA_ACCESS_TOKEN"):
            self.auth = BearerTokenAuth(token=access_token)
        elif (
            client_id
            or client_secret
            or username
            or password
            or os.getenv("MOTADATA_CLIENT_ID")
            or os.getenv("API_CLIENT_ID")
        ):
            self.auth = OAuth2Auth(
                client_id=client_id,
                client_secret=client_secret,
                username=username,
                password=password,
                base_url=self.base_url,
                token_age=token_age,
                verify_ssl=self.verify_ssl,
                timeout=self.timeout,
            )
        else:
            self.auth = None

    @property
    def api_url(self) -> str:
        """Backwards compatibility alias for base_url."""
        return self.base_url

    @property
    def username(self) -> Optional[str]:
        if isinstance(self.auth, OAuth2Auth):
            return self.auth.username
        return None

    @property
    def api_key(self) -> Optional[str]:
        if isinstance(self.auth, APIKeyAuth):
            return self.auth.api_key
        return None

    @property
    def _access_token(self) -> Optional[str]:
        if isinstance(self.auth, OAuth2Auth):
            return self.auth._access_token
        if isinstance(self.auth, BearerTokenAuth):
            return self.auth.token
        return None

    @_access_token.setter
    def _access_token(self, value: Optional[str]) -> None:
        if isinstance(self.auth, OAuth2Auth):
            self.auth._access_token = value
        elif isinstance(self.auth, BearerTokenAuth):
            self.auth.token = value

    @property
    def _token_expires_at(self) -> Optional[float]:
        if isinstance(self.auth, OAuth2Auth):
            return self.auth._token_expires_at
        return None

    @_token_expires_at.setter
    def _token_expires_at(self, value: Optional[float]) -> None:
        if isinstance(self.auth, OAuth2Auth):
            self.auth._token_expires_at = value

    def _generate_access_token(self) -> str:
        if isinstance(self.auth, OAuth2Auth):
            return self.auth._generate_token(self.base_url, session=self.session)
        raise HelpDeskAuthError(
            "Missing OAuth2 credentials (username, password, client_id, client_secret) "
            "required to generate an access token."
        )

    def _get_access_token(self) -> str:
        if isinstance(self.auth, OAuth2Auth):
            return self.auth.get_token(self.base_url, session=self.session)
        if isinstance(self.auth, BearerTokenAuth):
            return self.auth.token or ""
        raise HelpDeskAuthError("Current authentication provider is not token-based.")

    def _build_auth_headers(self) -> Dict[str, str]:
        if self.auth is None:
            raise HelpDeskAuthError("No authentication provider configured.")
        return self.auth.get_headers(base_url=self.base_url, session=self.session)

    def _dispatch(self, method: str, endpoint: str, **kwargs) -> Any:
        if not self.base_url:
            raise HelpDeskValidationError("base_url must be configured before making requests.")

        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        url = f"{self.base_url}{endpoint}"

        headers = kwargs.pop("headers", {})
        auth_headers = self._build_auth_headers()
        headers.update(auth_headers)

        kwargs.setdefault("verify", self.verify_ssl)
        kwargs.setdefault("timeout", self.timeout)

        try:
            response = self.session.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            if not response.content:
                return {}
            return response.json()
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            msg = f"API error {status} for {method} {url}: {exc}"
            try:
                details = exc.response.json() if exc.response is not None else {}
            except Exception:
                details = {}

            if status in (401, 403):
                raise HelpDeskAuthError(
                    msg, response=exc.response, status_code=status, error_details=details
                ) from exc
            if status == 404:
                raise HelpDeskNotFoundError(
                    msg, response=exc.response, status_code=status, error_details=details
                ) from exc
            raise HelpDeskAPIError(
                msg, response=exc.response, status_code=status, error_details=details
            ) from exc

    def get_technician(self, technician_id: int) -> Technician:
        """Get technician details by ID.

        Args:
            technician_id: The ID of the technician to retrieve

        Returns:
            Technician: The technician object with details

        Raises:
            HelpDeskNotFoundError: If technician not found (404)
            HelpDeskAPIError: If API request fails
        """
        url = f"/api/technician/{technician_id}"
        raw_dict = self._dispatch("GET", url)
        return Technician(**raw_dict)

    def search_tickets(
        self,
        query: Union[dict, QueryBuilder],
        offset: int = 0,
        page_size: int = 50,
    ) -> SearchResponse:
        """Search tickets matching qualifications.

        Args:
            query: Query dictionary or a QueryBuilder instance
            offset: Pagination offset
            page_size: Number of tickets per page

        Returns:
            SearchResponse: List of HelpTicket models and total count
        """
        if isinstance(query, QueryBuilder):
            payload = query.build()
        elif hasattr(query, "to_dict"):
            payload = query.to_dict()
        else:
            payload = query

        url = f"/api/v1/request/search/byqual?offset={offset}&size={page_size}"
        raw_dict = self._dispatch("POST", url, json=payload)
        return SearchResponse(**raw_dict)

    def create_ticket(
        self,
        subject: str,
        requester_email: str,
        category_name: Optional[str] = None,
        description: Optional[str] = None,
        status_name: Optional[str] = None,
        priority_name: Optional[str] = None,
        urgency_name: Optional[str] = None,
        impact_name: Optional[str] = None,
        department_name: Optional[str] = None,
        location_name: Optional[str] = None,
        technician_group_name: Optional[str] = None,
        assignee_email: Optional[str] = None,
        support_level: Optional[str] = None,
        source: Optional[str] = "External",
        spam: bool = False,
        tags: Optional[List[str]] = None,
        cc_email_set: Optional[List[str]] = None,
        custom_field: Optional[Dict[str, Any]] = None,
        file_attachments: Optional[List[dict]] = None,
        link_asset_ids: Optional[List[dict]] = None,
        link_ci_ids: Optional[List[dict]] = None,
        extra_fields: Optional[Dict[str, Any]] = None,
        validate_response: bool = True,
    ) -> Union[HelpTicket, dict]:
        """Create a new request/ticket in ServiceOps.

        Args:
            subject: Subject of the ticket (required).
            requester_email: Email address of the requester (required).
            category_name: Category name of the request (e.g. 'Request', 'Hardware').
            description: Detailed explanation about the ticket.
            status_name: Status name (e.g. 'Open', 'In Progress', 'Pending', 'Resolved', 'Closed').
            priority_name: Importance (e.g. 'Low', 'Medium', 'High', 'Urgent').
            urgency_name: Urgency (e.g. 'Low', 'Medium', 'High', 'Urgent').
            impact_name: Effect of the request (e.g. 'Low', 'On User', 'On department', 'On Business').
            department_name: Department name.
            location_name: Location name where the request occurred.
            technician_group_name: Assigned technician group.
            assignee_email: Assigned technician email.
            support_level: Support tier (e.g. 'Tier1', 'Tier2', 'Tier3', 'tier4').
            source: Origin of ticket (default 'External').
            spam: Whether marked as spam (default False).
            tags: Additional identifier tags.
            cc_email_set: CC recipient emails for notifications.
            custom_field: Custom fields dictionary.
            file_attachments: List of attachments ({'refFileName': ..., 'realName': ...}).
            link_asset_ids: List of linked assets ({'assetModel': ..., 'assetId': ...}).
            link_ci_ids: List of linked CIs ({'ciId': ..., 'ciModel': ...}).
            extra_fields: Any additional arbitrary API payload fields.
            validate_response: Return validated HelpTicket model if True, raw dict if False.

        Returns:
            Union[HelpTicket, dict]: The created ticket.
        """
        if not subject:
            raise HelpDeskValidationError("subject is required to create a ticket.")
        if not requester_email:
            raise HelpDeskValidationError("requester_email is required to create a ticket.")

        payload: Dict[str, Any] = {
            "subject": subject,
            "requesterEmail": requester_email,
            "source": source or "External",
            "spam": bool(spam),
        }

        if category_name is not None:
            payload["categoryName"] = category_name
        if description is not None:
            payload["description"] = description
        if status_name is not None:
            payload["statusName"] = status_name
        if priority_name is not None:
            payload["priorityName"] = priority_name
        if urgency_name is not None:
            payload["urgencyName"] = urgency_name
        if impact_name is not None:
            payload["impactName"] = impact_name
        if department_name is not None:
            payload["departmentName"] = department_name
        if location_name is not None:
            payload["locationName"] = location_name
        if technician_group_name is not None:
            payload["technicianGroupName"] = technician_group_name
        if assignee_email is not None:
            payload["assigneeEmail"] = assignee_email
        if support_level is not None:
            payload["supportLevel"] = support_level
        if tags is not None:
            payload["tags"] = tags
        if cc_email_set is not None:
            payload["ccEmailSet"] = cc_email_set
        if custom_field is not None:
            payload["customField"] = custom_field
        if file_attachments is not None:
            payload["fileAttachments"] = file_attachments
        if link_asset_ids is not None:
            payload["linkAssetIds"] = link_asset_ids
        if link_ci_ids is not None:
            payload["linkCiIds"] = link_ci_ids
        if extra_fields:
            payload.update(extra_fields)

        url = "/api/v1/request"
        raw_dict = self._dispatch("POST", url, json=payload)
        if validate_response:
            return HelpTicket(**raw_dict)
        return raw_dict

    create_request = create_ticket

    def get_ticket(self, ticket_id: int) -> dict:
        """Get a single ticket by ID from the help desk API.

        Args:
            ticket_id: The ID of the ticket to retrieve

        Returns:
            dict: Raw ticket data in HelpDesk API format
        """
        url = f"/api/v1/request/{ticket_id}"
        return self._dispatch("GET", url)

    def update_ticket(
        self,
        ticket_id: int,
        updates: dict,
        validate_response: bool = True,
    ) -> Union[HelpTicket, dict]:
        """Update a ticket in the help desk system.

        Args:
            ticket_id: The ID of the ticket to update
            updates: Dictionary of fields to update
            validate_response: Whether to validate the response against HelpTicket model (default: True)

        Returns:
            Union[HelpTicket, dict]: Response from API
        """
        url = f"/api/request/{ticket_id}"
        raw_dict = self._dispatch("PATCH", url, json=updates)
        if validate_response:
            return HelpTicket(**raw_dict)
        return raw_dict

    def delete_ticket(self, ticket_id: int) -> dict:
        """Delete / archive a request ticket by ID.

        Args:
            ticket_id: The ID of the ticket to delete.

        Returns:
            dict: API response, e.g. {"userMessage": "...", "id": ticket_id}
        """
        url = f"/api/v1/request/{ticket_id}"
        return self._dispatch("DELETE", url)

    delete_request = delete_ticket

    def get_tickets_by_requester(self, requester: str) -> SearchResponse:
        """Get tickets by requester logon name or email address.

        Args:
            requester: The requester's email address or logon name.

        Returns:
            SearchResponse: Search response containing matching tickets.
        """
        url = f"/api/v1/request/search/byRequester?requester={requester}"
        raw_dict = self._dispatch("GET", url)
        return SearchResponse(**raw_dict)

    def get_request_count(self, column: str = "status", module: str = "request") -> dict:
        """Get ticket aggregation count by column (status, priority, department, etc.).

        Args:
            column: Column name to aggregate by (e.g. 'status', 'priority', 'department', 'category', 'urgency', 'impact').
            module: Module name (default 'request').

        Returns:
            dict: Aggregation result dictionary.
        """
        url = "/api/analytics/v1/aggregation/bymodule"
        payload = {"module": module, "column": column}
        return self._dispatch("GET", url, json=payload)

    def upload_attachment(
        self,
        file_path: Optional[Union[str, os.PathLike]] = None,
        file_content: Optional[bytes] = None,
        file_name: Optional[str] = None,
    ) -> dict:
        """Upload a file attachment to ServiceOps to obtain a refFileName.

        The returned refFileName can be passed in fileAttachments when creating
        or updating tickets, or adding replies.

        Args:
            file_path: Path to the local file to upload.
            file_content: Raw bytes of the file (alternative to file_path).
            file_name: Name of the file (required if file_content is provided).

        Returns:
            dict: Upload response containing 'refFileName', 'realName', 'id', etc.
        """
        url = "/api/upload/file"
        if file_path is not None:
            path_obj = os.path.abspath(str(file_path))
            fname = file_name or os.path.basename(path_obj)
            with open(path_obj, "rb") as f:
                files = {"file": (fname, f)}
                return self._dispatch("POST", url, files=files)
        elif file_content is not None:
            if not file_name:
                raise HelpDeskValidationError(
                    "file_name is required when passing file_content bytes"
                )
            files = {"file": (file_name, file_content)}
            return self._dispatch("POST", url, files=files)
        else:
            raise HelpDeskValidationError("Either file_path or file_content must be provided")

    def reply_to_ticket(
        self,
        ticket_id: int,
        conversation_type: Union[str, ConversationType],
        details: str,
        subject: str,
        conversation_state: Union[str, ConversationState] = "published",
        email_ids: Optional[List[str]] = None,
        cc_email_ids: Optional[List[str]] = None,
        file_attachments: Optional[List[dict]] = None,
    ) -> dict:
        """Create a reply/conversation entry for a ticket in the help desk system.

        Args:
            ticket_id: The ID of the ticket to reply to
            conversation_type: Type of conversation - 'requestor_to_technician',
                'technician_to_requester', 'note', or 'collaborate'
            details: The reply message content (HTML supported)
            subject: Subject line for the reply
            conversation_state: State of conversation - 'published' (default) or 'draft'
            email_ids: List of primary recipient email addresses
            cc_email_ids: List of CC recipient email addresses
            file_attachments: List of file attachment dicts with 'refFileName' and 'realName'

        Returns:
            dict: Response from the help desk API
        """
        c_type = (
            conversation_type.value
            if isinstance(conversation_type, ConversationType)
            else conversation_type
        )
        c_state = (
            conversation_state.value
            if isinstance(conversation_state, ConversationState)
            else conversation_state
        )

        valid_conversation_types = [
            "requestor_to_technician",
            "technician_to_requester",
            "note",
            "collaborate",
        ]
        if c_type not in valid_conversation_types:
            raise HelpDeskValidationError(
                f"Invalid conversation_type '{c_type}'. Must be one of: {valid_conversation_types}"
            )

        valid_states = ["published", "draft"]
        if c_state not in valid_states:
            raise HelpDeskValidationError(
                f"Invalid conversation_state '{c_state}'. Must be one of: {valid_states}"
            )

        payload: Dict[str, Any] = {
            "conversationType": c_type,
            "details": details,
            "subject": subject,
            "conversationState": c_state,
            "noteAsFirstResponse": False,
        }

        if email_ids:
            payload["emailIds"] = email_ids
            payload["emailSendConfigId"] = 4

        if cc_email_ids:
            payload["ccEmailIds"] = cc_email_ids

        if file_attachments:
            for attachment in file_attachments:
                if (
                    not isinstance(attachment, dict)
                    or "refFileName" not in attachment
                    or "realName" not in attachment
                ):
                    raise HelpDeskValidationError(
                        "Each file attachment must be a dict with 'refFileName' and 'realName' keys"
                    )
            payload["fileAttachments"] = file_attachments

        url = f"/api/request/{ticket_id}/conversation"
        return self._dispatch("POST", url, json=payload)

    def reply_to_ticket_simple(
        self,
        ticket_id: int,
        message: str,
        subject: Optional[str] = None,
        from_technician: bool = True,
        notify_requester: bool = True,
        cc_emails: Optional[List[str]] = None,
    ) -> dict:
        """Simplified method to reply to a ticket with common defaults."""
        if not message.strip().startswith("<"):
            message = f"<p>{message}</p>"

        if not subject:
            subject = "Ticket Update"

        conversation_type = (
            "technician_to_requester" if from_technician else "requestor_to_technician"
        )

        email_ids = [] if (notify_requester and from_technician) else None

        return self.reply_to_ticket(
            ticket_id=ticket_id,
            conversation_type=conversation_type,
            details=message,
            subject=subject,
            email_ids=email_ids,
            cc_email_ids=cc_emails,
        )

    def get_conversation(self, conversation_id: int) -> Optional[Conversation]:
        """Get a specific conversation by conversation ID. Returns None if 404 Not Found."""
        try:
            url = f"/api/conversation/{conversation_id}"
            raw_dict = self._dispatch("GET", url)
            return Conversation(**raw_dict)
        except HelpDeskNotFoundError:
            logger.warning("Conversation %s not found", conversation_id)
            return None
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                logger.warning("Conversation %s not found", conversation_id)
                return None
            raise

    def get_ticket_conversations(self, ticket_id: int) -> dict:
        """Get all conversations/replies for a specific ticket."""
        url = f"/api/request/{ticket_id}/conversation"
        return self._dispatch("GET", url)

    def search_ticket_conversations(
        self,
        ticket_id: int,
        conversation_state: Union[str, ConversationState] = "published",
        offset: int = 0,
        page_size: int = 50,
    ) -> ConversationSearchResponse:
        """Search conversations for a specific ticket using the search API."""
        c_state = (
            conversation_state.value
            if isinstance(conversation_state, ConversationState)
            else conversation_state
        )
        url = (
            f"/api/request/{ticket_id}/conversation/search/byqual?offset={offset}&size={page_size}"
        )

        query = {
            "qualDetails": {
                "type": "FlatQualificationRest",
                "quals": [
                    {
                        "type": "RelationalQualificationRest",
                        "leftOperand": {
                            "type": "PropertyOperandRest",
                            "key": ".conversation.conversationState",
                        },
                        "operator": "equal",
                        "rightOperand": {
                            "type": "ValueOperandRest",
                            "value": {
                                "type": "EnumValueRest",
                                "value": c_state,
                            },
                        },
                    }
                ],
            }
        }

        raw_dict = self._dispatch("POST", url, json=query)
        return ConversationSearchResponse(**raw_dict)

    def get_all_ticket_conversations(self, ticket_id: int) -> ConversationSearchResponse:
        """Get all conversations for a ticket regardless of type or state."""
        url = f"/api/request/{ticket_id}/conversation/search/byqual"
        query = {"qualDetails": {"type": "FlatQualificationRest", "quals": []}}
        raw_dict = self._dispatch("POST", url, json=query)
        return ConversationSearchResponse(**raw_dict)

    def update_conversation(
        self,
        ticket_id: int,
        conversation_id: int,
        conversation_type: Optional[Union[str, ConversationType]] = None,
        details: Optional[str] = None,
        subject: Optional[str] = None,
        conversation_state: Optional[Union[str, ConversationState]] = None,
        email_ids: Optional[List[str]] = None,
        cc_email_ids: Optional[List[str]] = None,
        file_attachments: Optional[List[dict]] = None,
    ) -> dict:
        """Update/patch an existing conversation in a help desk ticket."""
        payload: Dict[str, Any] = {}

        if conversation_type is not None:
            c_type = (
                conversation_type.value
                if isinstance(conversation_type, ConversationType)
                else conversation_type
            )
            valid_types = [
                "note",
                "collaborate",
                "requestor_to_technician",
                "technician_to_requester",
            ]
            if c_type not in valid_types:
                raise HelpDeskValidationError(
                    f"Invalid conversation_type '{c_type}'. Must be one of: {valid_types}"
                )
            payload["conversationType"] = c_type

        if details is not None:
            payload["details"] = details

        if subject is not None:
            payload["subject"] = subject

        if conversation_state is not None:
            c_state = (
                conversation_state.value
                if isinstance(conversation_state, ConversationState)
                else conversation_state
            )
            valid_states = ["published", "draft"]
            if c_state not in valid_states:
                raise HelpDeskValidationError(
                    f"Invalid conversation_state '{c_state}'. Must be one of: {valid_states}"
                )
            payload["conversationState"] = c_state

        if email_ids is not None:
            payload["emailIds"] = email_ids

        if cc_email_ids is not None:
            payload["ccEmailIds"] = cc_email_ids

        if file_attachments is not None:
            for attachment in file_attachments:
                if (
                    not isinstance(attachment, dict)
                    or "refFileName" not in attachment
                    or "realName" not in attachment
                ):
                    raise HelpDeskValidationError(
                        "Each file attachment must be a dict with 'refFileName' and 'realName' keys"
                    )
            payload["fileAttachments"] = file_attachments

        if not payload:
            raise HelpDeskValidationError("At least one field must be provided for update")

        url = f"/api/conversation/{conversation_id}"
        return self._dispatch("PATCH", url, json=payload)

    def update_conversation_simple(
        self,
        ticket_id: int,
        conversation_id: int,
        message: Optional[str] = None,
        subject: Optional[str] = None,
        make_note: bool = False,
        publish: bool = True,
    ) -> dict:
        """Simplified method to update a conversation with common defaults."""
        update_fields: Dict[str, Any] = {}

        if message is not None:
            if not message.strip().startswith("<"):
                message = f"<p>{message}</p>"
            update_fields["details"] = message

        if subject is not None:
            update_fields["subject"] = subject

        if make_note:
            update_fields["conversation_type"] = "note"

        update_fields["conversation_state"] = "published" if publish else "draft"

        return self.update_conversation(
            ticket_id=ticket_id,
            conversation_id=conversation_id,
            **update_fields,
        )

    def search_response_templates(
        self,
        offset: int = 0,
        page_size: int = 25,
        name_filter: Optional[str] = None,
    ) -> dict:
        """Search response templates from the help desk system."""
        url = f"/api/responsetemplate/search/byqual?offset={offset}&size={page_size}"
        payload: Dict[str, Any] = {}
        if name_filter:
            payload = {
                "qualDetails": {
                    "type": "FlatQualificationRest",
                    "quals": [
                        {
                            "type": "RelationalQualificationRest",
                            "leftOperand": {
                                "type": "PropertyOperandRest",
                                "key": ".name",
                            },
                            "operator": "contains",
                            "rightOperand": {
                                "type": "ValueOperandRest",
                                "value": {
                                    "type": "StringValueRest",
                                    "value": name_filter,
                                },
                            },
                        }
                    ],
                }
            }

        return self._dispatch("POST", url, json=payload)

    def get_response_template_by_name(self, template_name: str) -> Optional[dict]:
        """Get a response template by its exact name."""
        try:
            response = self.search_response_templates(name_filter=template_name)
            templates = response.get("objectList", [])
            for template in templates:
                if template.get("name") == template_name:
                    return template
            return None
        except Exception as e:
            logger.error("Error fetching template '%s': %s", template_name, str(e))
            return None

    def render_response_template(self, template_content: str, variables: dict) -> str:
        """Render a response template with provided variables."""
        return render_helpdesk_template(template_content, variables)

    def close(self) -> None:
        """Close the underlying requests session."""
        self.session.close()

    def __enter__(self) -> "HelpDeskClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"<HelpDeskClient base_url={self.base_url!r}>"
