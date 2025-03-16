import os
import json
from typing import List, Dict, Any, Optional, Tuple
import openai
from qdrant_client import QdrantClient
from qdrant_client.http import models
from upsert_to_qdrant import generate_embedding, prepare_candidate_for_embedding, prepare_job_for_embedding, COLLECTION_NAME

# Set your OpenAI API key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Please set the OPENAI_API_KEY environment variable")

openai.api_key = OPENAI_API_KEY

# Qdrant client configuration
QDRANT_URL = os.environ.get("QDRANT_URL", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", 6333))
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY")

def get_client():
    """Initialize the Qdrant client."""
    # Check if we're using Qdrant Cloud or local instance
    if QDRANT_URL != "localhost" and QDRANT_API_KEY:
        # For Qdrant Cloud
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        print("Connected to Qdrant Cloud")
    else:
        # For local Qdrant
        client = QdrantClient(host=QDRANT_URL, port=QDRANT_PORT)
        print("Connected to local Qdrant instance")
    
    return client

def search_similar_candidates(client: QdrantClient, job: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    """Search for candidates similar to a job posting."""
    # Prepare job for embedding
    text_for_embedding = prepare_job_for_embedding(job)
    
    # Generate embedding
    embedding = generate_embedding(text_for_embedding)
    
    # Search for similar candidates
    search_result = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=embedding,
        query_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="type",
                    match=models.MatchValue(value="candidate")
                )
            ]
        ),
        limit=limit
    )
    
    # Extract and return results
    candidates = []
    for result in search_result:
        candidate_data = result.payload["data"]
        candidates.append({
            "candidate": candidate_data,
            "score": result.score,
            "job": job
        })
    
    return candidates

def search_similar_jobs(client: QdrantClient, candidate: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    """Search for jobs similar to a candidate profile."""
    # Prepare candidate for embedding
    text_for_embedding = prepare_candidate_for_embedding(candidate)
    
    # Generate embedding
    embedding = generate_embedding(text_for_embedding)
    
    # Search for similar jobs
    search_result = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=embedding,
        query_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="type",
                    match=models.MatchValue(value="job")
                )
            ]
        ),
        limit=limit
    )
    
    # Extract and return results
    jobs = []
    for result in search_result:
        job_data = result.payload["data"]
        jobs.append({
            "job": job_data,
            "score": result.score,
            "candidate": candidate
        })
    
    return jobs

def find_all_matches(client: QdrantClient, limit_per_match: int = 5) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Find matches for all candidates and jobs in the database."""
    # Get all points from the collection
    scroll_result = client.scroll(
        collection_name=COLLECTION_NAME,
        limit=1000  # Adjust based on your expected data size
    )
    
    points = scroll_result[0]
    
    # Separate candidates and jobs
    candidates = []
    jobs = []
    
    for point in points:
        if point.payload["type"] == "candidate":
            candidates.append(point.payload["data"])
        elif point.payload["type"] == "job":
            jobs.append(point.payload["data"])
    
    # Find matches for candidates
    candidate_matches = []
    for candidate in candidates:
        matches = search_similar_jobs(client, candidate, limit=limit_per_match)
        if matches:
            candidate_matches.append({
                "candidate": candidate,
                "matches": matches
            })
    
    # Find matches for jobs
    job_matches = []
    for job in jobs:
        matches = search_similar_candidates(client, job, limit=limit_per_match)
        if matches:
            job_matches.append({
                "job": job,
                "matches": matches
            })
    
    return candidate_matches, job_matches

def search_by_text(client: QdrantClient, search_text: str, limit: int = 10, search_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Search for candidates or jobs matching a text query."""
    # Generate embedding for the search text
    embedding = generate_embedding(search_text)
    
    # Set up filter based on search type
    query_filter = None
    if search_type:
        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="type",
                    match=models.MatchValue(value=search_type)
                )
            ]
        )
    
    # Perform the search
    search_result = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=embedding,
        query_filter=query_filter,
        limit=limit
    )
    
    # Extract and return results
    results = []
    for result in search_result:
        item_type = result.payload["type"]
        item_data = result.payload["data"]
        
        results.append({
            "type": item_type,
            "data": item_data,
            "score": result.score
        })
    
    return results

