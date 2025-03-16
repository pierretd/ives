import json
import os
import time
from typing import List, Dict, Any
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http import models
from job_matcher import extract_candidate_fields, extract_job_fields, generate_candidate_summary, generate_job_summary, clean_html
import uuid

# Set your OpenAI API key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Please set the OPENAI_API_KEY environment variable")

# Initialize OpenAI client
client_openai = OpenAI(api_key=OPENAI_API_KEY)

# Qdrant client configuration
QDRANT_URL = os.environ.get("QDRANT_URL", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", 6333))
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY")
COLLECTION_NAME = "hacker_news_jobs"
VECTOR_SIZE = 1536  # Size of OpenAI's text-embedding-ada-002 embeddings
BATCH_SIZE = 20  # Number of items to process in a single batch

def generate_embedding(text: str) -> List[float]:
    """Generate an embedding for the given text using OpenAI's API."""
    response = client_openai.embeddings.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response.data[0].embedding

def prepare_candidate_for_embedding(candidate: Dict[str, Any]) -> str:
    """Prepare candidate data for embedding by creating a rich text representation."""
    parts = []
    
    # Add basic information
    if candidate.get("Location"):
        parts.append(f"Location: {candidate['Location']}")
    
    if candidate.get("Remote"):
        parts.append(f"Remote: {candidate['Remote']}")
    
    if candidate.get("Willing to Relocate"):
        parts.append(f"Willing to Relocate: {candidate['Willing to Relocate']}")
    
    if candidate.get("Technologies"):
        parts.append(f"Skills: {candidate['Technologies']}")
    
    # Add the summary
    if candidate.get("Summary"):
        parts.append(f"Summary: {candidate['Summary']}")
    
    # Add the raw text content if available
    if candidate.get("Raw Text"):
        parts.append(f"Details: {candidate['Raw Text']}")
    
    return "\n".join(parts)

def prepare_job_for_embedding(job: Dict[str, Any]) -> str:
    """Prepare job data for embedding by creating a rich text representation."""
    parts = []
    
    # Add company and position information
    if job.get("Company"):
        parts.append(f"Company: {job['Company']}")
    
    if job.get("Position"):
        parts.append(f"Position: {job['Position']}")
    
    if job.get("Location"):
        parts.append(f"Location: {job['Location']}")
    
    if job.get("Remote"):
        parts.append(f"Remote: {job['Remote']}")
    
    if job.get("Salary"):
        parts.append(f"Salary: {job['Salary']}")
    
    if job.get("Technologies"):
        parts.append(f"Technologies: {job['Technologies']}")
    
    # Add the summary and description
    if job.get("Summary"):
        parts.append(f"Summary: {job['Summary']}")
    
    if job.get("Description"):
        parts.append(f"Description: {job['Description']}")
    
    # Add the raw text content if available
    if job.get("Raw Text"):
        parts.append(f"Details: {job['Raw Text']}")
    
    return "\n".join(parts)

def init_qdrant_collection():
    """Initialize the Qdrant collection for storing job and candidate vectors."""
    # Check if we're using Qdrant Cloud or local instance
    if QDRANT_URL != "localhost" and QDRANT_API_KEY:
        # For Qdrant Cloud
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        print("Connected to Qdrant Cloud")
    else:
        # For local Qdrant
        client = QdrantClient(host=QDRANT_URL, port=QDRANT_PORT)
        print("Connected to local Qdrant instance")
    
    # Check if collection exists
    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]
    
    if COLLECTION_NAME not in collection_names:
        # Create a new collection
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=VECTOR_SIZE,
                distance=models.Distance.COSINE
            )
        )
        
        # Create payload index for type field to enable filtering
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="type",
            field_schema=models.PayloadSchemaType.KEYWORD
        )
    
    return client

def process_batch(client, items, item_type):
    """Process a batch of items (candidates or jobs) and upsert them to Qdrant."""
    points = []
    prepare_fn = prepare_candidate_for_embedding if item_type == "candidate" else prepare_job_for_embedding
    
    for item in items:
        # Generate a unique UUID for the item
        item_id = str(uuid.uuid4())
        
        # Prepare text for embedding
        text_for_embedding = prepare_fn(item)
        
        # Generate embedding
        embedding = generate_embedding(text_for_embedding)
        
        # Create a point
        points.append(
            models.PointStruct(
                id=item_id,
                vector=embedding,
                payload={
                    "type": item_type,
                    "data": item
                }
            )
        )
    
    # Upsert points to Qdrant
    try:
        operation_info = client.upsert(
            collection_name=COLLECTION_NAME,
            wait=True,
            points=points
        )
        print(f"Successfully upserted {len(points)} {item_type}s. Operation ID: {operation_info.operation_id}")
        return len(points)
    except Exception as e:
        print(f"Error upserting batch: {str(e)}")
        return 0

