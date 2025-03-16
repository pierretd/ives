import os
import requests
import html
import random
import uuid
import re
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, VectorParams, PointStruct
from fastembed import TextEmbedding
from time import time as current_time

# Load environment variables from .env file
load_dotenv()

# Global constants
HN_API_URL = "https://hacker-news.firebaseio.com/v0"
collection_name = "hacker_news_jobs"
MAX_POSTS = 25  # ✅ Increased to get more samples

# Thread IDs (moved to top)
WHO_IS_HIRING_THREAD_ID = 43243022
WHO_WANTS_TO_BE_HIRED_THREAD_ID = 43243024

# Common technology keywords to help filter non-tech terms
COMMON_TECH_KEYWORDS = {
    # Languages
    'python', 'javascript', 'typescript', 'java', 'c++', 'c#', 'ruby', 'php', 'swift', 'kotlin', 'go', 'rust',
    # Web
    'react', 'angular', 'vue', 'node', 'express', 'django', 'flask', 'rails', 'html', 'css', 'sass', 'less',
    # Databases
    'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch', 'dynamodb', 'cassandra',
    # Cloud & DevOps
    'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform', 'jenkins', 'gitlab', 'github',
    # AI/ML
    'tensorflow', 'pytorch', 'scikit-learn', 'pandas', 'numpy', 'opencv',
    # Mobile
    'ios', 'android', 'react native', 'flutter', 'swift', 'kotlin',
    # Other
    'git', 'linux', 'windows', 'macos', 'rest', 'graphql', 'websocket', 'oauth'
}

# 🚀 Step 1: Securely Load Qdrant Cloud Credentials
QDRANT_URL = os.getenv("QDRANT_URL")  # ✅ Load from .env
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")  # ✅ Load from .env

if not QDRANT_URL or not QDRANT_API_KEY:
    raise ValueError("❌ Qdrant credentials not found. Please set QDRANT_URL and QDRANT_API_KEY in your .env file")

# ✅ Connect to Qdrant Cloud
client = QdrantClient(QDRANT_URL, api_key=QDRANT_API_KEY)
print(f"✅ Successfully connected to Qdrant Cloud at {QDRANT_URL}")

def get_item(item_id):
    """Fetch a single Hacker News post or comment."""
    response = requests.get(f"{HN_API_URL}/item/{item_id}.json")
    return response.json() if response.status_code == 200 else None

def clean_text(text):
    """Cleans text: removes HTML tags & normalizes characters"""
    text = html.unescape(text)  # Decode HTML entities
    text = BeautifulSoup(text, "html.parser").get_text()  # Remove HTML tags
    return text.strip()

def clean_technology_name(tech):
    """Clean and validate technology names."""
    tech = tech.strip().lower()
    # Remove common prefixes/suffixes that aren't part of the tech name
    tech = re.sub(r'^(?:in|with|using|and|or|,|\+|\(|\))*\s*', '', tech)
    tech = re.sub(r'\s*(?:experience|framework|library|development|programming|latest|version)*$', '', tech)
    return tech

def clean_location(location):
    """Clean and normalize location strings"""
    if not location:
        return ""
    
    # Remove common prefixes
    location = re.sub(r'^Location:\s*', '', location, flags=re.IGNORECASE)
    
    # Remove parenthetical notes
    location = re.sub(r'\s*\([^)]*\)', '', location)
    
    # Clean up common location formats
    location = re.sub(r'Remote[- ]?first', '', location, flags=re.IGNORECASE)
    location = re.sub(r'Banglore', 'Bangalore', location)
    
    # Remove extra spaces and punctuation
    location = re.sub(r'[,/].*$', '', location)
    location = location.strip()
    
    return location

def extract_technologies(text):
    """Extract technology keywords from text"""
    # Common technology keywords
    tech_patterns = [
        r'\b(?:Python|JavaScript|TypeScript|Node\.js?|React|Vue\.js?|Angular|Next\.js?|Ruby|Rails|Django|Flask|Express|PHP|Laravel|Java|Kotlin|Swift|Go|Rust|C\+\+|C#|\.NET|SQL|MySQL|PostgreSQL|MongoDB|Redis|AWS|GCP|Azure|Docker|Kubernetes|Linux|Git|HTML|CSS|Tailwind|Bootstrap)\b',
        r'\b(?:REST|GraphQL|WebSocket|gRPC|CI/CD|DevOps|Machine Learning|AI|TensorFlow|PyTorch|Pandas|NumPy|Scikit-learn)\b'
    ]
    
    technologies = set()
    
    for pattern in tech_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            tech = match.group(0).lower()
            # Normalize some common variations
            tech = {
                'node.js': 'node',
                'vue.js': 'vue',
                'next.js': 'nextjs',
                'react.js': 'react',
                '.net': 'dotnet'
            }.get(tech, tech)
            technologies.add(tech)
    
    # Remove version numbers and common false positives
    technologies = {t for t in technologies if not re.match(r'^\d+(\.\d+)*(\+)?$', t)}
    
    return sorted(list(technologies))

def extract_field(text, field_name):
    """Extract a field value from text"""
    pattern = rf'(?:{field_name}|{field_name} ?:)[^\n]*'
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    
    field_text = match.group(0).lower()
    if any(word in field_text for word in ['yes', 'open', 'willing']):
        return "Yes"
    elif any(word in field_text for word in ['no', 'not', 'unwilling']):
        return "No"
    return None

