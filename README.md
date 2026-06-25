<!--
Title: Network Operations Center (NOC) Email Automation System | Langchain/Langgraph Integration
Description: Automate NOC email handling with our system built using Langchain/Langgraph. Features include email categorization, circuit lookup, internal NOC action procedure drafting, and FortiToken automation.
Keywords: NOC automation, email automation, Langchain, Langgraph, AI NOC agents, Gmail API, Python email automation, email categorization, SOP integration, AI agents
-->

# Network Operations Center (NOC) Email Automation with AI Agents and RAG

## Features

### NOC Inbox Management
- Continuously monitors the NOC team's Gmail inbox every 60 seconds.
- Categorizes emails into one of the following:
  - `circuit_down` — complete outage or link down
  - `link_flapping` — intermittent connectivity
  - `packet_loss` — degraded performance or high latency
  - `maintenance_notification` — scheduled downtime or planned work
  - `ewh_fortitoken` — FortiToken/FortiClient VPN requests for EWH users (add, resend, offboard/delete)
  - `general_inquiry` — general questions or status updates
  - `log_analysis` — thread replies containing log files or pasted log content
  - `unrelated` — skipped permanently
- Automatically skips emails from blocked senders and previously processed threads.

### Circuit Lookup (No LLM)
- Extracts circuit reference numbers (NEV-*, provider CIDs, customer CIDs) directly from email text using regex.
- Searches all CSV files in `/data` for matching circuit records.
- Injects matched circuit details (customer, provider, IPs, CPE) into the writer prompt so the LLM has accurate data without hallucinating.

### Internal Procedure Generation
- Drafts an **INTERNAL NOC ACTION PROCEDURE** for each email — not a reply to the customer.
- Output format includes:
  - Request Type
  - Summary of Request
  - Circuit Details (provider, customer, IPs — sourced from CSV lookup)
  - Numbered Action Steps (concise, no repeated circuit info)
  - Notes (escalation paths, SOP references)
- Uses RAG to retrieve relevant SOPs and knowledge base content from ChromaDB.
- Maintenance emails: automatically converts timestamps to GMT+8, inferring timezone from the circuit's installation country if not stated.
- Log analysis emails: produces a structured log analysis (key findings, timeline, root cause indicators, recommendations).

### FortiToken Automation (EWH)
- For `ewh_fortitoken` emails, after the draft is written, the system automatically:
  1. Parses all usernames and emails from the draft (supports multiple users per email).
  2. Validates each user against the **"All Users"** sheet in the FortiToken Google Sheet.
  3. Checks email match and group validity (`EWH-LOCAL-FTK` or `EWH-VENDOR-FTK`).
  4. Appends validated entries to the **"Actions Queue"** sheet (Action, Username, Email, Group).
  5. Appends the automation result to the draft so the NOC officer sees what was queued or failed.
- To disable automation and revert to manual procedure only, comment out this line in `src/nodes.py`:
  ```python
  draft_text = self._process_fortitoken_from_draft(draft_text)
  ```

### Output
- Approved procedures are saved as **Gmail draft replies** in the NOC inbox thread, ready for review.
- Google Chat delivery is implemented but disabled by default (see Switching to Google Chat below).

---

## Tech Stack

- **LangChain & LangGraph** — AI agent workflow orchestration
- **Google Gemini API** — LLM (`gemini-2.5-flash`) and embeddings (`gemini-embedding-001`)
- **Gmail API** — inbox monitoring and draft creation
- **Google Sheets API** — FortiToken automation
- **ChromaDB** — vector store for SOP/knowledge base retrieval
- **Python 3.10+**

---

## Project Structure

```
Gmail-NOC-Agent/
├── main.py                        # Entry point — continuous loop
├── deploy_api.py                  # Optional FastAPI/Langserve deployment
├── requirements.txt
├── .env                           # Environment variables (not committed)
├── config/
│   ├── credentials.json           # Gmail/Sheets OAuth client (not committed)
│   ├── token.json                 # OAuth token (auto-generated, not committed)
│   └── skipped_senders.txt        # Blocked sender list
├── data/                          # SOP .txt files and circuit CSV files (not committed)
├── db/                            # ChromaDB vector store (auto-generated)
├── logs/                          # Log files (auto-generated)
├── scripts/
│   ├── create_index.py            # Build/rebuild ChromaDB from scratch
│   └── add_files.py               # Incrementally add new files to ChromaDB
└── src/
    ├── agents.py                  # LLM chains (categorize, writer, log analyzer)
    ├── graph.py                   # LangGraph workflow definition
    ├── nodes.py                   # Node implementations
    ├── schemas.py                 # Pydantic output schemas
    ├── state.py                   # Graph state definition
    ├── logger.py                  # Centralized logging (UTC+8, rotating file)
    ├── prompts/
    │   ├── categorize.py          # Categorization prompt
    │   ├── writer.py              # Per-category writer prompts
    │   ├── log_analysis.py        # Log analysis prompt
    │   └── rag.py                 # RAG query prompt
    └── tools/
        ├── GmailTools.py          # Gmail API wrapper
        ├── AttachmentParser.py    # .txt/.log attachment extraction
        ├── LogDetector.py         # Detects pasted log content in email body
        ├── CircuitLookup.py       # Direct CSV circuit lookup (no LLM)
        ├── GoogleSheetsFortiToken.py  # FortiToken Google Sheets automation
        └── GoogleChatTools.py     # Google Chat webhook (disabled by default)
```

