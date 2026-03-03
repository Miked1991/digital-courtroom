# digital-courtroom

---

## Prerequisites

- Python 3.10 or higher
- Git
- GROQ API KEY 
- LangSmith API key for tracing

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/automaton-auditor.git
cd automaton-auditor


----------------set up environment-----------------


# Using uv (recommended)
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Or using standard venv
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate


-----------------install dependencies--------------------

# Using uv
uv pip install -r requirements.txt

# Using pip
pip install -r requirements.txt


`------------------- configure environmental variable(.env) -------------------`
#this process dependes on the provider we use 
# Required
GROQ_API_KEY=groqapikey
 

# LangSmith Configuration
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"
LANGCHAIN_API_KEY=langchainapi
LANGCHAIN_PROJECT=automaton-auditor

# Default Model Configuration
DEFAULT_LLM_MODEL=lallma- qwen 
VISION_LLM_MODEL=lallma- instant 

# Temporary Directory for Cloning
TEMP_DIR=/tmp/automaton-auditor

# Logging Level
LOG_LEVEL=INFO


#project structure

automaton-auditor/
├── src/
│   ├── graph.py              # Main LangGraph orchestration
│   ├── state.py              # Pydantic state models
│   ├── nodes/
│   │   ├── detectives.py     # Forensic evidence collectors
│   │   ├── judges.py         # Dialectical judges with rate limiting
│   │   └── justice.py        # Chief Justice synthesis
│   ├── tools/
│   │   ├── repo_tools.py      # Sandboxed git operations
│   │   ├── ast_tools.py      # AST parsing utilities
│   │   ├── doc_tools.py      # PDF analysis (PyMuPDF)
│   │   └── vision_tools.py   # Diagram analysis
│   └── config/
│       └── prompts.py        # Centralized prompt management
├── rubric/
│   └── week2_rubric.json     # Machine-readable grading rubric
├── audits/
│   ├── report_onself_generated/   # Your self-audit reports
│   ├── report_onpeer_generated/   # Audits of peers
│   ├── report_bypeer_received/    # Reports from peers
│   └── langsmith_logs/            # Execution traces
├── main.py                   # CLI entry point
├── run_audit.py              # Interactive runner
├── .env.example              # Environment variables template
├── requirements.txt          # Production dependencies     
├── Dockerfile                # Container configuration
└── README.md                 # This file

----------------------//------------------------