def extract_links(text):
    """Extract various links from the text."""
    links = {
        "resume": None,
        "linkedin": None,
        "github": None,
        "portfolio": None
    }
    
    # Resume/CV
    resume_match = re.search(r"(?:Résumé|Resume|CV):\s*(https?://\S+)", text, re.IGNORECASE)
    if resume_match:
        links["resume"] = resume_match.group(1)
    
    # LinkedIn
    linkedin_match = re.search(r"LinkedIn:\s*(https?://\S+)", text, re.IGNORECASE)
    if linkedin_match:
        links["linkedin"] = linkedin_match.group(1)
    
    # GitHub
    github_match = re.search(r"Github:\s*(https?://\S+)", text, re.IGNORECASE)
    if github_match:
        links["github"] = github_match.group(1)
    
    # Portfolio (optional)
    portfolio_match = re.search(r"Portfolio:\s*(https?://\S+)", text, re.IGNORECASE)
    if portfolio_match:
        links["portfolio"] = portfolio_match.group(1)
    
    return links

def extract_contact_info(text):
    """Extract contact information."""
    email_match = re.search(r"Email:\s*([^\s<>\n]+@[^\s<>\n]+)", text, re.IGNORECASE)
    return {
        "email": email_match.group(1) if email_match else None
    }

def extract_preferences(text):
    """Extract work preferences."""
    return {
        "remote": extract_field(text, "Remote"),
        "willing_to_relocate": extract_field(text, "Willing to relocate"),
        "visa": extract_field(text, "Visa"),
        "employment_type": extract_field(text, "Employment Type") or extract_field(text, "Type")
    }

