from enum import Enum, IntEnum


class StatusEnum(IntEnum):
    """Help desk ticket status IDs."""

    CLOSED = 13


class ConversationType(str, Enum):
    """Types of conversation in Help Desk."""

    REQUESTOR_TO_TECHNICIAN = "requestor_to_technician"
    TECHNICIAN_TO_REQUESTER = "technician_to_requester"
    NOTE = "note"
    COLLABORATE = "collaborate"


class ConversationState(str, Enum):
    """States of conversation."""

    PUBLISHED = "published"
    DRAFT = "draft"
