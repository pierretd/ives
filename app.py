import streamlit as st
import os
import json
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models
from openai import OpenAI

# Load environment variables
load_dotenv()

# API Keys and configurations
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
QDRANT_URL = os.environ.get("QDRANT_URL")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY")
COLLECTION_NAME = "hacker_news_jobs"

# Initialize clients
try:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
except TypeError:
    # Handle case where proxy settings might be causing issues
    openai_client = OpenAI(
        api_key=OPENAI_API_KEY,
        http_client=None  # Force using default client without proxy settings
    )

qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# Functions for working with Qdrant
def get_collection_info():
    """Get information about the Qdrant collection."""
    try:
        # Try to get points count in a safer way
        collection_points = qdrant_client.count(
            collection_name=COLLECTION_NAME,
            count_filter=None
        )
        
        return {
            "vector_size": 1536,  # Default for OpenAI embeddings
            "distance": "Cosine",
            "points_count": collection_points.count
        }
    except Exception as e:
        st.error(f"Error getting collection info: {str(e)}")
        return None

def get_candidates(limit=10):
    """Get candidate data from Qdrant."""
    try:
        candidate_points = qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter={
                "must": [
                    {"key": "type", "match": {"value": "candidate"}}
                ]
            },
            limit=limit,
            with_vectors=False
        )[0]
        
        candidates = []
        for point in candidate_points:
            candidates.append({
                "id": point.id,
                "data": point.payload.get("data", {})
            })
        
        return candidates
    except Exception as e:
        st.error(f"Error fetching candidates: {str(e)}")
        return []

def get_jobs(limit=10):
    """Get job data from Qdrant."""
    try:
        job_points = qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter={
                "must": [
                    {"key": "type", "match": {"value": "job"}}
                ]
            },
            limit=limit,
            with_vectors=False
        )[0]
        
        jobs = []
        for point in job_points:
            jobs.append({
                "id": point.id,
                "data": point.payload.get("data", {})
            })
        
        return jobs
    except Exception as e:
        st.error(f"Error fetching jobs: {str(e)}")
        return []

def search_by_text(query, search_type=None, limit=5):
    """Search using text query and OpenAI embeddings."""
    try:
        # Generate embedding for the query
        embedding_response = openai_client.embeddings.create(
            input=query,
            model="text-embedding-ada-002"
        )
        embedding = embedding_response.data[0].embedding
        
        # Prepare filter
        filter_option = {}
        if search_type:
            filter_option = {
                "must": [
                    {
                        "key": "type",
                        "match": {"value": search_type}
                    }
                ]
            }
        
        # Search Qdrant
        search_results = qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=embedding,
            limit=limit,
            query_filter=filter_option if filter_option else None
        )
        
        # Process results
        results = []
        for result in search_results:
            results.append({
                "id": result.id,
                "score": result.score,
                "type": result.payload.get("type"),
                "data": result.payload.get("data", {})
            })
        
        return results
    except Exception as e:
        st.error(f"Error during search: {str(e)}")
        return []

def match_candidate_with_jobs(candidate_id, limit=5):
    """Find jobs that match a specific candidate."""
    try:
        # Get the candidate point
        candidate_points = qdrant_client.retrieve(
            collection_name=COLLECTION_NAME,
            ids=[candidate_id],
            with_vectors=True
        )
        
        if not candidate_points:
            return []
        
        # Get the vector of the candidate
        candidate_vector = candidate_points[0].vector
        
        # Search for matching jobs
        matching_jobs = qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=candidate_vector,
            query_filter={
                "must": [
                    {"key": "type", "match": {"value": "job"}}
                ]
            },
            limit=limit
        )
        
        # Process results
        results = []
        for job in matching_jobs:
            results.append({
                "id": job.id,
                "score": job.score,
                "data": job.payload.get("data", {})
            })
        
        return results
    except Exception as e:
        st.error(f"Error matching candidate with jobs: {str(e)}")
        return []

def match_job_with_candidates(job_id, limit=5):
    """Find candidates that match a specific job."""
    try:
        # Get the job point
        job_points = qdrant_client.retrieve(
            collection_name=COLLECTION_NAME,
            ids=[job_id],
            with_vectors=True
        )
        
        if not job_points:
            return []
        
        # Get the vector of the job
        job_vector = job_points[0].vector
        
        # Search for matching candidates
        matching_candidates = qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=job_vector,
            query_filter={
                "must": [
                    {"key": "type", "match": {"value": "candidate"}}
                ]
            },
            limit=limit
        )
        
        # Process results
        results = []
        for candidate in matching_candidates:
            results.append({
                "id": candidate.id,
                "score": candidate.score,
                "data": candidate.payload.get("data", {})
            })
        
        return results
    except Exception as e:
        st.error(f"Error matching job with candidates: {str(e)}")
        return []

