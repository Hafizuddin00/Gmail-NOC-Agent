from colorama import Fore, Style
import time
from src.graph import Workflow
from dotenv import load_dotenv

# Load all env variables
load_dotenv()

# config 
config = {'recursion_limit': 100}

workflow = Workflow()
app = workflow.app

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
      "attachments": ""
    },
    "email_category": "",
    "generated_email": "",
    "rag_queries": [],
    "retrieved_documents": "",
    "writer_messages": [],
    "sendable": False,
    "trials": 0
}

# Run the automation
print(Fore.GREEN + "Starting workflow in continuous mode..." + Style.RESET_ALL)
CHECK_INTERVAL_SECONDS = 60 # Check for new emails every 60 seconds

while True:
    print(Fore.YELLOW + "\nChecking for new emails..." + Style.RESET_ALL)
    for output in app.stream(initial_state, config):
        for key, value in output.items():
            print(Fore.CYAN + f"Finished running: {key}:" + Style.RESET_ALL)
            
    print(Fore.MAGENTA + f"Waiting {CHECK_INTERVAL_SECONDS} seconds before the next check..." + Style.RESET_ALL)
    time.sleep(CHECK_INTERVAL_SECONDS)


