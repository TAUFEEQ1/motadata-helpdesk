import json
import time

import pytest
import requests

from motadata_helpdesk.client import HelpDeskClient
from motadata_helpdesk.enums import ConversationState, ConversationType
from motadata_helpdesk.exceptions import (
    HelpDeskAPIError,
    HelpDeskAuthError,
    HelpDeskNotFoundError,
    HelpDeskValidationError,
)
from motadata_helpdesk.models import (
    Conversation,
    ConversationSearchResponse,
    HelpTicket,
    SearchResponse,
    Technician,
)
from motadata_helpdesk.query_builder import QueryBuilder


def create_mock_response(status_code=200, json_data=None, content=b""):
    resp = requests.Response()
    resp.status_code = status_code
    if json_data is not None:
        resp._content = json.dumps(json_data).encode("utf-8")
        resp.headers["Content-Type"] = "application/json"
    else:
        resp._content = content
    return resp


def test_client_init_and_env(monkeypatch):
    monkeypatch.setenv("MOTADATA_BASE_URL", "https://env-serviceops.example.com/")
    monkeypatch.setenv("MOTADATA_USERNAME", "env_user")
    monkeypatch.setenv("MOTADATA_PASSWORD", "env_pass")
    monkeypatch.setenv("MOTADATA_CLIENT_ID", "env_cid")
    monkeypatch.setenv("MOTADATA_CLIENT_SECRET", "env_csecret")
    monkeypatch.setenv("MOTADATA_VERIFY_SSL", "false")

    client = HelpDeskClient()
    assert client.base_url == "https://env-serviceops.example.com"
    assert client.username == "env_user"
    assert client.verify_ssl is False


def test_client_repr():
    client = HelpDeskClient(base_url="https://test.example.com", api_key="secret")
    assert repr(client) == "<HelpDeskClient base_url='https://test.example.com'>"
    assert "secret" not in repr(client)


def test_api_key_auth(mocker):
    session_mock = mocker.MagicMock(spec=requests.Session)
    session_mock.request.return_value = create_mock_response(
        200, json_data={"id": 1, "subject": "Test"}
    )

    client = HelpDeskClient(
        base_url="https://test.example.com",
        api_key="my_api_key",
        session=session_mock,
    )

    data = client.get_ticket(1)
    assert data["id"] == 1
    session_mock.request.assert_called_once()
    args, kwargs = session_mock.request.call_args
    assert kwargs["headers"]["Authorization"] == "Apikey my_api_key"


def test_oauth2_token_generation_and_caching(mocker):
    session_mock = mocker.MagicMock(spec=requests.Session)
    token_resp = create_mock_response(200, json_data={"access_token": "token_123"})
    ticket_resp = create_mock_response(200, json_data={"id": 104, "subject": "Printer issue"})

    session_mock.post.return_value = token_resp
    session_mock.request.return_value = ticket_resp

    client = HelpDeskClient(
        base_url="https://test.example.com",
        username="user1",
        password="pwd",
        client_id="cid",
        client_secret="csecret",
        session=session_mock,
    )

    # First call triggers token fetch
    client.get_ticket(104)
    session_mock.post.assert_called_once()
    assert client._access_token == "token_123"

    # Second call uses cached token
    client.get_ticket(104)
    assert session_mock.post.call_count == 1  # Not called again


def test_oauth2_token_expiration(mocker):
    session_mock = mocker.MagicMock(spec=requests.Session)
    token_resp_1 = create_mock_response(200, json_data={"access_token": "token_1"})
    token_resp_2 = create_mock_response(200, json_data={"access_token": "token_2"})
    ticket_resp = create_mock_response(200, json_data={"id": 104})

    session_mock.post.side_effect = [token_resp_1, token_resp_2]
    session_mock.request.return_value = ticket_resp

    client = HelpDeskClient(
        base_url="https://test.example.com",
        username="user1",
        password="pwd",
        client_id="cid",
        client_secret="csecret",
        session=session_mock,
        token_age=1,  # 1 second expiration
    )

    client.get_ticket(104)
    assert client._access_token == "token_1"

    # Simulate token expiration
    client._token_expires_at = time.time() - 10
    client.get_ticket(104)
    assert client._access_token == "token_2"
    assert session_mock.post.call_count == 2


def test_oauth2_missing_credentials():
    client = HelpDeskClient(base_url="https://test.example.com")
    with pytest.raises(HelpDeskAuthError, match="Missing OAuth2 credentials"):
        client._generate_access_token()


def test_error_handling_401(mocker):
    session_mock = mocker.MagicMock(spec=requests.Session)
    err_resp = create_mock_response(401, json_data={"message": "Unauthorized"})
    http_error = requests.HTTPError(response=err_resp)
    session_mock.request.side_effect = http_error

    client = HelpDeskClient(
        base_url="https://test.example.com", api_key="bad_key", session=session_mock
    )

    with pytest.raises(HelpDeskAuthError) as exc_info:
        client.get_ticket(1)
    assert exc_info.value.status_code == 401