# Streamlit UI
st.set_page_config(
    page_title="HN Jobs & Candidates Matcher",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("HN Jobs & Candidates Matcher")
st.write("Search and match candidates with jobs from Hacker News.")

# Check Qdrant connection
collection_info = get_collection_info()
if collection_info:
    st.sidebar.success("Connected to Qdrant Cloud")
    st.sidebar.write(f"Collection: {COLLECTION_NAME}")
    st.sidebar.write(f"Points count: {collection_info['points_count']}")
    st.sidebar.write(f"Vector size: {collection_info['vector_size']}")
    st.sidebar.write(f"Distance: {collection_info['distance']}")
else:
    st.sidebar.error("Failed to connect to Qdrant")

# Sidebar navigation
page = st.sidebar.selectbox(
    "Choose a page", 
    ["Browse Data", "Semantic Search", "Match Candidates with Jobs", "Match Jobs with Candidates"]
)

# Browse Data page
if page == "Browse Data":
    st.header("Browse Data")
    
    tab1, tab2 = st.tabs(["Candidates", "Jobs"])
    
    with tab1:
        st.subheader("Candidates")
        candidates = get_candidates(limit=20)
        
        for i, candidate in enumerate(candidates, 1):
            # Get display name (email or location)
            email = candidate['data'].get('Email', '')
            location = candidate['data'].get('Location', 'Unknown location')
            technologies = candidate['data'].get('Technologies', '')
            
            # Create username display
            display_name = email if email and email != "Not provided" else f"Candidate from {location}"
            
            # Create technology preview
            tech_preview = f" - {technologies[:40]}..." if technologies else ""
            
            with st.expander(f"{display_name}{tech_preview}"):
                st.write(f"**Location**: {location}")
                st.write(f"**Technologies**: {candidate['data'].get('Technologies', 'Not specified')}")
                st.write(f"**Remote**: {candidate['data'].get('Remote', 'Not specified')}")
                st.write(f"**Willing to Relocate**: {candidate['data'].get('Willing to Relocate', 'Not specified')}")
                st.write(f"**Summary**: {candidate['data'].get('Summary', 'No summary available')}")
                
                if candidate['data'].get('Resume'):
                    st.write(f"**Resume**: {candidate['data'].get('Resume')}")
                
                # Display raw data as JSON (not in an expander)
                st.write("**Raw data:**")
                st.json(candidate)
    
    with tab2:
        st.subheader("Jobs")
        jobs = get_jobs(limit=20)
        
        for i, job in enumerate(jobs, 1):
            with st.expander(f"Job {i}: {job['data'].get('Company', 'Unknown company')} - {job['data'].get('Position', 'Unknown position')}"):
                st.write(f"**Technologies**: {job['data'].get('Technologies', 'Not specified')}")
                st.write(f"**Remote**: {job['data'].get('Remote', 'Not specified')}")
                st.write(f"**Salary**: {job['data'].get('Salary', 'Not specified')}")
                st.write(f"**Summary**: {job['data'].get('Summary', 'No summary available')}")
                
                # Display raw data as JSON (not in an expander)
                st.write("**Raw data:**")
                st.json(job)

# Semantic Search page
elif page == "Semantic Search":
    st.header("Semantic Search")
    
    search_query = st.text_input("Enter your search query")
    search_type = st.radio("Search type", ["Both", "Candidates", "Jobs"])
    
    if search_type == "Both":
        search_type_value = None
    elif search_type == "Candidates":
        search_type_value = "candidate"
    else:
        search_type_value = "job"
    
    if st.button("Search") and search_query:
        with st.spinner("Searching..."):
            results = search_by_text(search_query, search_type_value, limit=10)
            
            if results:
                st.success(f"Found {len(results)} results")
                
                for i, result in enumerate(results, 1):
                    result_type = result["type"]
                    data = result["data"]
                    score = result["score"] * 100  # Convert to percentage
                    
                    if result_type == "candidate":
                        with st.expander(f"{i}. Candidate ({score:.1f}%): {data.get('Location', 'Unknown location')}"):
                            st.write(f"**Technologies**: {data.get('Technologies', 'Not specified')}")
                            st.write(f"**Remote**: {data.get('Remote', 'Not specified')}")
                            st.write(f"**Summary**: {data.get('Summary', 'No summary available')}")
                            
                            # Display raw data as JSON (not in an expander)
                            st.write("**Raw data:**")
                            st.json(result)
                    else:
                        with st.expander(f"{i}. Job ({score:.1f}%): {data.get('Company', 'Unknown company')} - {data.get('Position', 'Unknown position')}"):
                            st.write(f"**Technologies**: {data.get('Technologies', 'Not specified')}")
                            st.write(f"**Remote**: {data.get('Remote', 'Not specified')}")
                            st.write(f"**Summary**: {data.get('Summary', 'No summary available')}")
                            
                            # Display raw data as JSON (not in an expander)
                            st.write("**Raw data:**")
                            st.json(result)
            else:
                st.warning("No results found")

# Match Candidates with Jobs page
elif page == "Match Candidates with Jobs":
    st.header("Match Candidates with Jobs")
    
    candidates = get_candidates(limit=20)
    
    candidate_options = {}
    for candidate in candidates:
        location = candidate['data'].get('Location', 'Unknown location')
        technologies = candidate['data'].get('Technologies', 'No technologies')
        display_text = f"{location} - {technologies[:30]}..." if technologies else location
        candidate_options[display_text] = candidate['id']
    
    selected_candidate_display = st.selectbox("Select a candidate", list(candidate_options.keys()))
    selected_candidate_id = candidate_options[selected_candidate_display]
    
    if st.button("Find Matching Jobs"):
        with st.spinner("Finding matches..."):
            # Display the selected candidate details
            for candidate in candidates:
                if candidate['id'] == selected_candidate_id:
                    st.subheader("Selected Candidate")
                    st.write(f"**Location**: {candidate['data'].get('Location', 'Not specified')}")
                    st.write(f"**Technologies**: {candidate['data'].get('Technologies', 'Not specified')}")
                    st.write(f"**Remote**: {candidate['data'].get('Remote', 'Not specified')}")
                    st.write(f"**Summary**: {candidate['data'].get('Summary', 'No summary available')}")
                    break
            
            # Find matching jobs
            matching_jobs = match_candidate_with_jobs(selected_candidate_id, limit=10)
            
            if matching_jobs:
                st.success(f"Found {len(matching_jobs)} matching jobs")
                
                for i, job in enumerate(matching_jobs, 1):
                    data = job["data"]
                    score = job["score"] * 100  # Convert to percentage
                    
                    with st.expander(f"{i}. ({score:.1f}%) {data.get('Company', 'Unknown company')} - {data.get('Position', 'Unknown position')}"):
                        st.write(f"**Technologies**: {data.get('Technologies', 'Not specified')}")
                        st.write(f"**Remote**: {data.get('Remote', 'Not specified')}")
                        st.write(f"**Salary**: {data.get('Salary', 'Not specified')}")
                        st.write(f"**Summary**: {data.get('Summary', 'No summary available')}")
            else:
                st.warning("No matching jobs found")

# Match Jobs with Candidates page
elif page == "Match Jobs with Candidates":
    st.header("Match Jobs with Candidates")
    
    jobs = get_jobs(limit=20)
    
    job_options = {}
    for job in jobs:
        company = job['data'].get('Company', 'Unknown company')
        position = job['data'].get('Position', 'Unknown position')
        display_text = f"{company} - {position[:30]}..." if position else company
        job_options[display_text] = job['id']
    
    selected_job_display = st.selectbox("Select a job", list(job_options.keys()))
    selected_job_id = job_options[selected_job_display]
    
    if st.button("Find Matching Candidates"):
        with st.spinner("Finding matches..."):
            # Display the selected job details
            for job in jobs:
                if job['id'] == selected_job_id:
                    st.subheader("Selected Job")
                    st.write(f"**Company**: {job['data'].get('Company', 'Not specified')}")
                    st.write(f"**Position**: {job['data'].get('Position', 'Not specified')}")
                    st.write(f"**Technologies**: {job['data'].get('Technologies', 'Not specified')}")
                    st.write(f"**Remote**: {job['data'].get('Remote', 'Not specified')}")
                    st.write(f"**Summary**: {job['data'].get('Summary', 'No summary available')}")
                    break
            
            # Find matching candidates
            matching_candidates = match_job_with_candidates(selected_job_id, limit=10)
            
            if matching_candidates:
                st.success(f"Found {len(matching_candidates)} matching candidates")
                
                for i, candidate in enumerate(matching_candidates, 1):
                    data = candidate["data"]
                    score = candidate["score"] * 100  # Convert to percentage
                    
                    # Get display name (email or location)
                    email = data.get('Email', '')
                    location = data.get('Location', 'Unknown location')
                    technologies = data.get('Technologies', '')
                    
                    # Create username display
                    display_name = email if email and email != "Not provided" else f"Candidate from {location}"
                    
                    # Create technology preview
                    tech_preview = f" - {technologies[:40]}..." if technologies else ""
                    
                    with st.expander(f"{i}. ({score:.1f}%) {display_name}{tech_preview}"):
                        st.write(f"**Location**: {location}")
                        st.write(f"**Technologies**: {data.get('Technologies', 'Not specified')}")
                        st.write(f"**Remote**: {data.get('Remote', 'Not specified')}")
                        st.write(f"**Willing to Relocate**: {data.get('Willing to Relocate', 'Not specified')}")
                        st.write(f"**Summary**: {data.get('Summary', 'No summary available')}")
            else:
                st.warning("No matching candidates found") 