def extract_salary(text, post_type):
    """Extract salary information based on post type."""
    if post_type == "job":
        # For jobs, look for compensation, salary range, budget
        patterns = [
            r"(?:Salary|Compensation|Pay|Budget|Rate):\s*([^\n]+)",
            r"(?:paying|offer|range|budget):\s*([^\n]+)",
            r"(?:\$[\d,]+(?:\s*-\s*\$[\d,]+)?(?:\s*(?:USD|per year|annual|/year|k|/hr|/hour))?)"
        ]
    else:  # candidate
        # For candidates, look for expected salary, rate, compensation
        patterns = [
            r"(?:Expected Salary|Rate|Desired Compensation|Target):\s*([^\n]+)",
            r"(?:seeking|looking for|targeting)\s*(?:salary of)?\s*(\$[\d,]+(?:\s*-\s*\$[\d,]+)?(?:\s*(?:USD|per year|annual|/year|k|/hr|/hour))?)"
        ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            salary = match.group(1).strip()
            # Clean up common salary formats
            salary = re.sub(r'\s+', ' ', salary)
            return salary
    
    return "Not specified"

def extract_job_specific_data(text):
    """Extract fields specific to job posts."""
    return {
        "company": extract_field(text, "Company"),
        "position": extract_field(text, "Position") or extract_field(text, "Role"),
        "experience_required": extract_field(text, "Experience"),
        "visa_sponsorship": extract_field(text, "Visa") or bool(re.search(r'visa|sponsorship', text, re.IGNORECASE)),
        "interview_process": extract_field(text, "Interview Process"),
        "benefits": extract_field(text, "Benefits"),
    }

def extract_candidate_specific_data(text):
    """Extract fields specific to candidate posts."""
    return {
        "years_of_experience": extract_field(text, "Experience") or extract_years_of_experience(text),
        "education": extract_field(text, "Education"),
        "availability": extract_field(text, "Available") or extract_field(text, "Start Date"),
        "preferred_role": extract_field(text, "Role") or extract_field(text, "Position"),
        "visa_status": extract_field(text, "Visa Status") or extract_field(text, "Work Authorization"),
    }

def extract_years_of_experience(text):
    """Extract years of experience from candidate text"""
    if not text:
        return None
        
    # Patterns to extract years of experience
    experience_patterns = [
        r'(\d+)\+?\s*(?:years|yrs)(?:\s*of)?(?:\s*experience)?',  # "X years experience" or "X+ years of experience"
        r'(?:experience|exp)(?:\s*of)?\s*(\d+)\+?\s*(?:years|yrs)',  # "experience of X years" or "exp X+ years"
        r'(?:with)?\s*(\d+)\+?\s*(?:years|yrs)(?:\s*of)?(?:\s*experience)?',  # "with X years experience"
        r'senior.*?(\d+)\+?\s*(?:years|yrs)',  # "Senior X with Y years"
        r'(\d+)\+?\s*(?:years|yrs).*?senior',  # "X years ... senior"
    ]
    
    # Try to find explicit years of experience
    for pattern in experience_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            years = int(match.group(1))
            return years
    
    # If explicit years not found, try to identify seniority level
    if re.search(r'\b(?:senior|sr\.?|lead|principal|staff)\b', text, re.IGNORECASE):
        return "Senior (5+ years)"
    elif re.search(r'\b(?:mid[\-\s]level|intermediate|mid[\-\s]career)\b', text, re.IGNORECASE):
        return "Mid-level (3-5 years)"
    elif re.search(r'\b(?:junior|jr\.?|entry[\-\s]level|beginner|graduate|fresh)\b', text, re.IGNORECASE):
        return "Junior (0-2 years)"
    
    return "Not specified"

def extract_structured_data(text, post_type):
    """Extract all structured data from the post based on type."""
    # Common data for both types
    data = {
        "location": extract_location(text),
        "technologies": extract_technologies(text),
        "links": extract_links(text),
        "contact": extract_contact_info(text),
        "preferences": extract_preferences(text),
        "salary": extract_salary(text, post_type),
        "raw_text": text
    }
    
    # Add type-specific data
    if post_type == "job":
        data["job_specific"] = extract_job_specific_data(text)
    else:  # candidate
        data["candidate_specific"] = extract_candidate_specific_data(text)
    
    return data

def validate_post_data(post_data, thread_id, post_type):
    """Validate and clean post data"""
    # Clean the text
    text = post_data["text"]
    
    # Extract email using a more precise pattern
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_match = re.search(email_pattern, text)
    email = email_match.group(0) if email_match else None
    
    # Extract location
    location_pattern = r'(?:Location|Location ?:)[^\n]*'
    location_match = re.search(location_pattern, text, re.IGNORECASE)
    location = clean_location(location_match.group(0) if location_match else "")
    
    # Extract remote preference
    remote_pattern = r'(?:Remote|Remote ?:)[^\n]*'
    remote_match = re.search(remote_pattern, text, re.IGNORECASE)
    remote = "Yes" if remote_match and any(word in remote_match.group(0).lower() for word in ['yes', 'preferred', 'only']) else "No"
    
    # Extract willing to relocate
    willing_to_relocate = extract_field(text, "Willing to relocate") or "No"
    
    # Extract technologies
    technologies = extract_technologies(text)
    
    # Extract resume/CV link
    resume_pattern = r'(?:Resume|CV|Résumé)[^\n]*(?:https?://\S+)'
    resume_match = re.search(resume_pattern, text, re.IGNORECASE)
    resume = resume_match.group(0).split("https://", 1)[1].strip() if resume_match else None
    if resume:
        resume = "https://" + resume
    
    # Extract years of experience for candidates
    experience = None
    if post_type == "candidate":
        experience = extract_years_of_experience(text)
    
    # We no longer filter out posts without location or technologies
    # Instead, we'll accept all posts but with empty values if needed
    if not location:
        location = "Unknown"
    if not technologies:
        technologies = []
    
    # Clean up and return the validated data
    return {
        "id": post_data["id"],
        "author": post_data["author"],
        "text": text,
        "time": post_data["time"],
        "type": post_type,
        "thread_id": thread_id,
        "location": location,
        "remote": remote,
        "willing_to_relocate": willing_to_relocate,
        "technologies": technologies,
        "email": email,
        "resume": resume,
        "experience": experience if post_type == "candidate" else None
    }

def get_comments(thread_id, post_type):
    """Fetch comments from a Hacker News thread (Jobs or Candidates)"""
    thread = get_item(thread_id)
    if not thread or 'kids' not in thread:
        print(f"⚠️ No comments found for thread {thread_id}")
        return []

    comments_list = []
    skipped_count = 0
    
    for comment_id in thread['kids']:
        if len(comments_list) >= MAX_POSTS:
            break
        
        comment = get_item(comment_id)
        if comment and 'text' in comment:
            # Print raw text for analysis
            print(f"\n🔍 Raw {post_type} post:")
            print("-------------------")
            print(clean_text(comment["text"])[:500] + "..." if len(comment["text"]) > 500 else clean_text(comment["text"]))
            print("-------------------")
            
            post_data = validate_post_data({
                "id": str(uuid.uuid4()),
                "author": comment.get("by", "Unknown"),
                "text": clean_text(comment["text"]),
                "time": comment["time"],
                "type": post_type,
                "thread_id": str(comment.get("parent", thread_id))
            }, thread_id, post_type)
            
            if post_data:
                comments_list.append(post_data)
            else:
                skipped_count += 1
                print("⚠️ Skipped post: doesn't match required format")

    print(f"✅ Processed {len(comments_list) + skipped_count} posts, kept {len(comments_list)}, skipped {skipped_count}")
    return comments_list

# Update the thread ID references
hiring_posts = get_comments(WHO_IS_HIRING_THREAD_ID, "job")
candidate_posts = get_comments(WHO_WANTS_TO_BE_HIRED_THREAD_ID, "candidate")

print(f"✅ Found {len(hiring_posts)} job posts and {len(candidate_posts)} candidate posts")

# Take an equal number of posts from each category (up to MAX_POSTS/2)
max_per_category = MAX_POSTS // 2
hiring_posts = hiring_posts[:max_per_category]
candidate_posts = candidate_posts[:max_per_category]

# Combine the posts
all_posts = hiring_posts + candidate_posts

# If we have an odd MAX_POSTS, add one more from either category
if len(all_posts) < MAX_POSTS and (hiring_posts or candidate_posts):
    if len(hiring_posts) > max_per_category:
        all_posts.append(hiring_posts[max_per_category])
    elif len(candidate_posts) > max_per_category:
        all_posts.append(candidate_posts[max_per_category])

print(f"✅ Selected {len(all_posts)} posts total ({len(hiring_posts)} jobs, {len(candidate_posts)} candidates)")

# 🚀 Step 3: Store in Qdrant with FastEmbed
embed_model = TextEmbedding()

# ✅ Generate a sample embedding to detect size (Convert generator to list)
sample_embedding = list(embed_model.embed(["Test sentence"]))[0]
embedding_size = len(sample_embedding)  # ✅ Auto-detect correct size (384 or 768)

print(f"✅ Detected embedding size: {embedding_size}")

# ✅ Create collection if it doesn't exist
try:
    # Try to create the collection
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(
            size=embedding_size,
            distance=models.Distance.COSINE
        )
    )
    print(f"✅ Created/recreated collection: {collection_name}")