def test_error_handling_404(mocker):
    session_mock = mocker.MagicMock(spec=requests.Session)
    err_resp = create_mock_response(404, json_data={"message": "Not Found"})
    http_error = requests.HTTPError(response=err_resp)
    session_mock.request.side_effect = http_error

    client = HelpDeskClient(
        base_url="https://test.example.com", api_key="my_key", session=session_mock
    )

    with pytest.raises(HelpDeskNotFoundError) as exc_info:
        client.get_ticket(9999)
    assert exc_info.value.status_code == 404


def test_error_handling_500(mocker):
    session_mock = mocker.MagicMock(spec=requests.Session)
    err_resp = create_mock_response(500, json_data={"message": "Internal Server Error"})
    http_error = requests.HTTPError(response=err_resp)
    session_mock.request.side_effect = http_error

    client = HelpDeskClient(
        base_url="https://test.example.com", api_key="my_key", session=session_mock
    )

    with pytest.raises(HelpDeskAPIError) as exc_info:
        client.get_ticket(1)
    assert exc_info.value.status_code == 500


def test_get_technician(mocker):
    session_mock = mocker.MagicMock(spec=requests.Session)
    tech_data = {
        "id": 288,
        "name": "Jane Doe",
        "email": "jane@example.com",
        "userType": "technician",
        "accessLevel": "global_access",
    }
    session_mock.request.return_value = create_mock_response(200, json_data=tech_data)

    client = HelpDeskClient(
        base_url="https://test.example.com", api_key="my_key", session=session_mock
    )
    tech = client.get_technician(288)

    assert isinstance(tech, Technician)
    assert tech.id == 288
    assert tech.name == "Jane Doe"


def test_search_tickets_with_dict_and_builder(mocker):
    session_mock = mocker.MagicMock(spec=requests.Session)
    search_data = {
        "totalCount": 1,
        "objectList": [
            {
                "id": 104,
                "name": "INC-104",
                "createdTime": 1690000000000,
                "updatedTime": 1690001000000,
                "statusName": "Open",
                "createdByName": "Requester",
                "subject": "Help",
                "requesterName": "Bob",
                "requesterEmail": "bob@example.com",
                "description": "Details",
                "impactName": "Low",
                "priorityName": "Low",
                "urgencyName": "Low",
                "source": "Portal",
                "supportLevel": "Tier1",
            }
        ],
    }
    session_mock.request.return_value = create_mock_response(200, json_data=search_data)

    client = HelpDeskClient(
        base_url="https://test.example.com", api_key="my_key", session=session_mock
    )

    # 1. Search with QueryBuilder
    qb = QueryBuilder().where_not_closed()
    res1 = client.search_tickets(qb, offset=0, page_size=10)
    assert isinstance(res1, SearchResponse)
    assert res1.total_count == 1
    assert isinstance(res1.object_list[0], HelpTicket)

    # 2. Search with raw dict
    res2 = client.search_tickets(qb.build())
    assert res2.total_count == 1


def test_update_ticket(mocker):
    session_mock = mocker.MagicMock(spec=requests.Session)
    updated_data = {
        "id": 104,
        "name": "INC-104",
        "createdTime": 1690000000000,
        "updatedTime": 1690001000000,
        "statusName": "Resolved",
        "createdByName": "Requester",
        "subject": "Help",
        "requesterName": "Bob",
        "requesterEmail": "bob@example.com",
        "description": "Details",
        "impactName": "Low",
        "priorityName": "Low",
        "urgencyName": "Low",
        "source": "Portal",
        "supportLevel": "Tier1",
    }
    session_mock.request.return_value = create_mock_response(200, json_data=updated_data)

    client = HelpDeskClient(
        base_url="https://test.example.com", api_key="my_key", session=session_mock
    )

    # Validated update
    ticket = client.update_ticket(104, {"statusName": "Resolved"}, validate_response=True)
    assert isinstance(ticket, HelpTicket)
    assert ticket.status_name == "Resolved"
    call_args, call_kwargs = session_mock.request.call_args
    assert call_args[0] == "PATCH"
    assert call_args[1] == "https://test.example.com/api/request/104"

    # Non-validated update (returns raw dict)
    raw = client.update_ticket(104, {"urgencyName": "High"}, validate_response=False)
    assert isinstance(raw, dict)


def test_reply_to_ticket(mocker):
    session_mock = mocker.MagicMock(spec=requests.Session)
    session_mock.request.return_value = create_mock_response(200, json_data={"id": 55})

    client = HelpDeskClient(
        base_url="https://test.example.com", api_key="my_key", session=session_mock
    )

    resp = client.reply_to_ticket(
        ticket_id=104,
        conversation_type=ConversationType.TECHNICIAN_TO_REQUESTER,
        details="<p>Working on it</p>",
        subject="Status Update",
        conversation_state=ConversationState.PUBLISHED,
        email_ids=["requester@example.com"],
        cc_email_ids=["cc@example.com"],
        file_attachments=[{"refFileName": "f1", "realName": "doc.pdf"}],
    )
    assert resp["id"] == 55

    args, kwargs = session_mock.request.call_args
    assert kwargs["json"]["conversationType"] == "technician_to_requester"
    assert kwargs["json"]["emailSendConfigId"] == 4
    assert len(kwargs["json"]["fileAttachments"]) == 1


