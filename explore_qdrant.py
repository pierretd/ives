from qdrant_client import QdrantClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Connect to Qdrant
QDRANT_URL = os.environ.get('QDRANT_URL')
QDRANT_API_KEY = os.environ.get('QDRANT_API_KEY')
COLLECTION_NAME = 'hacker_news_jobs'

print(f"Connecting to Qdrant at {QDRANT_URL}")

# Connect to Qdrant
client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# Get collection info
print(f'\nCollection info for {COLLECTION_NAME}:')
try:
    collection_info = client.get_collection(collection_name=COLLECTION_NAME)
    print(f'Vector size: {collection_info.config.params.vectors.size}')
    print(f'Distance: {collection_info.config.params.vectors.distance}')
    print(f'Points count: {collection_info.vectors_count}')
except Exception as e:
    print(f'Error getting collection info: {str(e)}')

# Get sample points
print('\nFetching sample points:')
try:
    # Get candidate points
    print('\nCANDIDATE POINTS:')
    candidate_points = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter={
            'must': [
                {'key': 'type', 'match': {'value': 'candidate'}}
            ]
        },
        limit=5,
        with_vectors=False  # Don't include the vector data to keep output clean
    )[0]
    
    for i, point in enumerate(candidate_points, 1):
        data = point.payload.get('data', {})
        print(f'Candidate {i}:')
        print(f'  ID: {point.id}')
        print(f'  Technologies: {data.get("Technologies")}')
        print(f'  Location: {data.get("Location")}')
        print(f'  Remote: {data.get("Remote")}')
        print('')
    
    # Get job points
    print('\nJOB POINTS:')
    job_points = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter={
            'must': [
                {'key': 'type', 'match': {'value': 'job'}}
            ]
        },
        limit=5,
        with_vectors=False  # Don't include the vector data to keep output clean
    )[0]
    
    for i, point in enumerate(job_points, 1):
        data = point.payload.get('data', {})
        print(f'Job {i}:')
        print(f'  ID: {point.id}')
        print(f'  Company: {data.get("Company")}')
        print(f'  Position: {data.get("Position")}')
        print(f'  Technologies: {data.get("Technologies")}')
        print(f'  Remote: {data.get("Remote")}')
        print('')
    
    # Count total points by type
    print('\nCOUNTS BY TYPE:')
    candidate_count = len(client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter={'must': [{'key': 'type', 'match': {'value': 'candidate'}}]},
        limit=100
    )[0])
    
    job_count = len(client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter={'must': [{'key': 'type', 'match': {'value': 'job'}}]},
        limit=100
    )[0])
    
    print(f'Total candidates: {candidate_count}')
    print(f'Total jobs: {job_count}')
    print(f'Total points: {candidate_count + job_count}')
        
except Exception as e:
    print(f'Error fetching points: {str(e)}') 