except Exception as e:
    print(f"Collection operation error (continuing anyway): {str(e)}")

def upload_to_qdrant(posts):
    """Upload posts to Qdrant"""
    global client
    collection_name = "hacker_news_jobs"
    
    # Check if collection exists, create if not
    try:
        client.get_collection(collection_name)
        print(f"Collection {collection_name} already exists")
    except Exception as e:
        print(f"Error checking collection: {str(e)}")
        try:
            print(f"Creating collection {collection_name}")
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=384,  # FastEmbed default size
                    distance=models.Distance.COSINE
                )
            )
        except Exception as create_error:
            # Check if the error is because collection already exists (409 Conflict)
            if "already exists" in str(create_error):
                print(f"Collection {collection_name} already exists (confirmed from error)")
            else:
                print(f"Error creating collection: {str(create_error)}")
                return False
    
    # Check points before upload
    print("\nChecking points before upload:")
    for post in posts:
        print(f"ID: {post['id']}, Type: {post['type']}, Location: {post['location']}, " + 
              f"Author: {post['author']}, Technologies: {post['technologies']}, " + 
              f"Remote: {post['remote']}, Willing to relocate: {post.get('willing_to_relocate', 'Not specified')}")
        if post['type'] == 'candidate' and post.get('experience'):
            print(f"  Experience: {post['experience']}")
    
    # Create embedding
    texts = [post["text"] for post in posts]
    
    # Get embeddings
    embeddings = list(embed_model.embed(texts))
    
    # Prepare points for upload - exclude sensitive information
    points = []
    for i, post in enumerate(posts):
        # Create a safe version of the post excluding sensitive information
        safe_post = {
            "id": post["id"],
            "author": post["author"],
            "text": post["text"],
            "time": post["time"],
            "type": post["type"],
            "thread_id": post["thread_id"],
            "location": post["location"],
            "remote": post["remote"],
            "willing_to_relocate": post.get("willing_to_relocate", "Not specified"),
            "technologies": post["technologies"],
            # Include experience for candidates
            "experience": post.get("experience") if post["type"] == "candidate" else None
            # Exclude email and resume from the payload
        }
        
        points.append(models.PointStruct(
            id=post["id"],
            vector=embeddings[i].tolist(),
            payload=safe_post
        ))
    
    # Upload points
    try:
        operation_info = client.upsert(
            collection_name=collection_name,
            wait=True,
            points=points
        )
        
        print(f"\nUploaded {len(points)} points to {collection_name}")
        return True
    except Exception as e:
        print(f"Error uploading points: {str(e)}")
        return False

# Extract documents & metadata
documents = [post["text"] for post in all_posts]
metadata = [{k: v for k, v in post.items() if k != "text"} for post in all_posts]
ids = [post["id"] for post in all_posts]  # ✅ Use UUIDs for valid IDs

# ✅ Convert generator to list before upserting embeddings
embeddings = list(embed_model.embed(documents))

# Update the point creation logic
points = []
for i, post in enumerate(all_posts):
    try:
        # Extract text and metadata
        text = post["text"]
        meta = {k: v for k, v in post.items() if k != "text"}
        
        # Create a cleaner payload structure with privacy considerations
        payload = {
            "id": post["id"],
            "type": post["type"],
            "location": post["location"],
            "author": post["author"],
            "technologies": post["technologies"],
            "remote": post["remote"],
            "willing_to_relocate": post.get("willing_to_relocate", "Not specified"),
            "experience": extract_years_of_experience(post.get("text", "")),
            # Include the full text for search but exclude it from display
            "text_embedding_only": True,  
            "text": text,  # Keep for embedding generation but not for display
        }
        
        # Add resume if available (but not personal contact info)
        if post.get("resume"):
            payload["resume"] = post["resume"]
            
        # Create point with embedding
        point = PointStruct(
            id=post["id"],
            vector=embeddings[i].tolist(),
            payload=payload
        )
        
        points.append(point)
        
    except Exception as e:
        print(f"Error creating point for post {post['id']}: {str(e)}")

# Debug output
print("\n🔍 Checking points before upload:")
for point in points:
    print("\n-------------------")
    print(f"ID: {point.id}")
    print(f"Type: {point.payload['type']}")
    print(f"Location: {point.payload['location']}")
    print(f"Author: {point.payload['author']}")
    print(f"Technologies: {', '.join(point.payload['technologies'])}")
    print(f"Remote: {point.payload['remote']}")
    if point.payload.get('resume'):
        print(f"Resume: {point.payload['resume']}")
    print("-------------------")

# Upload points to Qdrant
try:
    client.upsert(
        collection_name=collection_name,
        wait=True,
        points=points
    )
    print(f"✅ Successfully uploaded {len(points)} points to {collection_name}")
except Exception as e:
    print(f"❌ Error uploading points: {str(e)}")