---

## Setup

### Prerequisites

- Python 3.10 or higher (3.13 recommended)
- Google Gemini API key
- Gmail OAuth credentials (`credentials.json` from Google Cloud Console)
- Google Sheets API enabled on the same Google Cloud project (for FortiToken automation)

### 1. Create and activate a virtual environment

```sh
python -m venv venv
venv\Scripts\activate       # Windows
source venv/bin/activate    # macOS/Linux
```

### 2. Install dependencies

```sh
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
NOC_EMAIL=your_noc_inbox@yourdomain.com
GOOGLE_API_KEY=your_gemini_api_key
GOOGLE_CHAT_WEBHOOK_URL=           # optional, leave blank if not using Google Chat
FORTITOKEN_SHEET_ID=your_google_sheet_id_here
```

To get the `FORTITOKEN_SHEET_ID`: open the Google Sheet in your browser and copy the ID from the URL between `/d/` and `/edit`. The sheet must be a **native Google Sheets file** (not an uploaded .xlsx). If it is an Excel file, go to **File → Save as Google Sheets** first.

### 4. Set up Gmail and Sheets OAuth

1. Follow [this guide](https://developers.google.com/gmail/api/quickstart/python) to enable the **Gmail API**.
2. Enable the **Google Sheets API** on the same Google Cloud project.
3. Download `credentials.json` (OAuth 2.0 Desktop client) and place it in `config/`.
4. On first run, a browser window will open for authentication. Grant access to both Gmail and Google Sheets. A `token.json` will be saved automatically in `config/`.

### 5. Populate the knowledge base

Copy SOP `.txt` files and circuit CSV files into the `data/` folder. CSV files must have these columns (at minimum):

```
Sales Order Number, Customer Company, End Customer Company,
End Customer Installation Address, End Customer Installation Country,
Service Type, CPE Model, CPE Serial, IP Address LAN, IP Address WAN,
Provider Company, Provider Circuit Reference, Customer Circuit Reference
```

### 6. Build the vector store

```sh
python scripts/create_index.py
```

To add new files without rebuilding from scratch:

```sh
python scripts/add_files.py --scan
# or add a specific file:
python scripts/add_files.py "data/MyNewSOP.txt"
```

---

## Running the Agent

### Background mode (recommended)

```sh
start_agent.bat     # Start agent in background
status_agent.bat    # Check status and view last 30 log lines
stop_agent.bat      # Stop the agent
tail_log.bat        # Live-tail the log file
```

### Foreground mode

```sh
python main.py
```

### Deploy as API (optional)

```sh
python deploy_api.py
```

The API runs on `localhost:8000`. Docs available at `/docs`, Langserve playground at `/playground`.

---

## Workflow

[![](https://mermaid.ink/img/pako:eNqllFtv2jAUgP-K5UpTKkGX0BGSPGyCdEVraaWFdkiMCZnkJFg4duY4Awr89zkJl03aw2gfLPlcvnPLcTY4FBFgD8dMLMM5kQo93UzkhHe_PwhOlZConxLK0Bc-E6sflQU1mx9Rb_Mlr5Xoc5qp9addaeuVtu2jQI-w1HoN5ls0NkaEKmSbaAih4FF-WbqO6zAn6lYUPELPnPB8CRKiI-8bPlGQCElfoFZWAcrjV-Qzl8C0S7RFw3tjuKAZeod6jIQLRnPd0FwCiS5P_kwkU8IJW-dUhx90jYFIUHevQCNJFcg_3EMqw4KqaSSWHL1HjPLFNGYkyyhPtJzpPKCmTOS5lnR5XIFuIgQtwXI-jYVUepALKOEEOEjCppT_LKhcb1Fg-ILnShahQkG3j74WICmUkfzhN7RPjZgQiyI7tl2eoJpfEBgBKE38AhRLkZYxKregto-Muh3U1ZnVMcCoMm7_Lm-L7ozbUnqqis3nAAqRQomUKCr45QnsG74eqYL9btxIEitdcemA-kIkDJA_Jwo9QJ6TBCpyUO9N_1BCv14VWKn6m27rXRje_1tfnlytdeQuiilj3kXsxg09OF2rd-E4zv7eXNJIzb1WtmqEggnpXZimeYJ7e3g2O8HX19f_B_uHzLPZ-XDwJvhIx-759OjQdPyK1IPuW-j-HnZfU7fehZqOouh8enwcGZwP350P4wZOJI2wpx8zNHAKUq-vFvFGvwo0wWoOKUywp68RkYsJnvCdZjLCx0KkB0yKIpljLyYs11KRRfqZ3VCSSJIetRJ4BNLX_0uFPafTroJgb4NX2Gu13CvXcTtmyzbd9oe2azfwGntNy3KvOi3bdWzLtGzHsju7Bn6pEltXTstqtxzTbpuO1el0rne_AaQcDB8?type=png)](https://mermaid.live/edit#pako:eNqllFtv2jAUgP-K5UpTKkGX0BGSPGyCdEVraaWFdkiMCZnkJFg4duY4Awr89zkJl03aw2gfLPlcvnPLcTY4FBFgD8dMLMM5kQo93UzkhHe_PwhOlZConxLK0Bc-E6sflQU1mx9Rb_Mlr5Xoc5qp9addaeuVtu2jQI-w1HoN5ls0NkaEKmSbaAih4FF-WbqO6zAn6lYUPELPnPB8CRKiI-8bPlGQCElfoFZWAcrjV-Qzl8C0S7RFw3tjuKAZeod6jIQLRnPd0FwCiS5P_kwkU8IJW-dUhx90jYFIUHevQCNJFcg_3EMqw4KqaSSWHL1HjPLFNGYkyyhPtJzpPKCmTOS5lnR5XIFuIgQtwXI-jYVUepALKOEEOEjCppT_LKhcb1Fg-ILnShahQkG3j74WICmUkfzhN7RPjZgQiyI7tl2eoJpfEBgBKE38AhRLkZYxKregto-Muh3U1ZnVMcCoMm7_Lm-L7ozbUnqqis3nAAqRQomUKCr45QnsG74eqYL9btxIEitdcemA-kIkDJA_Jwo9QJ6TBCpyUO9N_1BCv14VWKn6m27rXRje_1tfnlytdeQuiilj3kXsxg09OF2rd-E4zv7eXNJIzb1WtmqEggnpXZimeYJ7e3g2O8HX19f_B_uHzLPZ-XDwJvhIx-759OjQdPyK1IPuW-j-HnZfU7fehZqOouh8enwcGZwP350P4wZOJI2wpx8zNHAKUq-vFvFGvwo0wWoOKUywp68RkYsJnvCdZjLCx0KkB0yKIpljLyYs11KRRfqZ3VCSSJIetRJ4BNLX_0uFPafTroJgb4NX2Gu13CvXcTtmyzbd9oe2azfwGntNy3KvOi3bdWzLtGzHsju7Bn6pEltXTstqtxzTbpuO1el0rne_AaQcDB8)

---

## Switching to Google Chat

The system is built to optionally send procedures to a Google Chat space instead of saving Gmail drafts. To switch:

1. Set `GOOGLE_CHAT_WEBHOOK_URL` in `.env` (get it from your Chat space → Apps & integrations → Webhooks).
2. In `src/graph.py`, comment out the `send_email` lines and uncomment the `send_to_google_chat` lines.
3. In `src/nodes.py`, uncomment the `send_to_google_chat` method.

---

## Resetting the Agent

| What to reset | Command |
|---|---|
| Gmail/Sheets OAuth token | `del config\token.json` |
| Skipped threads list | `echo [] > config\skipped_threads.json` |
| Vector store | `python scripts/create_index.py` |

After deleting `token.json`, the next `python main.py` run will re-open the browser for authentication.

> `credentials.json` never needs to be deleted — it comes from Google Cloud Console and stays the same.

---

## Customization

- **Prompts**: Edit files in `src/prompts/` to change how procedures are written per category.
- **RAG retrieval count**: Change `k=8` in `src/agents.py` to retrieve more or fewer document chunks.
- **Blocked senders**: Add email domains or addresses to `config/skipped_senders.txt` (one per line).
- **Check interval**: Change `CHECK_INTERVAL_SECONDS` in `main.py` (default: 60 seconds).
- **FortiToken sheet names**: Change `ALL_USERS_SHEET` and `ACTIONS_QUEUE_SHEET` in `src/tools/GoogleSheetsFortiToken.py` if your sheet tabs have different names.
