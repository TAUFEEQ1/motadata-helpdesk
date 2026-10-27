from motadata_helpdesk.templates import (
    _render_template_fallback,
    render_helpdesk_template,
)


def test_render_helpdesk_template_basic():
    content = "Hello {#user.name#}, your ticket is {#ticket_id#}."
    variables = {
        "user": {"name": "Alice"},
        "ticket_id": 104,
    }
    rendered = render_helpdesk_template(content, variables)
    assert rendered == "Hello Alice, your ticket is 104."


def test_render_helpdesk_template_jinja_syntax():
    content = "<p>Ticket {{ ticket_id }} for {{ user.name }}</p>"
    variables = {
        "user": {"name": "Bob"},
        "ticket_id": 42,
    }
    rendered = render_helpdesk_template(content, variables)
    assert rendered == "<p>Ticket 42 for Bob</p>"


def test_render_fallback():
    content = "Reset url: {#auth.reset_url#} for {#user.email#}"
    variables = {
        "auth": {"reset_url": "https://auth.example.com/token"},
        "user": {"email": "user@example.com"},
    }
    rendered = _render_template_fallback(content, variables)
    assert rendered == "Reset url: https://auth.example.com/token for user@example.com"


def test_render_missing_variable_keeps_placeholder():
    content = "Hello {#missing.key#}!"
    variables = {}
    rendered = _render_template_fallback(content, variables)
    assert rendered == "Hello {#missing.key#}!"