def search_posts(query_text=None, post_type=None, technologies=None, location=None, remote=None, limit=5):
    """Search for posts based on various criteria"""
    # Build filter conditions
    filter_conditions = []
    
    # Post type filter (job or candidate)
    if post_type:
        filter_conditions.append(
            models.FieldCondition(
                key="type",
                match=models.MatchValue(value=post_type)
            )
        )
    
    # Technologies filter
    if technologies:
        # Handle technologies as a list for OR condition
        tech_list = [t.lower().strip() for t in technologies] if isinstance(technologies, list) else [technologies.lower().strip()]
        for tech in tech_list:
            filter_conditions.append(
                models.FieldCondition(
                    key="technologies",
                    match=models.MatchValue(value=tech)
                )
            )
    
    # Location filter - case insensitive text matching
    if location:
        location = location.strip().lower()
        filter_conditions.append(
            models.FieldCondition(
                key="location",
                match=models.MatchText(text=location)
            )
        )
    
    # Remote filter - exact value match
    if remote:
        filter_conditions.append(
            models.FieldCondition(
                key="remote",
                match=models.MatchValue(value="Yes")
            )
        )
    
    # Create search filter
    search_filter = models.Filter(
        must=filter_conditions
    ) if filter_conditions else None
    
    # Convert query text to embedding if provided
    query_vector = None
    if query_text:
        # Convert the generator to a list
        query_embedding = list(embed_model.embed([query_text]))[0]
        query_vector = query_embedding.tolist()
    
    # Perform search
    try:
        # For debugging
        print(f"\nSearch parameters:")
        print(f"- Post type: {post_type}")
        print(f"- Technologies: {technologies}")
        print(f"- Location: {location}")
        print(f"- Remote: {remote}")
        
        # If we have filter but no vector, use scroll
        if search_filter and not query_vector:
            search_result, _ = client.scroll(
                collection_name=collection_name,
                scroll_filter=search_filter,
                limit=limit
            )
        # If we have vector and filter
        elif query_vector and search_filter:
            search_result = client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=search_filter,
                limit=limit
            )
        # If we have only vector
        elif query_vector:
            search_result = client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit
            )
        # No search criteria
        else:
            print("Error: No search criteria provided")
            return []
        
        # When displaying search results, respect privacy settings
        print(f"\n🔍 Search Results ({len(search_result)} found):\n")
        for result in search_result:
            print("-------------------")
            print(f"Score: {getattr(result, 'score', 'N/A')}")
            print(f"Type: {result.payload['type']}")
            print(f"Location: {result.payload['location']}")
            print(f"Technologies: {', '.join(result.payload['technologies'])}")
            print(f"Remote: {result.payload['remote']}")
            if result.payload.get('willing_to_relocate'):
                print(f"Willing to relocate: {result.payload['willing_to_relocate']}")
            if result.payload.get('experience'):
                print(f"Experience: {result.payload['experience']}")
            if result.payload.get('resume') and not result.payload.get('text_embedding_only', False):
                print(f"Resume: {result.payload['resume']}")
            print("-------------------\n")
        
        return search_result
    except Exception as e:
        print(f"Error during search: {str(e)}")
        return []

# Verify collection contents
def check_collection():
    """Verify what's in the collection"""
    try:
        # Get collection info
        collection_info = client.get_collection(collection_name)
        print(f"\n✅ Collection info: {collection_name}, vectors: {collection_info.vectors_count}")
        
        # Get first few records to verify structure
        records, _ = client.scroll(
            collection_name=collection_name,
            limit=3
        )
        
        if records:
            print("\n✅ Sample records in collection:")
            for record in records:
                print("\n-------------------")
                print(f"ID: {record.id}")
                for key, value in record.payload.items():
                    if key == "text":
                        print(f"{key}: {value[:100]}...")  # Truncate text
                    elif isinstance(value, list):
                        print(f"{key}: {', '.join(str(v) for v in value)}")
                    else:
                        print(f"{key}: {value}")
                print("-------------------")
        else:
            print("❌ No records found in collection")
            
    except Exception as e:
        print(f"❌ Error checking collection: {str(e)}")

