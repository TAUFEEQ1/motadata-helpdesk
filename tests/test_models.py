from motadata_helpdesk.models import (
    Conversation,
    ConversationSearchResponse,
    HelpTicket,
    SearchResponse,
    Technician,
)


def test_technician_model():
    data = {
        "id": 288,
        "name": "Jane Doe",
        "email": "jane@example.com",
        "userType": "technician",
        "accessLevel": "global_access",
        "isSuperAdmin": True,
        "departmentId": 5,
        "managerId": 10,
        "userLogOnName": "janedoe",
        "supportLevel": ["Tier1", "Tier2"],
        "extraFieldFromFutureApi": "something_ignored",
    }
    tech = Technician.model_validate(data)
    assert tech.id == 288
    assert tech.name == "Jane Doe"
    assert tech.email == "jane@example.com"
    assert tech.user_type == "technician"
    assert tech.access_level == "global_access"
    assert tech.is_super_admin is True
    assert tech.department_id == 5
    assert tech.manager_id == 10
    assert tech.user_logon_name == "janedoe"
    assert tech.support_level == ["Tier1", "Tier2"]


def test_help_ticket_model():
    data = {
        "id": 104,
        "name": "INC-104",
        "createdTime": 1690000000000,
        "updatedTime": 1690001000000,
        "technicianGroupName": "IT Support",
        "assigneeEmail": "tech@example.com",
        "statusName": "Open",
        "createdByName": "John Doe",
        "subject": "VPN connection failure",
        "requesterName": "Alice Smith",
        "fileAttachments": [{"refFileName": "abc", "realName": "log.txt"}],
        "requesterEmail": "alice@example.com",
        "description": "<p>Cannot connect to VPN</p>",
        "impactName": "Medium",
        "priorityName": "High",
        "urgencyName": "High",
        "updatedByName": "Bob Jones",
        "source": "Portal",
        "spam": False,
        "supportLevel": "Tier1",
        "unmappedField": "should be ignored safely",
    }
    ticket = HelpTicket.model_validate(data)
    assert ticket.id == 104
    assert ticket.subject == "VPN connection failure"
    assert ticket.status_name == "Open"
    assert ticket.assignee_email == "tech@example.com"
    assert len(ticket.file_attachments) == 1
    assert ticket.file_attachments[0]["realName"] == "log.txt"


def test_search_response_model():
    data = {
        "totalCount": 1,
        "objectList": [
            {
                "id": 104,
                "name": "INC-104",
                "createdTime": 1690000000000,
                "updatedTime": 1690001000000,
                "statusName": "Open",
                "createdByName": "John Doe",
                "subject": "VPN issue",
                "requesterName": "Alice Smith",
                "requesterEmail": "alice@example.com",
                "description": "Help please",
                "impactName": "Low",
                "priorityName": "Low",
                "urgencyName": "Low",
                "source": "Email",
                "supportLevel": "Tier1",
            }
        ],
    }
    resp = SearchResponse.model_validate(data)
    assert resp.total_count == 1
    assert len(resp.object_list) == 1
    assert resp.object_list[0].id == 104


def test_conversation_model():
    data = {
        "id": 12,
        "details": "<p>Ticket acknowledged.</p>",
        "conversationType": "technician_to_requester",
        "createdByName": "Tech User",
        "createdById": 42,
    }
    conv = Conversation.model_validate(data)
    assert conv.id == 12
    assert conv.details == "<p>Ticket acknowledged.</p>"
    assert conv.created_by_name == "Tech User"


def test_conversation_created_by_fallback():
    # If createdByName is missing but createdById is provided, set User-{createdById}
    data = {
        "id": 13,
        "details": "Note content",
        "createdById": 88,
    }
    conv = Conversation.model_validate(data)
    assert conv.created_by_name == "User-88"


def test_conversation_search_response():
    data = {
        "totalCount": 2,
        "objectList": [
            {"id": 1, "details": "Msg 1"},
            {"id": 2, "details": "Msg 2"},
        ],
    }
    resp = ConversationSearchResponse.model_validate(data)
    assert resp.total_count == 2
    assert len(resp.object_list) == 2
    assert resp.object_list[0].id == 1
    assert resp.object_list[1].details == "Msg 2"