def test_reply_to_ticket_invalid_args():
    client = HelpDeskClient(base_url="https://test.example.com", api_key="key")

    with pytest.raises(HelpDeskValidationError, match="Invalid conversation_type"):
        client.reply_to_ticket(104, "invalid_type", "msg", "sub")

    with pytest.raises(HelpDeskValidationError, match="Invalid conversation_state"):
        client.reply_to_ticket(104, "note", "msg", "sub", conversation_state="bad_state")

    with pytest.raises(HelpDeskValidationError, match="Each file attachment must be a dict"):
        client.reply_to_ticket(104, "note", "msg", "sub", file_attachments=["bad"])


def test_reply_to_ticket_simple(mocker):
    session_mock = mocker.MagicMock(spec=requests.Session)
    session_mock.request.return_value = create_mock_response(200, json_data={"id": 56})

    client = HelpDeskClient(
        base_url="https://test.example.com", api_key="my_key", session=session_mock
    )

    client.reply_to_ticket_simple(104, message="All good now", subject="Fixed")
    args, kwargs = session_mock.request.call_args
    assert kwargs["json"]["details"] == "<p>All good now</p>"
    assert kwargs["json"]["subject"] == "Fixed"
    assert kwargs["json"]["conversationType"] == "technician_to_requester"


def test_get_conversation(mocker):
    session_mock = mocker.MagicMock(spec=requests.Session)
    conv_data = {"id": 2, "details": "Hello", "createdByName": "Tech"}
    session_mock.request.return_value = create_mock_response(200, json_data=conv_data)

    client = HelpDeskClient(
        base_url="https://test.example.com", api_key="my_key", session=session_mock
    )
    conv = client.get_conversation(2)
    assert isinstance(conv, Conversation)
    assert conv.id == 2


def test_get_conversation_not_found(mocker):
    session_mock = mocker.MagicMock(spec=requests.Session)
    err_resp = create_mock_response(404, json_data={"message": "Not Found"})
    session_mock.request.side_effect = requests.HTTPError(response=err_resp)

    client = HelpDeskClient(
        base_url="https://test.example.com", api_key="my_key", session=session_mock
    )
    conv = client.get_conversation(9999)
    assert conv is None


def test_search_ticket_conversations(mocker):
    session_mock = mocker.MagicMock(spec=requests.Session)
    search_data = {
        "totalCount": 1,
        "objectList": [{"id": 1, "details": "Comment"}],
    }
    session_mock.request.return_value = create_mock_response(200, json_data=search_data)

    client = HelpDeskClient(
        base_url="https://test.example.com", api_key="my_key", session=session_mock
    )
    res = client.search_ticket_conversations(104)
    assert isinstance(res, ConversationSearchResponse)
    assert res.total_count == 1
    assert res.object_list[0].id == 1


def test_get_all_ticket_conversations(mocker):
    session_mock = mocker.MagicMock(spec=requests.Session)
    search_data = {
        "totalCount": 2,
        "objectList": [{"id": 1, "details": "C1"}, {"id": 2, "details": "C2"}],
    }
    session_mock.request.return_value = create_mock_response(200, json_data=search_data)

    client = HelpDeskClient(
        base_url="https://test.example.com", api_key="my_key", session=session_mock
    )
    res = client.get_all_ticket_conversations(104)
    assert res.total_count == 2


def test_update_conversation_simple(mocker):
    session_mock = mocker.MagicMock(spec=requests.Session)
    session_mock.request.return_value = create_mock_response(200, json_data={"id": 2})

    client = HelpDeskClient(
        base_url="https://test.example.com", api_key="my_key", session=session_mock
    )
    client.update_conversation_simple(
        ticket_id=104,
        conversation_id=2,
        message="Escalated",
        make_note=True,
    )

    args, kwargs = session_mock.request.call_args
    assert kwargs["json"]["details"] == "<p>Escalated</p>"
    assert kwargs["json"]["conversationType"] == "note"
    assert kwargs["json"]["conversationState"] == "published"


def test_search_and_get_response_template(mocker):
    session_mock = mocker.MagicMock(spec=requests.Session)
    template_data = {
        "totalCount": 1,
        "objectList": [
            {
                "id": 1,
                "name": "pwd_reset",
                "content": "<p>Reset: {#url#}</p>",
            }
        ],
    }
    session_mock.request.return_value = create_mock_response(200, json_data=template_data)

    client = HelpDeskClient(
        base_url="https://test.example.com", api_key="my_key", session=session_mock
    )

    template = client.get_response_template_by_name("pwd_reset")
    assert template is not None
    assert template["name"] == "pwd_reset"

    rendered = client.render_response_template(template["content"], {"url": "https://example.com"})
    assert rendered == "<p>Reset: https://example.com</p>"


def test_context_manager():
    with HelpDeskClient(base_url="https://test.example.com", api_key="key") as client:
        assert client.base_url == "https://test.example.com"