# Match candidates to a specific job
def match_candidates_for_job(job_id, limit=5):
    """Find the most suitable candidates for a specific job based on skills and preferences"""
    try:
        # First, get the job post details
        job_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="id",
                    match=models.MatchValue(value=job_id)
                ),
                models.FieldCondition(
                    key="type",
                    match=models.MatchValue(value="job")
                )
            ]
        )
        
        job_results, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=job_filter,
            limit=1
        )
        
        if not job_results:
            print(f"❌ Job with ID {job_id} not found")
            return []
        
        job = job_results[0]
        print(f"\n🔍 Finding candidates for job: {job.payload.get('author')}'s position in {job.payload.get('location')}")
        print(f"Required technologies: {', '.join(job.payload.get('technologies', []))}")
        print(f"Remote: {job.payload.get('remote')}")
        
        # Get all candidates
        candidates_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="type",
                    match=models.MatchValue(value="candidate")
                )
            ]
        )
        
        all_candidates, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=candidates_filter,
            limit=20  # Get more candidates to rank
        )
        
        # Score candidates based on matching technologies
        job_techs = set(job.payload.get('technologies', []))
        scored_candidates = []
        
        for candidate in all_candidates:
            candidate_techs = set(candidate.payload.get('technologies', []))
            matching_techs = job_techs.intersection(candidate_techs)
            
            # Calculate match score - more weight to matching technologies
            match_percentage = 0
            if job_techs:
                match_percentage = int((len(matching_techs) / len(job_techs)) * 100)
            
            # Additional scoring factors (can be expanded)
            # - Remote preference match: +10%
            # - Location match: +10%
            bonus = 0
            if job.payload.get('remote') == "Yes" and candidate.payload.get('remote') == "Yes":
                bonus += 10
                
            if job.payload.get('location') and candidate.payload.get('location'):
                if job.payload.get('location').lower() in candidate.payload.get('location').lower() or \
                   candidate.payload.get('location').lower() in job.payload.get('location').lower():
                    bonus += 10
            
            total_score = match_percentage + bonus
            
            # Store candidate with score for ranking
            scored_candidates.append({
                'candidate': candidate,
                'score': total_score,
                'matching_techs': matching_techs
            })
        
        # Sort candidates by score (highest first)
        scored_candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # Take top candidates up to the limit
        top_candidates = scored_candidates[:limit]
        
        # Update display of potential candidates
        print(f"\n🔍 Found {len(top_candidates)} potential candidates:\n")
        for i, item in enumerate(top_candidates):
            candidate = item['candidate']
            score = item['score']
            matching_techs = item['matching_techs']
            
            print(f"Candidate #{i+1} - Match score: {score}%")
            print("-------------------")
            print(f"Author: {candidate.payload.get('author')}")
            if candidate.payload.get('location'):
                print(f"Location: {candidate.payload.get('location')}")
            print(f"Technologies: {', '.join(candidate.payload.get('technologies', []))}")
            print(f"Matching skills: {', '.join(matching_techs)}")
            if candidate.payload.get('remote'):
                print(f"Remote: {candidate.payload.get('remote')}")
            if candidate.payload.get('willing_to_relocate'):
                print(f"Willing to relocate: {candidate.payload.get('willing_to_relocate')}")
            if candidate.payload.get('experience'):
                print(f"Experience: {candidate.payload.get('experience')}")
            if candidate.payload.get('resume') and not candidate.payload.get('text_embedding_only', False):
                print(f"Resume: {candidate.payload.get('resume')}")
            print("-------------------\n")
        
        return [item['candidate'] for item in top_candidates]
    except Exception as e:
        print(f"Error matching candidates: {str(e)}")
        return []

def match_candidates_to_jobs(job_post_id=None):
    """Match candidates to job posts based on skills and preferences"""
    global client
    collection_name = "hacker_news_jobs"
    
    try:
        # First, retrieve the job post
        job_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="type",
                    match=models.MatchValue(value="job")
                )
            ]
        )
        
        # If a specific job post ID is provided, add it to the filter
        if job_post_id:
            job_filter.must.append(
                models.FieldCondition(
                    key="id",
                    match=models.MatchValue(value=job_post_id)
                )
            )
        
        job_posts = client.scroll(
            collection_name=collection_name,
            scroll_filter=job_filter,
            limit=10
        )[0]
        
        if not job_posts:
            print("No job posts found")
            return []
        
        # For each job post, find matching candidates
        results = []
        for job_post in job_posts:
            job_data = job_post.payload
            job_technologies = job_data.get("technologies", [])
            job_location = job_data.get("location", "")
            job_remote = job_data.get("remote", "No")
            
            print(f"\nMatching candidates for job: {job_data['author']} - {job_location}")
            print(f"Required technologies: {job_technologies}")
            print(f"Remote: {job_remote}")
            
            # Construct candidate filter
            candidate_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="type",
                        match=models.MatchValue(value="candidate")
                    )
                ]
            )
            
            # If job requires specific location and is not remote, add location constraint
            # For remote jobs, we can match candidates regardless of location
            location_conditions = []
            if job_remote == "No" and job_location:
                location_conditions.append(
                    models.FieldCondition(
                        key="location",
                        match=models.MatchValue(value=job_location)
                    )
                )
                location_conditions.append(
                    models.FieldCondition(
                        key="willing_to_relocate",
                        match=models.MatchValue(value="Yes")
                    )
                )
                
                # Add location conditions with OR relationship
                if location_conditions:
                    # Create a new filter with should conditions
                    candidate_filter = models.Filter(
                        must=[
                            models.FieldCondition(
                                key="type",
                                match=models.MatchValue(value="candidate")
                            )
                        ],
                        should=location_conditions
                    )
                    
                    # Try to set min_should_match safely
                    try:
                        candidate_filter.min_should_match = 1
                    except AttributeError:
                        print("Warning: min_should_match not supported in this Qdrant version")
                        # Fall back to regular must condition if should isn't supported
            
            # Get candidate matches
            embedding = list(embed_model.embed([job_data["text"]]))[0].tolist()
            
            candidates = client.search(
                collection_name=collection_name,
                query_vector=embedding,
                query_filter=candidate_filter,
                limit=5
            )
            
            # Calculate match scores
            job_matches = []
            for candidate in candidates:
                candidate_data = candidate.payload
                candidate_technologies = candidate_data.get("technologies", [])
                
                # Calculate technology match score
                tech_match_score = 0
                for tech in job_technologies:
                    if tech in candidate_technologies:
                        tech_match_score += 1
                
                tech_match_percentage = 0
                if job_technologies:
                    tech_match_percentage = (tech_match_score / len(job_technologies)) * 100
                
                # Calculate overall match score
                overall_score = 0.6 * tech_match_percentage + 0.4 * (candidate.score * 100)
                
                job_matches.append({
                    "job": job_data,
                    "candidate": candidate_data,
                    "similarity_score": candidate.score,
                    "tech_match_percentage": tech_match_percentage,
                    "overall_match_score": overall_score
                })
            
            # Sort by overall match score
            job_matches.sort(key=lambda x: x["overall_match_score"], reverse=True)
            
            # Add to results
            for match in job_matches:
                print(f"\nCandidate: {match['candidate']['author']}")
                print(f"Location: {match['candidate']['location']}")
                print(f"Technologies: {match['candidate']['technologies']}")
                print(f"Willing to relocate: {match['candidate'].get('willing_to_relocate', 'Not specified')}")
                print(f"Tech match: {match['tech_match_percentage']:.1f}%")
                print(f"Similarity score: {match['similarity_score']:.4f}")
                print(f"Overall match: {match['overall_match_score']:.1f}%")
            
            results.extend(job_matches)
        
        return results
        
    except Exception as e:
        print(f"Error matching candidates: {str(e)}")
        return []

