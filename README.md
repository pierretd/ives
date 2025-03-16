# Ives - HN Jobs & Candidates Matching System

A system that scrapes Hacker News "Who is hiring" and "Who wants to be hired" threads, extracts structured data, and uses semantic search to match candidates with relevant jobs.

## Features

- Extracts candidate information from "Who wants to be hired" threads
- Extracts job postings from "Who is hiring" threads
- Creates structured data from unstructured text
- Performs basic rule-based matching using location, remote preferences, and technologies
- Generates vector embeddings for semantic search
- Stores data in Qdrant vector database for similarity searches
- Provides an interactive Streamlit dashboard for visualizing matches

## Setup

### Prerequisites

- Python 3.9+
- An OpenAI API key for generating embeddings
- Either a local Qdrant server or a Qdrant Cloud account

### Installation

1. Clone this repository:
```bash
git clone https://github.com/pierretd/ives.git
cd ives
```

2. Create a virtual environment (recommended):
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file with your API keys:
```
OPENAI_API_KEY=your-openai-api-key
QDRANT_URL=your-qdrant-url
QDRANT_API_KEY=your-qdrant-api-key  # Only needed for Qdrant Cloud
```

## Usage

### Data Collection and Processing

1. Extract candidates from "Who wants to be hired" threads:
```bash
python extract_hn_candidates.py
```

2. Extract job postings from "Who is hiring" threads:
```bash
python extract_hn_jobs.py
```

3. Run rule-based matching:
```bash
python job_matcher.py
```

4. Generate embeddings and store in Qdrant:
```bash
python upsert_to_qdrant.py
```

5. Run semantic search to find matches:
```bash
python vector_search.py
```

### Using the Streamlit Dashboard

View the matching results in an interactive dashboard:

```bash
streamlit run streamlit_app.py
```

### Using the Interactive CLI

You can also use the wrapper script for a command-line interface:

```bash
python run_job_matcher.py
```

This will provide an interactive menu with all available options.

## How Matching Works

### Rule-Based Matching

The basic matching algorithm considers:
- Remote work preferences (25 points)
- Location match or relocation willingness (10-20 points)
- Technology overlap (up to 55 points)

A minimum match score (default: 40%) is required for a match to be considered valid.

### Semantic Matching

The semantic matching uses OpenAI embeddings to find similar candidates and jobs based on:
- The entire profile content (not just keywords)
- Semantic understanding of skills and requirements
- Context of the job or candidate

This often produces better matches than the rule-based approach, as it can understand related technologies and roles even when exact keywords don't match.

## Project Structure

- `extract_hn_candidates.py` - Extracts candidate data from HN threads
- `extract_hn_jobs.py` - Extracts job posting data from HN threads
- `job_matcher.py` - Performs rule-based matching
- `vector_search.py` - Performs semantic search using Qdrant
- `upsert_to_qdrant.py` - Generates embeddings and uploads to Qdrant
- `streamlit_app.py` - Interactive dashboard for visualizing matches
- `run_job_matcher.py` - CLI wrapper for all functionality
- `explore_qdrant.py` - Utility for exploring data in Qdrant
- `get_data.py` - Utility functions for data collection

## License

MIT License 