def print_matches(matches, match_type="candidate"):
    """Pretty print matches."""
    if match_type == "candidate":
        for entry in matches:
            candidate = entry["candidate"]
            print(f"\nCandidate: {candidate.get('Email', 'No email')} ({candidate.get('Location', 'Unknown location')})")
            print(f"Summary: {candidate.get('Summary', 'No summary')}")
            
            for idx, match in enumerate(entry["matches"], 1):
                job = match["job"]
                score = match["score"] * 100  # Convert to percentage
                
                print(f"  Match {idx} ({score:.1f}%): {job.get('Company', 'Unknown company')} - {job.get('Position', 'Unknown position')}")
                print(f"    Location: {job.get('Location', 'Not specified')}")
                print(f"    Remote: {job.get('Remote', 'Not specified')}")
                print(f"    Technologies: {job.get('Technologies', 'Not specified')}")
            
            print("-" * 50)
    else:
        for entry in matches:
            job = entry["job"]
            print(f"\nJob: {job.get('Company', 'Unknown company')} - {job.get('Position', 'Unknown position')}")
            print(f"Summary: {job.get('Summary', 'No summary')}")
            
            for idx, match in enumerate(entry["matches"], 1):
                candidate = match["candidate"]
                score = match["score"] * 100  # Convert to percentage
                
                print(f"  Match {idx} ({score:.1f}%): {candidate.get('Email', 'No email')} ({candidate.get('Location', 'Unknown location')})")
                print(f"    Remote: {candidate.get('Remote', 'Not specified')}")
                print(f"    Technologies: {candidate.get('Technologies', 'Not specified')}")
            
            print("-" * 50)

def main():
    # Initialize Qdrant client
    client = get_client()
    
    # Check if the collection exists
    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]
    
    if COLLECTION_NAME not in collection_names:
        print(f"Collection '{COLLECTION_NAME}' does not exist. Please run upsert_to_qdrant.py first.")
        return
    
    while True:
        print("\n=== HN Jobs & Candidates Vector Search ===")
        print("1. Find matches for all candidates")
        print("2. Find matches for all jobs")
        print("3. Search by text query")
        print("4. Exit")
        
        choice = input("Enter your choice (1-4): ")
        
        if choice == "1":
            candidate_matches, _ = find_all_matches(client)
            print("\n=== Candidate Matches ===")
            print_matches(candidate_matches, "candidate")
            
            # Save results to file
            with open("vector_candidate_matches.json", "w") as f:
                json.dump(candidate_matches, f, indent=2)
            print("Results saved to vector_candidate_matches.json")
            
        elif choice == "2":
            _, job_matches = find_all_matches(client)
            print("\n=== Job Matches ===")
            print_matches(job_matches, "job")
            
            # Save results to file
            with open("vector_job_matches.json", "w") as f:
                json.dump(job_matches, f, indent=2)
            print("Results saved to vector_job_matches.json")
            
        elif choice == "3":
            search_text = input("Enter search text: ")
            search_type = input("Search type (candidate/job/both, default=both): ").lower()
            
            if search_type not in ["candidate", "job"]:
                search_type = None
            
            results = search_by_text(client, search_text, limit=10, search_type=search_type)
            
            print("\n=== Search Results ===")
            for idx, result in enumerate(results, 1):
                item_type = result["type"]
                data = result["data"]
                score = result["score"] * 100  # Convert to percentage
                
                if item_type == "candidate":
                    print(f"{idx}. Candidate ({score:.1f}%): {data.get('Email', 'No email')} ({data.get('Location', 'Unknown location')})")
                    print(f"   Summary: {data.get('Summary', 'No summary')}")
                else:
                    print(f"{idx}. Job ({score:.1f}%): {data.get('Company', 'Unknown company')} - {data.get('Position', 'Unknown position')}")
                    print(f"   Summary: {data.get('Summary', 'No summary')}")
                
                print()
            
        elif choice == "4":
            print("Exiting...")
            break
            
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main() 