def get_raw_posts(thread_id):
    """Fetch raw posts from a Hacker News thread"""
    thread = get_item(thread_id)
    if not thread or 'kids' not in thread:
        print(f"⚠️ No comments found for thread {thread_id}")
        return []

    raw_posts = []
    for comment_id in thread['kids']:
        if len(raw_posts) >= MAX_POSTS:
            break
        
        comment = get_item(comment_id)
        if comment and 'text' in comment:
            raw_posts.append(comment)
    
    return raw_posts

def get_posts_from_raw(raw_posts, thread_id, post_type):
    """Process raw posts and convert to structured data"""
    processed_posts = []
    skipped_count = 0
    
    for post in raw_posts:
        if 'text' in post:
            # Print raw text for analysis
            print(f"\n🔍 Raw {post_type} post:")
            print("-------------------")
            print(clean_text(post["text"])[:500] + "..." if len(post["text"]) > 500 else clean_text(post["text"]))
            print("-------------------")
            
            post_data = validate_post_data({
                "id": str(uuid.uuid4()),
                "author": post.get("by", "Unknown"),
                "text": clean_text(post["text"]),
                "time": post["time"],
                "type": post_type,
                "thread_id": str(post.get("parent", thread_id))
            }, thread_id, post_type)
            
            if post_data:
                processed_posts.append(post_data)
            else:
                skipped_count += 1
                print("⚠️ Skipped post: doesn't match required format")
    
    print(f"✅ Processed {len(processed_posts) + skipped_count} posts, kept {len(processed_posts)}, skipped {skipped_count}")
    return processed_posts

def init_embedding_model():
    """Initialize the embedding model"""
    global embed_model
    embed_model = TextEmbedding()
    print("✅ Embedding model initialized")
    return embed_model

def init_qdrant_client():
    """Initialize the Qdrant client"""
    global client
    # Already initialized at the top of the file
    print("✅ Qdrant client already initialized")
    return client

