<!--
Title: Network Operations Center (NOC) Email Automation System | Langchain/Langgraph Integration
Description: Automate NOC email handling with our system built using Langchain/Langgraph. Features include email categorization, query synthesis, internal NOC action procedure drafting, and procedure verification.
Keywords: NOC automation, email automation, Langchain, Langgraph, AI NOC agents, Gmail API, Python email automation, email categorization, SOP integration, AI agents
-->

# 🚀 **Network Operations Center (NOC) Email Automation with AI Agents and RAG**

## **Features**  

### **NOC Inbox Management with AI Agents**  

- **Continuously monitors** the NOC team's Gmail inbox.
- **Categorizes emails** into '**network_issue**,' '**maintenance_notification**,' '**general_inquiry**,' '**ewh_fortitoken**,' or '**unrelated**'.
- **Automatically flags irrelevant emails** to ensure the NOC team focuses only on operational priorities.

### **Internal Procedure Generation**  

- **Drafts actionable internal procedures** detailing the exact steps the NOC officer must take to handle the request.
- Utilizes **RAG techniques** to extract instructions from ingested agency SOPs and knowledge bases.
- **Formats procedures clearly** with Request Type, Sender, Subject, Summary, and numbered Action Steps.

### **Quality Assurance with AI**  

- **Automatically acts as a Senior NOC Team Lead** to check procedure completeness, accuracy, and clarity.
- **Ensures every drafted procedure** meets internal standards and contains actionable steps before it reaches the NOC officer.

## **How It Works**  

1. **Email Monitoring**: The system **constantly checks** for new emails in the NOC Gmail inbox using the **Gmail API**.  
2. **Email Categorization**: **AI agents** sort each email into **predefined NOC categories**.  
3. **Procedure Generation**:   
   - The system synthesizes the core issue from the email.
   - Using **RAG**, it retrieves **accurate SOP steps** from ingested documents.
   - It **drafts an internal action checklist** for the NOC officer.  
4. **Output**: **Approved procedures** are generated, ensuring the NOC team can execute the required actions **promptly and correctly**.  

## System Flowchart

This is the detailed flow of the system:

