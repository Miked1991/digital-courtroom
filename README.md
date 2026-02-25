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
OPENAI_API_KEY=your_openai_api_key_here

# Optional for Claude
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Optional for tracing
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key_here
LANGCHAIN_PROJECT=automaton-auditor



----------------------//------------------------