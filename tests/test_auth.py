import json
import time

import pytest
import requests

from motadata_helpdesk.auth import APIKeyAuth, BaseAuth, BearerTokenAuth, OAuth2Auth
from motadata_helpdesk.client import HelpDeskClient
from motadata_helpdesk.exceptions import HelpDeskAuthError


def create_mock_response(status_code=200, json_data=None):
    resp = requests.Response()
    resp.status_code = status_code
    if json_data is not None:
        resp._content = json.dumps(json_data).encode("utf-8")
        resp.headers["Content-Type"] = "application/json"
    return resp


def test_base_auth_not_implemented():
    auth = BaseAuth()
    with pytest.raises(NotImplementedError):
        auth.get_headers()


def test_api_key_auth():
    auth = APIKeyAuth(api_key="secret123")
    headers = auth.get_headers()
    assert headers == {"Authorization": "Apikey secret123"}

    # Custom prefix (e.g. Bearer)
    bearer_api_auth = APIKeyAuth(api_key="secret123", prefix="Bearer")
    assert bearer_api_auth.get_headers() == {"Authorization": "Bearer secret123"}


def test_api_key_auth_missing():
    with pytest.raises(HelpDeskAuthError, match="API key must be provided"):
        APIKeyAuth(api_key="")


def test_api_key_callable():
    auth = APIKeyAuth(api_key="testkey")
    req = requests.Request("GET", "https://example.com").prepare()
    req = auth(req)
    assert req.headers["Authorization"] == "Apikey testkey"


def test_oauth2_auth_token_flow(mocker):
    session_mock = mocker.MagicMock(spec=requests.Session)
    token_resp = create_mock_response(200, json_data={"access_token": "tok_xyz"})
    session_mock.post.return_value = token_resp

    oauth = OAuth2Auth(
        client_id="cid",
        client_secret="csec",
        username="user@example.com",
        password="pwd",
        base_url="https://helpdesk.example.com",
    )

    headers = oauth.get_headers(session=session_mock)
    assert headers == {"Authorization": "Bearer tok_xyz"}
    assert session_mock.post.call_count == 1

    # Second call uses cache
    headers2 = oauth.get_headers(session=session_mock)
    assert headers2 == {"Authorization": "Bearer tok_xyz"}
    assert session_mock.post.call_count == 1


def test_oauth2_auth_refresh(mocker):
    session_mock = mocker.MagicMock(spec=requests.Session)
    token_resp_1 = create_mock_response(200, json_data={"access_token": "tok_1"})
    token_resp_2 = create_mock_response(200, json_data={"access_token": "tok_2"})
    session_mock.post.side_effect = [token_resp_1, token_resp_2]

    oauth = OAuth2Auth(
        client_id="cid",
        client_secret="csec",
        username="user@example.com",
        password="pwd",
        base_url="https://helpdesk.example.com",
        token_age=1,
    )

    oauth.get_headers(session=session_mock)
    assert oauth._access_token == "tok_1"

    # Expire token
    oauth._token_expires_at = time.time() - 5
    oauth.get_headers(session=session_mock)
    assert oauth._access_token == "tok_2"
    assert session_mock.post.call_count == 2


def test_oauth2_auth_missing_credentials():
    oauth = OAuth2Auth(base_url="https://helpdesk.example.com")
    with pytest.raises(HelpDeskAuthError, match="Missing OAuth2 credentials"):
        oauth.get_headers()


def test_bearer_token_auth():
    auth = BearerTokenAuth(token="static_jwt")
    assert auth.get_headers() == {"Authorization": "Bearer static_jwt"}


def test_client_with_injected_auth(mocker):
    session_mock = mocker.MagicMock(spec=requests.Session)
    session_mock.request.return_value = create_mock_response(200, json_data={"id": 10})

    custom_auth = APIKeyAuth(api_key="custom_injected_key")
    client = HelpDeskClient(
        base_url="https://helpdesk.example.com",
        auth=custom_auth,
        session=session_mock,
    )

    ticket = client.get_ticket(10)
    assert ticket["id"] == 10

    _, kwargs = session_mock.request.call_args
    assert kwargs["headers"]["Authorization"] == "Apikey custom_injected_key"
