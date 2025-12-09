# RunnerVision AI

Safety-aware running route recommendations for NYC runners using multi-agent LLM system.

## Quick Start

### Setup
```bash
# Clone repository
git clone https://github.com/lgp3212/runner_vision.git
cd runner_vision

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Mac/Linux
# OR
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root:
```
OPENAI_API_KEY=your_key_here
GOOGLE_ROUTES_API_KEY=your_key_here
OPENWEATHER_API_KEY=your_key_here
SUPABASE_DB_URL=your_db_url
SUPABASE_DB_PASSWORD=your_password
LANGFUSE_PUBLIC_KEY=your_key_here
LANGFUSE_SECRET_KEY=your_key_here
```

### Run
```bash
python -m streamlit run app.py
```

App opens at `http://localhost:8501`

## Usage

Try these queries:

- "Give me a 5km route"
- "I need a safe route"
- "Generate a safe route that avoids construction"

## How It Works

6 specialized agents powered by LangGraph:

1. Router - analyzes query intent
2. Route Generation - creates 8 directional options
3. Safety Analysis - evaluates crash risk
4. Weather - checks current conditions
5. Closures - detects construction
6. Synthesis - GPT-4o-mini generates recommendation

## Features

- 60 days NYC crash data analysis
- Real-time street closures
- Weather conditions
- Interactive safety-coded map
- Natural language interface
- Conditional routing (70% faster for simple queries)

## Troubleshooting

### Import errors
```bash
pip install --upgrade -r requirements.txt
```

### Streamlit cache issues
```bash
streamlit cache clear
```

### Missing .env file
Copy template above and fill in your API keys

## Team

Lindsey Pietrewicz, Henry Yuan, Raymond Zhang

NYU DS-UA 301 Fall 2024