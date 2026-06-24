"""
Entry point for the Gmail NOC Agent.

Runs the LangGraph workflow in a continuous loop, checking for new emails
every CHECK_INTERVAL_SECONDS seconds.  All output goes to both the console
and logs/agent.log.
"""

import os
import sys
import time
import signal

from dotenv import load_dotenv

# ── Logging must be set up before any other project imports ────────────────────
from src.logger import setup_logging, get_logger
setup_logging()
logger = get_logger("main")

from src.graph import Workflow  # noqa: E402  (after logging init)

# ── Load environment variables ─────────────────────────────────────────────────
load_dotenv()

# ── Write PID file so manage scripts can find the process ─────────────────────
PID_FILE = os.path.join(os.path.dirname(__file__), "agent.pid")

def _write_pid():
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))
    logger.info(f"Agent started | PID={os.getpid()} | PID file → {PID_FILE}")

def _remove_pid():
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)
    logger.info("PID file removed — agent stopped cleanly.")

# ── Graceful shutdown on SIGINT / SIGTERM ──────────────────────────────────────
def _handle_signal(signum, frame):
    logger.warning(f"Received signal {signum}. Shutting down gracefully...")
    _remove_pid()
    sys.exit(0)

signal.signal(signal.SIGINT,  _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)

# ── Workflow setup ─────────────────────────────────────────────────────────────
CHECK_INTERVAL_SECONDS = 60  # Check for new emails every 60 seconds

config = {"recursion_limit": 100}

initial_state = {
    "emails": [],
    "current_email": {
        "id": "",
        "threadId": "",
        "messageId": "",
        "references": "",
        "sender": "",
        "subject": "",
        "body": "",
        "attachments": "",
    },
    "email_category": "",
    "generated_email": "",
    "rag_queries": [],
    "retrieved_documents": "",
    "writer_messages": [],
    "sendable": False,
    "trials": 0,
}

# ── Main loop ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    _write_pid()
    logger.info("=" * 60)
    logger.info("Gmail NOC Agent starting in continuous mode")
    logger.info(f"Check interval: {CHECK_INTERVAL_SECONDS}s")
    logger.info("=" * 60)

    workflow = Workflow()
    app = workflow.app

    cycle = 0
    while True:
        cycle += 1
        logger.info(f"── Cycle #{cycle} | Checking for new emails... ──")

        try:
            for output in app.stream(initial_state, config):
                for node_name, value in output.items():
                    logger.info(f"Node completed: {node_name}")

        except Exception as exc:
            logger.error(f"Unhandled exception in cycle #{cycle}: {exc}", exc_info=True)

        logger.info(
            f"── Cycle #{cycle} done | Sleeping {CHECK_INTERVAL_SECONDS}s "
            f"before next check ──"
        )
        time.sleep(CHECK_INTERVAL_SECONDS)
