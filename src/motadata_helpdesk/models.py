from typing import Any, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Technician(BaseModel):
    """Pydantic model for a technician."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: int
    name: str
    email: str
    user_type: str = Field(alias="userType")
    access_level: str = Field(alias="accessLevel")
    timezone: Optional[str] = Field(default=None)
    department_id: Optional[int] = Field(alias="departmentId", default=None)
    manager_id: Optional[int] = Field(alias="managerId", default=None)
    is_super_admin: bool = Field(alias="isSuperAdmin", default=False)
    logged_in: bool = Field(alias="loggedIn", default=False)
    disabled: bool = Field(default=False)
    verified: bool = Field(default=True)
    vip: bool = Field(default=False)

    # Optional fields that might be useful
    user_logon_name: Optional[str] = Field(alias="userLogOnName", default=None)
    user_language: Optional[str] = Field(alias="userLanguage", default="en-US")
    support_level: List[str] = Field(alias="supportLevel", default_factory=list)
    roles: List[int] = Field(default_factory=list)

    # Timestamps
    created_time: Optional[int] = Field(alias="createdTime", default=None)
    updated_time: Optional[int] = Field(alias="updatedTime", default=None)


class HelpTicket(BaseModel):
    """Pydantic model for a help desk ticket."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: int
    name: str
    created_time: int = Field(alias="createdTime")
    updated_time: int = Field(alias="updatedTime")
    technician_group_name: Optional[str] = Field(alias="technicianGroupName", default=None)
    assignee_email: Optional[str] = Field(alias="assigneeEmail", default=None)
    status_name: str = Field(alias="statusName")
    created_by_name: str = Field(alias="createdByName")
    subject: str
    requester_name: str = Field(alias="requesterName")
    file_attachments: List[dict] = Field(alias="fileAttachments", default_factory=list)
    requester_email: str = Field(alias="requesterEmail")
    description: str
    impact_name: str = Field(alias="impactName")
    priority_name: str = Field(alias="priorityName")
    urgency_name: str = Field(alias="urgencyName")
    updated_by_name: Optional[str] = Field(alias="updatedByName", default=None)
    source: str
    spam: bool = False
    support_level: str = Field(alias="supportLevel")


class SearchResponse(BaseModel):
    """Pydantic model for ticket search response."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    object_list: List[HelpTicket] = Field(alias="objectList", default_factory=list)
    total_count: int = Field(alias="totalCount", default=0)


class Conversation(BaseModel):
    """Pydantic model for a help desk conversation.

    Focus: Only validate fields critical to bot operations.
    Philosophy: Accept any API response format, only enforce what we actually need.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    # CRITICAL FIELDS - Required for bot command operations
    id: int
    details: str

    # IMPORTANT FIELDS - Used for audit/logging but should be permissive
    created_by_name: Optional[str] = Field(alias="createdByName", default="Unknown User")

    # NON-CRITICAL FIELDS - Accept any format, provide sensible defaults
    conversation_type: Optional[str] = Field(alias="conversationType", default="unknown")
    created_by_email: Optional[str] = Field(alias="createdByEmail", default=None)
    created_time: Optional[Union[str, int, None]] = Field(alias="createdTime", default=None)
    updated_time: Optional[Union[str, int, None]] = Field(alias="updatedTime", default=None)
    subject: Optional[str] = Field(default="")
    conversation_state: Optional[str] = Field(alias="conversationState", default="unknown")
    email_ids: Optional[List[str]] = Field(alias="emailIds", default_factory=list)
    cc_email_ids: Optional[List[str]] = Field(alias="ccEmailIds", default_factory=list)
    updatable: Optional[bool] = Field(alias="updatebleOob", default=True)
    deletable: Optional[bool] = Field(alias="deleteableOob", default=True)
    file_attachments: Optional[List[dict]] = Field(alias="fileAttachments", default_factory=list)

    # Additional fields that might be present in responses
    created_by_id: Optional[int] = Field(alias="createdById", default=None)
    updated_by_id: Optional[int] = Field(alias="updatedById", default=None)

    @model_validator(mode="before")
    @classmethod
    def _handle_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            c_name = data.get("createdByName") or data.get("created_by_name")
            c_id = data.get("createdById") or data.get("created_by_id")
            if not c_name and c_id is not None:
                data["createdByName"] = f"User-{c_id}"
        return data


class ConversationSearchResponse(BaseModel):
    """Pydantic model for conversation search response."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    object_list: List[Conversation] = Field(alias="objectList", default_factory=list)
    total_count: int = Field(alias="totalCount", default=0)
