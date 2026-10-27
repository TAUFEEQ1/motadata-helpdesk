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

You can authenticate using dedicated Auth classes (`OAuth2Auth` or `APIKeyAuth`) or by passing credentials directly to `HelpDeskClient`.

#### Option A: OAuth 2.0 Authentication (Recommended for ServiceOps)

```python
from motadata_helpdesk import HelpDeskClient, OAuth2Auth

auth = OAuth2Auth(
    client_id="your-client-id",
    client_secret="your-client-secret",
    username="technician@company.com",
    password="your-password",
)

client = HelpDeskClient(
    base_url="https://serviceops.example.com",
    auth=auth,
    verify_ssl=False,  # Set to True for production with valid certificates
)
```

#### Option B: API Key Authentication

```python
from motadata_helpdesk import HelpDeskClient, APIKeyAuth

auth = APIKeyAuth(api_key="your-api-key")

client = HelpDeskClient(
    base_url="https://serviceops.example.com",
    auth=auth,
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
from motadata_helpdesk import HelpDeskClient

# Automatically resolves auth and URL from environment variables
client = HelpDeskClient()
```

---

## Usage Examples

### Creating a Ticket / Request

```python
# Create a new ticket (POST /api/v1/request)
ticket = client.create_ticket(
    subject="Printer not responding",
    requester_email="alice@company.com",
    category_name="Hardware",
    priority_name="High",
    urgency_name="Urgent",
    impact_name="On Users",
    department_name="Finance",
    description="Network printer on 2nd floor is throwing paper jam error.",
    tags=["Printer", "Hardware"],
)

print(f"Ticket created: {ticket.name} (ID: {ticket.id})")
```

### Uploading Attachments

```python
# Upload a file to receive a refFileName for tickets or conversations
attachment = client.upload_attachment(file_path="logs.txt")
ref_file_name = attachment["refFileName"]

# Attach when creating or updating a ticket
ticket = client.create_ticket(
    subject="App Crash",
    requester_email="bob@company.com",
    file_attachments=[
        {"refFileName": ref_file_name, "realName": "logs.txt"}
    ],
)
```

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