# Example usage of the new job-candidate matching feature
if __name__ == "__main__":
    # Check collection first
    try:
        collection_info = client.get_collection(collection_name)
        print(f"\n✅ Collection info: {collection_name}, vectors: {collection_info.vectors_count}")
    except Exception as e:
        print(f"❌ Error checking collection: {str(e)}")
    
    print("\n🔍 Testing search functionality...")
    
    # Search 1: Find jobs with Python
    print("\nSearch 1: Jobs with Python")
    try:
        python_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="type", 
                    match=models.MatchValue(value="job")
                ),
                models.FieldCondition(
                    key="technologies",
                    match=models.MatchValue(value="python")
                )
            ]
        )
        
        jobs_with_python, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=python_filter,
            limit=5
        )
        
        print(f"\n🔍 Found {len(jobs_with_python)} jobs with Python:\n")
        for job in jobs_with_python:
            print("-------------------")
            print(f"Author: {job.payload.get('author')}")
            print(f"Location: {job.payload.get('location')}")
            print(f"Technologies: {', '.join(job.payload.get('technologies', []))}")
            print(f"Remote: {job.payload.get('remote')}")
            print("-------------------\n")
    except Exception as e:
        print(f"Error in Python job search: {str(e)}")
    
    # Search 2: Find React developers
    print("\nSearch 2: React developers")
    try:
        react_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="type", 
                    match=models.MatchValue(value="candidate")
                ),
                models.FieldCondition(
                    key="technologies",
                    match=models.MatchValue(value="react")
                )
            ]
        )
        
        react_developers, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=react_filter,
            limit=5
        )
        
        print(f"\n🔍 Found {len(react_developers)} candidate posts with React:\n")
        for dev in react_developers:
            print("-------------------")
            print(f"Type: {dev.payload.get('type')}")
            print(f"Author: {dev.payload.get('author')}")
            print(f"Location: {dev.payload.get('location')}")
            print(f"Technologies: {', '.join(dev.payload.get('technologies', []))}")
            print("-------------------\n")
    except Exception as e:
        print(f"Error in React developer search: {str(e)}")
    
    # Search 2a: Find React jobs
    print("\nSearch 2a: React jobs")
    try:
        react_jobs_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="type", 
                    match=models.MatchValue(value="job")
                ),
                models.FieldCondition(
                    key="technologies",
                    match=models.MatchValue(value="react")
                )
            ]
        )
        
        react_jobs, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=react_jobs_filter,
            limit=5
        )
        
        print(f"\n🔍 Found {len(react_jobs)} job posts with React:\n")
        for job in react_jobs:
            print("-------------------")
            print(f"Author: {job.payload.get('author')}")
            print(f"Location: {job.payload.get('location')}")
            print(f"Technologies: {', '.join(job.payload.get('technologies', []))}")
            print(f"Remote: {job.payload.get('remote')}")
            print("-------------------\n")
    except Exception as e:
        print(f"Error in React jobs search: {str(e)}")
    
    # Check what locations we have
    try:
        print("\n🔍 Listing all unique location values in the collection:")
        location_filter = models.Filter()
        all_points, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=location_filter,
            limit=100
        )
        
        # Extract unique locations
        locations = set()
        for point in all_points:
            location = point.payload.get('location', '').strip()
            if location:
                locations.add(location)
        
        # Print sorted locations
        for location in sorted(locations):
            print(f"- {location}")
        
    except Exception as e:
        print(f"Error listing locations: {str(e)}")
        
    # Search 3: Jobs in USA
    print("\nSearch 3: Jobs in USA")
    try:
        # Use exact location values we saw in the data
        usa_locations = ["USA", "California"]
        all_usa_jobs = []
        
        # Search for each USA location exactly as stored
        for location in usa_locations:
            usa_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="type", 
                        match=models.MatchValue(value="job")
                    ),
                    models.FieldCondition(
                        key="location",
                        match=models.MatchValue(value=location)
                    )
                ]
            )
            
            try:
                usa_jobs, _ = client.scroll(
                    collection_name=collection_name,
                    scroll_filter=usa_filter,
                    limit=5
                )
                all_usa_jobs.extend(usa_jobs)
                print(f"  - Found {len(usa_jobs)} jobs for location '{location}'")
            except Exception as e:
                print(f"  Error searching for '{location}': {str(e)}")
        
        # Remove duplicates by ID
        seen_ids = set()
        unique_usa_jobs = []
        for job in all_usa_jobs:
            if job.id not in seen_ids:
                seen_ids.add(job.id)
                unique_usa_jobs.append(job)
        
        print(f"\n🔍 Found {len(unique_usa_jobs)} jobs in USA:\n")
        for job in unique_usa_jobs:
            print("-------------------")
            print(f"Author: {job.payload.get('author')}")
            print(f"Location: {job.payload.get('location')}")
            print(f"Technologies: {', '.join(job.payload.get('technologies', []))}")
            print(f"Remote: {job.payload.get('remote')}")
            print("-------------------\n")
    except Exception as e:
        print(f"Error in USA job search: {str(e)}")

    # After the previous searches, add:
    print("\n🔍 Testing job-candidate matching functionality...")
    
    # Find a job with technology requirements
    try:
        # Get a sample job post to match candidates against
        sample_job_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="type",
                    match=models.MatchValue(value="job")
                ),
                models.FieldCondition(
                    key="technologies",
                    match=models.MatchValue(value="react")
                )
            ]
        )
        
        sample_jobs, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=sample_job_filter,
            limit=1
        )
        
        if sample_jobs:
            print("\nSearch 4: Best matching candidates for a React job")
            match_candidates_for_job(sample_jobs[0].id)
        else:
            print("❌ No suitable job found for matching candidates")
            
    except Exception as e:
        print(f"Error in job-candidate matching test: {str(e)}")

    # Get raw posts from HN
    raw_jobs_posts = []
    raw_candidate_posts = []
    
    try:
        raw_jobs_posts = get_raw_posts(WHO_IS_HIRING_THREAD_ID)
        print(f"Found {len(raw_jobs_posts)} job posts")
    except Exception as e:
        print(f"Error fetching job posts: {str(e)}")
        
    try:
        raw_candidate_posts = get_raw_posts(WHO_WANTS_TO_BE_HIRED_THREAD_ID)
        print(f"Found {len(raw_candidate_posts)} candidate posts")
    except Exception as e:
        print(f"Error fetching candidate posts: {str(e)}")
    
    # Get posts for both jobs and candidates
    job_posts = get_posts_from_raw(raw_jobs_posts, WHO_IS_HIRING_THREAD_ID, "job")
    candidate_posts = get_posts_from_raw(raw_candidate_posts, WHO_WANTS_TO_BE_HIRED_THREAD_ID, "candidate")
    
    # Take a subset of posts for testing
    max_posts_per_type = 12
    job_posts = job_posts[:max_posts_per_type]
    candidate_posts = candidate_posts[:max_posts_per_type]
    
    all_posts = job_posts + candidate_posts
    print(f"Selected {len(all_posts)} posts for processing")
    
    # Initialize the embedding model
    init_embedding_model()
    
    # Initialize Qdrant client
    init_qdrant_client()
    
    # Upload posts to Qdrant
    upload_to_qdrant(all_posts)
    
    # Test search functionality
    print("\nSearching for jobs with Python:")
    python_jobs = search_posts(post_type="job", technologies=["Python"])
    for post in python_jobs:
        print(f"Author: {post.payload['author']}, Location: {post.payload['location']}, Technologies: {post.payload['technologies']}")
    
    print("\nSearching for React developers:")
    react_posts = search_posts(technologies=["React"])
    for post in react_posts:
        print(f"Type: {post.payload['type']}, Author: {post.payload['author']}, Location: {post.payload['location']}, Technologies: {post.payload['technologies']}")
    
    print("\nSearching for jobs in USA:")
    usa_jobs = search_posts(post_type="job", location="USA")
    for post in usa_jobs:
        print(f"Author: {post.payload['author']}, Location: {post.payload['location']}, Technologies: {post.payload['technologies']}, Remote: {post.payload['remote']}")
    
    # Test candidate matching
    print("\nTesting candidate matching:")
    matches = match_candidates_to_jobs()
    print(f"\nFound {len(matches)} potential matches between jobs and candidates.")