def upsert_to_qdrant_in_batches(client, candidates, jobs):
    """Upsert candidates and jobs to Qdrant in batches to avoid timeouts."""
    total_candidates = 0
    total_jobs = 0
    
    # Process candidates in batches
    print(f"Processing {len(candidates)} candidates in batches of {BATCH_SIZE}...")
    for i in range(0, len(candidates), BATCH_SIZE):
        batch = candidates[i:i+BATCH_SIZE]
        print(f"Processing candidate batch {i//BATCH_SIZE + 1}/{(len(candidates) + BATCH_SIZE - 1)//BATCH_SIZE}")
        total_candidates += process_batch(client, batch, "candidate")
        time.sleep(1)  # Add a short delay between batches to avoid rate limits
    
    # Process jobs in batches
    print(f"Processing {len(jobs)} jobs in batches of {BATCH_SIZE}...")
    for i in range(0, len(jobs), BATCH_SIZE):
        batch = jobs[i:i+BATCH_SIZE]
        print(f"Processing job batch {i//BATCH_SIZE + 1}/{(len(jobs) + BATCH_SIZE - 1)//BATCH_SIZE}")
        total_jobs += process_batch(client, batch, "job")
        time.sleep(1)  # Add a short delay between batches to avoid rate limits
    
    return total_candidates, total_jobs

def main():
    # Check if we have pre-existing match results
    if os.path.exists("job_matching_results.json"):
        print("Loading pre-existing match results...")
        with open("job_matching_results.json", "r") as f:
            data = json.load(f)
            candidates = data.get("candidates", [])
            jobs = data.get("jobs", [])
    else:
        # If not, load from the matcher script directly
        print("No pre-existing results found. Processing directly...")
        from job_matcher import fetch_hn_comments, CANDIDATES_THREAD_ID, JOBS_THREAD_ID
        
        # Fetch candidate and job data without limits
        print("Fetching candidate data...")
        candidate_comments = fetch_hn_comments(CANDIDATES_THREAD_ID)
        
        print("Fetching job data...")
        job_comments = fetch_hn_comments(JOBS_THREAD_ID)
        
        # Process candidates
        candidates = []
        for comment in candidate_comments:
            candidate = extract_candidate_fields(comment)
            candidate["id"] = comment.get("id", "")
            
            # Skip entries missing critical fields
            if not candidate["Email"] and not candidate["Resume"] and not candidate["Location"]:
                continue
                
            # Generate summary
            candidate["Summary"] = generate_candidate_summary(candidate)
            candidates.append(candidate)
        
        # Process jobs
        jobs = []
        for comment in job_comments:
            job = extract_job_fields(comment)
            job["id"] = comment.get("id", "")
            
            # Skip entries missing critical fields
            if not job["Company"] and not job["Position"]:
                continue
                
            # Generate summary
            job["Summary"] = generate_job_summary(job)
            jobs.append(job)
    
    print(f"Found {len(candidates)} candidates and {len(jobs)} jobs for processing.")
    
    # Initialize Qdrant client and collection
    print("Initializing Qdrant collection...")
    client = init_qdrant_collection()
    
    # Upsert data to Qdrant in batches
    print("Generating embeddings and upserting to Qdrant in batches...")
    total_candidates, total_jobs = upsert_to_qdrant_in_batches(client, candidates, jobs)
    
    print(f"Successfully upserted a total of {total_candidates} candidates and {total_jobs} jobs to Qdrant.")
    
    # Try getting collection info to verify, but catch errors from Qdrant Cloud version differences
    try:
        collection_info = client.get_collection(collection_name=COLLECTION_NAME)
        print(f"Collection info: {collection_info}")
    except Exception as e:
        print(f"NOTE: Could not retrieve detailed collection info due to: {e}")
        print("This is likely due to a version difference with Qdrant Cloud and doesn't affect functionality.")
    
    print("Done! You can now perform vector searches on candidates and jobs.")

if __name__ == "__main__":
    main() 