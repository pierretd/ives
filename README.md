# HN Jobs & Candidates Matching System

This system scrapes Hacker News "Who is hiring" and "Who wants to be hired" threads, extracts structured data, and uses semantic search to match candidates with relevant jobs.

## Features

- Extracts candidate information from "Who wants to be hired" threads
- Extracts job postings from "Who is hiring" threads
- Creates structured data from unstructured text
- Performs basic rule-based matching using location, remote preferences, and technologies
- Generates vector embeddings for semantic search
- Stores data in Qdrant vector database for similarity searches
- Provides an interactive interface for searching and matching

## Setup

### Prerequisites

- Python 3.9+
- An OpenAI API key for generating embeddings
- Either a local Qdrant server or a Qdrant Cloud account

### Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/hn-job-matcher.git
cd hn-job-matcher
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your OpenAI API key:
```bash
export OPENAI_API_KEY="your-api-key-here"
```

4. Configure Qdrant:

   **Option 1: Local Qdrant Instance**
   ```bash
   export QDRANT_URL="localhost"
   export QDRANT_PORT=6333
   ```
   
   **Option 2: Qdrant Cloud**
   ```bash
   export QDRANT_URL="your-cluster-url.cloud.qdrant.io"
   export QDRANT_API_KEY="your-qdrant-api-key"
   ```

   Alternatively, create a `.env` file with these variables.

## Usage

The easiest way to use the system is through the wrapper script:
```bash
python run_job_matcher.py
```

This will provide an interactive menu with all available options.

Alternatively, you can run individual scripts:

### 1. Data Extraction

Extract candidate information from "Who wants to be hired" threads:
```bash
python extract_hn_candidates.py
```

Extract job postings from "Who is hiring" threads:
```bash
python extract_hn_jobs.py
```

### 2. Basic Matching

Run the rule-based matcher to find potential matches between candidates and jobs:
```bash
python job_matcher.py
```

This will:
- Extract data from both threads
- Generate summaries for each candidate and job
- Calculate match scores based on location, remote status, and technology overlap
- Print the results and save them to `job_matching_results.json`

### 3. Semantic Search with Qdrant

First, generate embeddings and upsert data to Qdrant:
```bash
python upsert_to_qdrant.py
```

Then, perform vector searches for semantic matching:
```bash
python vector_search.py
```

This interactive tool provides several options:
1. Find matches for all candidates
2. Find matches for all jobs
3. Search by text query
4. Exit

Results will be saved to `vector_candidate_matches.json` and `vector_job_matches.json`.

## Qdrant Cloud Setup

[Qdrant Cloud](https://cloud.qdrant.io/) is a fully managed vector database service that eliminates the need to set up and maintain your own Qdrant server.

To use Qdrant Cloud with this system:

1. Create an account at [cloud.qdrant.io](https://cloud.qdrant.io/)
2. Create a new cluster (free tier available)
3. Get your cluster URL and API key
4. Add them to your `.env` file:
   ```
   QDRANT_URL=https://your-cluster-id.region.cloud.qdrant.io
   QDRANT_API_KEY=your-api-key
   ```

The system will automatically detect that you're using Qdrant Cloud and connect accordingly.

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

## Customization

You can customize the system by:
- Modifying the regex patterns in extraction scripts
- Adjusting the matching weights in `job_matcher.py`
- Changing the minimum match score
- Using different embedding models

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Hacker News for hosting the "Who is hiring" and "Who wants to be hired" threads
- OpenAI for the embedding model
- Qdrant for the vector database 