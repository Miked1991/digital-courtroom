# digital-courtroom

---

## Prerequisites

- Python 3.10 or higher
- Git
- OpenAI API key (or Anthropic)
- (Optional) LangSmith API key for tracing

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
GEMINAI_API_KEY=geminaiapi
 

# LangSmith Configuration
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"
LANGCHAIN_API_KEY=langchainapi
LANGCHAIN_PROJECT=automaton-auditor

# Default Model Configuration
DEFAULT_LLM_MODEL=gemini-3-pro-preview
VISION_LLM_MODEL=gemini-2.5-flash-image

# Temporary Directory for Cloning
TEMP_DIR=/tmp/automaton-auditor

# Logging Level
LOG_LEVEL=INFO



----------------------//------------------------