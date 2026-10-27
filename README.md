# motadata-helpdesk

[![PyPI version](https://img.shields.io/pypi/v/motadata-helpdesk.svg)](https://pypi.org/project/motadata-helpdesk/)
[![Python versions](https://img.shields.io/pypi/pyversions/motadata-helpdesk.svg)](https://pypi.org/project/motadata-helpdesk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

A Python client library and SDK for the **Motadata ServiceOps** HelpDesk REST API.

---

## Features

- **Full Ticket Lifecycle**: Retrieve, search, update status, categories, and custom fields.
- **Conversation & Replies**: Add notes, technician-to-requester replies, requester-to-technician updates, and attachments.
- **Fluent Query Builder**: Construct complex qualification filters (`where_property`, `where_variable`, `where_not_closed`, `where_created_after`, etc.) with ease.
- **Response Template Engine**: Fetch and render response templates with placeholders (`{#variable#}` and Jinja2 syntax).
- **Multiple Authentication Modes**:
  - OAuth2 Password Grant (automatic token retrieval and caching/refresh)
  - API Key (`Apikey <key>`)
  - Direct Bearer Token
  - Environment variables fallback
- **Strong Typing & Validation**: Pydantic v2 models for `HelpTicket`, `Technician`, `Conversation`, and `SearchResponse`.

---

## Installation

```bash
pip install motadata-helpdesk
```

---

## Quickstart

### 1. Initialize the Client

#### Option A: OAuth 2.0 Credentials (Recommended for ServiceOps)

```python
from motadata_helpdesk import HelpDeskClient

client = HelpDeskClient(
    base_url="https://serviceops.example.com",
    client_id="your-client-id",
    client_secret="your-client-secret",
    username="technician@company.com",
    password="your-password",
    verify_ssl=False,  # Set to True for production with valid certificates
)
```

#### Option B: API Key

```python
from motadata_helpdesk import HelpDeskClient

client = HelpDeskClient(
    base_url="https://serviceops.example.com",
    api_key="your-api-key",
)
```

#### Option C: Environment Variables

You can configure the client via environment variables:

- `MOTADATA_BASE_URL` (or `MOTADATA_API_URL`, `TICKET_API_URL`)
- `MOTADATA_CLIENT_ID` (or `API_CLIENT_ID`)
- `MOTADATA_CLIENT_SECRET` (or `API_CLIENT_SECRET`)
- `MOTADATA_USERNAME` (or `API_USERNAME`)
- `MOTADATA_PASSWORD` (or `API_PASSWORD`)
- `MOTADATA_API_KEY` (or `API_KEY`)
- `MOTADATA_VERIFY_SSL` (`true` or `false`)

```python
import os
from motadata_helpdesk import HelpDeskClient

# Automatically reads from environment variables
client = HelpDeskClient()
```

---

## Usage Examples

### Searching Tickets with QueryBuilder

```python
from datetime import datetime, timedelta
from motadata_helpdesk import HelpDeskClient, QueryBuilder, StatusEnum

client = HelpDeskClient(...)

# Build a fluent filter query
query = (
    QueryBuilder()
    .where_not_closed()
    .where_property("request.priorityId", "in", [1, 2])
    .where_created_after(datetime.now() - timedelta(days=7))
)

response = client.search_tickets(query, offset=0, page_size=20)

print(f"Total matching tickets: {response.total_count}")
for ticket in response.object_list:
    print(f"[{ticket.id}] {ticket.subject} - Status: {ticket.status_name} (Requester: {ticket.requester_name})")
```

### Retrieving & Updating Tickets

```python
# Get a single ticket by ID
ticket = client.get_ticket(104)
print(ticket["subject"])

# Update ticket fields (e.g. urgency, category, status)
client.update_ticket(104, {"urgencyName": "High", "categoryName": "Hardware"})
```

### Managing Conversations & Replies

```python
from motadata_helpdesk import ConversationType, ConversationState

# Simple technician reply
client.reply_to_ticket_simple(
    ticket_id=104,
    message="We are looking into this issue and will update you shortly.",
    subject="Ticket Update",
    from_technician=True,
    notify_requester=True,
)

# Detailed reply with attachments and CC
client.reply_to_ticket(
    ticket_id=104,
    conversation_type=ConversationType.TECHNICIAN_TO_REQUESTER,
    details="<p>Please review the attached diagnostic guide.</p>",
    subject="Diagnostic Information",
    conversation_state=ConversationState.PUBLISHED,
    email_ids=["requester@company.com"],
    cc_email_ids=["manager@company.com"],
    file_attachments=[
        {"refFileName": "diagnostic_uuid_123.pdf", "realName": "diagnostic_guide.pdf"}
    ],
)

# Get all conversations for a ticket
conversations = client.get_all_ticket_conversations(104)
for conv in conversations.object_list:
    print(f"{conv.created_by_name}: {conv.details}")

# Update / patch a conversation
client.update_conversation_simple(
    ticket_id=104,
    conversation_id=2,
    message="Internal note: escalated to tier 2 team.",
    make_note=True,
)
```

### Response Templates

```python
# Search templates
templates = client.search_response_templates(name_filter="password.reset")

# Get template by name and render
template = client.get_response_template_by_name("itco:password.generateResetLink")
if template:
    rendered = client.render_response_template(
        template["content"],
        {
            "user": {"name": "Alice"},
            "data": {"reset_url": "https://example.com/reset?token=xyz"},
        },
    )
    print(rendered)
```

### Using Context Manager

```python
with HelpDeskClient(...) as client:
    technician = client.get_technician(288)
    print(f"Technician: {technician.name} ({technician.email})")
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