[![](https://mermaid.ink/img/pako:eNqllN9v2jAQx_8Vy5X2RLuQtPzIw6aQbqgqq7SwComkQia-BAvHzhynQIH_fU7Cjz3sYbQPlnzfu8-d7-xki2NJAbs44XIVL4jS6Nd9pCLhhT-kYFoqNMwI4-hBzOX6pfag6-svaLB9KBoRfctyvfm6r3yDyrd7kugJVkY3YLFD03BCmEYdC40hloIWdZppk-ZMfZeloOhZEFGsQAE98X7oEw2pVOwNGrFOUC2_Jp-FAm5C6A6NH8PxkuXoExpwEi85K0xDCwWEvpzjuUxnRBC-KZhJP_LCkUyRdxDQRDEN6q_wmKm4ZHpG5Uqgz4gzsZwlnOQ5E6mxc1MH9IzLojCWOZ7QYJqIwViwWswSqbQZ5BIqOAUBivAZE79LpjY7FIS-FIVWZaxR4A3RzxIUg-LUYbWCelRBEAagjfMVUKJkVoXXYUHjn4TNyZFniuhTgkntHIa-GYKGw23eK5I0IaPmOofH8GFzg7DWzah3zRWNH_-tV6vQGw7IQwnj3L1K-knL9GP6da96vd5hf71iVC9cO1-3Ysmlcq8syzrDgwM8n59hx3H-D_aPlefzy-HgQ_CJTvqX05Nj08k7So-8j9DDA9x_z7nNW2hoSunl9PQ0MrgExi2cKkaxaz4VaOEMlHmFxsTbSCAUYb2ADCLsmi0lahnhSOwNkxMxlTI7YkqW6QK7CeGFscqcmk_inpFUkeykKhAUlG_-Rhq7nbZdJ8HuFq-xazvdG9vqOn2nbbWdbtu5beENdu96N23HdjpGue12un27s2_ht7qudVMJ_bu7ju3Y3VunZ-__AJAy1oI?type=png)](https://mermaid.live/edit#pako:eNqllN9v2jAQx_8Vy5X2RLuQtPzIw6aQbqgqq7SwComkQia-BAvHzhynQIH_fU7Cjz3sYbQPlnzfu8-d7-xki2NJAbs44XIVL4jS6Nd9pCLhhT-kYFoqNMwI4-hBzOX6pfag6-svaLB9KBoRfctyvfm6r3yDyrd7kugJVkY3YLFD03BCmEYdC40hloIWdZppk-ZMfZeloOhZEFGsQAE98X7oEw2pVOwNGrFOUC2_Jp-FAm5C6A6NH8PxkuXoExpwEi85K0xDCwWEvpzjuUxnRBC-KZhJP_LCkUyRdxDQRDEN6q_wmKm4ZHpG5Uqgz4gzsZwlnOQ5E6mxc1MH9IzLojCWOZ7QYJqIwViwWswSqbQZ5BIqOAUBivAZE79LpjY7FIS-FIVWZaxR4A3RzxIUg-LUYbWCelRBEAagjfMVUKJkVoXXYUHjn4TNyZFniuhTgkntHIa-GYKGw23eK5I0IaPmOofH8GFzg7DWzah3zRWNH_-tV6vQGw7IQwnj3L1K-knL9GP6da96vd5hf71iVC9cO1-3Ysmlcq8syzrDgwM8n59hx3H-D_aPlefzy-HgQ_CJTvqX05Nj08k7So-8j9DDA9x_z7nNW2hoSunl9PQ0MrgExi2cKkaxaz4VaOEMlHmFxsTbSCAUYb2ADCLsmi0lahnhSOwNkxMxlTI7YkqW6QK7CeGFscqcmk_inpFUkeykKhAUlG_-Rhq7nbZdJ8HuFq-xazvdG9vqOn2nbbWdbtu5beENdu96N23HdjpGue12un27s2_ht7qudVMJ_bu7ju3Y3VunZ-__AJAy1oI)

## Tech Stack

* Langchain & Langgraph: for developing AI agents workflow.
* Langserve: simplify API development & deployment (using FastAPI).
* Gemini API: for LLM and embeddings access.
* Google Gmail API
* ChromaDB: for vector storage.

## How to Run

### Prerequisites

- Python 3.10 or higher (3.13 recommended)
- Google Gemini api key (for LLM and embeddings)
- Gmail API credentials
- Necessary Python libraries (listed in `requirements.txt`)

### Setup

1. **Create and activate a virtual environment:**

   ```sh
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

2. **Install the required packages:**

   ```sh
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**

   Create a `.env` file in the root directory of the project and add your GMAIL address. We are using the Google Gemini model for both processing and embeddings, so you must get an API key:

   ```env
   MY_EMAIL=your_email@gmail.com
   GOOGLE_API_KEY=your_gemini_api_key
   ```

4. **Populate the knowledge base:**

   The `data/` files is not included in the repository. Copy the SOP and knowledge base files from the shared drive into the `data/` folder. The files can be found in:

   ```
   ~\sharing\Operations\data
   ```

5. **Ensure Gmail API is enabled:**

   Follow [this guide](https://developers.google.com/gmail/api/quickstart/python) to enable Gmail API and obtain your credentials. Place the `credentials.json` in `\config`.

6. **Build the vector store** 

   ```sh
   python scripts/create_index.py
   ```

### Running the Application

1. **Start the workflow:**

   ```sh
   python main.py
   ```

   The application will start checking for new emails, categorizing them, synthesizing queries, drafting internal NOC action procedures, and verifying the drafted procedure's quality.

2. **Deploy as API:** you can deploy the workflow as an API using Langserve and FastAPI by running the command below:

   ```sh
   python deploy_api.py
   ```

   The workflow api will be running on `localhost:8000`, you can consult the API docs on `/docs` and you can use the langsergve playground (on the route `/playground`) to test it out.

### Starting Fresh

If you need to reset the agent (e.g. switching Gmail accounts, fixing auth errors, or clearing all state), follow these steps:

1. **Delete the Gmail OAuth token** — forces re-authentication on next run:

   ```sh
   del config\token.json
   ```

2. **Clear skipped threads** — resets the list of blacklisted email threads:

   ```sh
   echo [] > config\skipped_threads.json
   ```

3. **Rebuild the vector store** — if you've changed files in the `data` folder:

   ```sh
   python scripts/create_index.py
   ```

4. **Re-authenticate Gmail** — on the next `python main.py` run, a browser window will open asking you to sign in and grant Gmail access. A new `token.json` will be saved automatically in `config/`.

> **Note:** You do not need to touch `credentials.json` — that file comes from Google Cloud Console and stays the same. Only `token.json` needs to be deleted when re-authenticating.

---

### Customization

You can customize the behavior of each agent by modifying the corresponding methods in the `Nodes` class or the agents prompt `prompts` located in the `src` directory.

You can also add your own agency data into the `data` folder, then you must create your own vector store by running:

```sh
python scripts/create_index.py
```