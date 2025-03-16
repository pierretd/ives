import requests
import re
import html
import json
from bs4 import BeautifulSoup
from datetime import datetime
from difflib import SequenceMatcher

# Hacker News API URLs
CANDIDATES_THREAD_ID = "43243022"  # Who wants to be hired thread ID
JOBS_THREAD_ID = "43243024"  # Who is hiring thread ID
HN_BASE_URL = "https://news.ycombinator.com/item?id="

# ===== Common functions =====

def fetch_hn_comments(item_id, limit=None):
    """Fetches Hacker News thread data and returns the comments."""
    url = f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Error fetching thread data: {response.status_code}")
        return []
    
    thread_data = response.json()
    if 'kids' not in thread_data:
        print("No comments found in thread.")
        return []
    
    # Fetch all comments without a limit
    comments = []
    for comment_id in thread_data['kids']:
        comment_data = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{comment_id}.json").json()
        if 'text' in comment_data:
            comment_data['text'] = html.unescape(comment_data['text'])  # Decode HTML entities
            comments.append(comment_data)
    
    return comments

def clean_html(html_text):
    """Clean HTML tags and convert breaks to newlines."""
    # Replace <p> and <br> tags with newlines before using BeautifulSoup
    html_text = re.sub(r'<p>', '\n', html_text)
    html_text = re.sub(r'<br\s*/?>', '\n', html_text)
    
    # Use BeautifulSoup to handle HTML properly
    soup = BeautifulSoup(html_text, 'html.parser')
    
    # Get the text
    text = soup.get_text()
    
    # Normalize spacing and remove extra newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    
    return text.strip()

# ===== Candidate extraction functions =====

def extract_candidate_fields(comment):
    """Extracts structured fields from a HN candidate comment."""
    today = datetime.now().strftime("%B %d, %Y")
    
    # Initialize fields with default values
    fields = {
        "Date": today,
        "Email": None,
        "Resume": None,
        "Location": None,
        "Remote": None,
        "Willing to Relocate": None,
        "Technologies": None,
        "Link to HN": f"{HN_BASE_URL}{CANDIDATES_THREAD_ID}#{comment['id']}",
        "Raw Text": None
    }
    
    # Clean the comment text
    text = clean_html(comment['text'])
    fields["Raw Text"] = text
    
    # Extract fields using regex patterns
    patterns = {
        "Email": r"(?i)(?:^|\n|\s)Email:\s*([\w\.-]+@[\w\.-]+)",
        "Resume": r"(?i)(?:^|\n|\s)(?:Résumé|Resume|CV)(?:/CV)?:\s*(https?://[^\s\n]+)",
        "Location": r"(?i)(?:^|\n|\s)Location:\s*([^\n]+)",
        "Remote": r"(?i)(?:^|\n|\s)Remote:\s*([^\n]+)",
        "Willing to Relocate": r"(?i)(?:^|\n|\s)Willing to relocate:\s*([^\n]+)",
        "Technologies": r"(?i)(?:^|\n|\s)Technologies:\s*([^\n]+)",
    }
    
    # Apply each pattern
    for field, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            fields[field] = match.group(1).strip()
    
    # Additional patterns for handling variations
    if not fields["Resume"]:
        resume_patterns = [
            r"(?i)(?:résumé|resume|cv)(?:/cv)?:?\s*(https?://[^\s\n]+)",
            r"(?i)\b(https?://[^\s\n]*(?:resume|cv)[^\s\n]*)"
        ]
        for pattern in resume_patterns:
            match = re.search(pattern, text)
            if match:
                fields["Resume"] = match.group(1).strip()
                break
    
    if not fields["Email"]:
        email_patterns = [
            r"(?i)(?:contact|e-mail):\s*([\w\.-]+@[\w\.-]+)",
            r"(?i)([\w\.-]+@[\w\.-]+)"
        ]
        for pattern in email_patterns:
            match = re.search(pattern, text)
            if match:
                fields["Email"] = match.group(1).strip()
                break
    
    # Extract technologies if not found with the main pattern
    if not fields["Technologies"]:
        tech_patterns = [
            r"(?i)skills?(?:[:\s])([^\.]+)",
            r"(?i)tech stack(?:[:\s])([^\.]+)",
            r"(?i)proficient in(?:[:\s])([^\.]+)"
        ]
        for pattern in tech_patterns:
            match = re.search(pattern, text)
            if match:
                fields["Technologies"] = match.group(1).strip()
                break
    
    return fields

def generate_candidate_summary(fields):
    """Generate a summary based on the candidate's information."""
    # Basic summary generation
    summary_parts = []
    
    # Check location, remote/relocation status
    if fields["Location"]:
        location_info = f"{fields['Location']}-based"
        summary_parts.append(location_info)
    
    # Check technologies
    if fields["Technologies"]:
        tech_list = fields["Technologies"].split(",")
        if len(tech_list) > 3:
            tech_summary = f"developer with skills in {', '.join(tech_list[:3])}, and more"
        else:
            tech_summary = f"developer with skills in {fields['Technologies']}"
        summary_parts.append(tech_summary)
    else:
        summary_parts.append("developer")
    
    # Add remote/relocation preferences
    preferences = []
    if fields["Remote"] and "yes" in fields["Remote"].lower():
        preferences.append("available for remote work")
    if fields["Willing to Relocate"] and "yes" in fields["Willing to Relocate"].lower():
        preferences.append("willing to relocate")
    
    if preferences:
        summary_parts.append(f"who is {' and '.join(preferences)}")
    
    # Combine all parts
    summary = " ".join(summary_parts)
    return summary.capitalize()

# ===== Job extraction functions =====

def extract_job_fields(comment):
    """Extracts structured fields from a job posting comment."""
    today = datetime.now().strftime("%B %d, %Y")
    
    # Initialize fields with default values
    fields = {
        "Date": today,
        "Company": None,
        "Position": None,
        "Location": None,
        "Remote": None,
        "Salary": None,
        "Technologies": None,
        "Description": None,
        "Apply": None,
        "Link to HN": f"{HN_BASE_URL}{JOBS_THREAD_ID}#{comment['id']}",
        "Raw Text": None
    }
    
    # Clean the comment text
    text = clean_html(comment['text'])
    fields["Raw Text"] = text
    
    # Extract company name - usually at the beginning of the post
    company_patterns = [
        r"^([A-Za-z0-9\s\.\-&]+)\s*\|\s",  # "Company Name | ..."
        r"^([A-Za-z0-9\s\.\-&]+)\s*\(\s*http",  # "Company Name (http..."
        r"^([A-Za-z0-9\s\.\-&]{2,30}?)(?:\s+is|\s+hiring|\s*\|)"  # "Company Name is/hiring/|"
    ]
    
    for pattern in company_patterns:
        match = re.search(pattern, text)
        if match:
            fields["Company"] = match.group(1).strip()
            break
    
    # Extract position/role
    position_patterns = [
        r"(?:hiring|for|hiring for|seeking|looking for)[:\s]+([^|\.]+?(?:Engineer|Developer|Manager|Designer|Architect|Scientist|Lead|Director|VP|CTO|DevOps)[^|\.]+?)(?:\||\.|\n|$)",
        r"(?:\|\s*)([^|\.]+?(?:Engineer|Developer|Manager|Designer|Architect|Scientist|Lead|Director|VP|CTO|DevOps)[^|\.]+?)(?:\||\.|\n|$)"
    ]
    
    for pattern in position_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            fields["Position"] = match.group(1).strip()
            break
    
    # Extract standard fields using regex patterns
    patterns = {
        "Location": r"(?i)(?:^|\n|\s)Location:\s*([^\n]+)",
        "Remote": r"(?i)(?:^|\n|\s)Remote:\s*([^\n]+)|(?i)\b(remote(?:\s+(?:friendly|ok|possible|only))?)\b",
        "Salary": r"(?i)(?:^|\n|\s)(?:Salary|Compensation):\s*([^\n]+)|(?i)(?:pay|salary|compensation|package)[:\s]+([^\.]+)",
        "Technologies": r"(?i)(?:^|\n|\s)(?:Tech|Stack|Technologies):\s*([^\n]+)",
        "Apply": r"(?i)(?:^|\n|\s)(?:Apply|Application|Contact):\s*([^\n]+)"
    }
    
    # Apply each pattern
    for field, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Some patterns have multiple capture groups, use the one that matched
            captured_group = next((group for group in match.groups() if group), None)
            if captured_group:
                fields[field] = captured_group.strip()
    
    # Extract technologies if not found with the main pattern
    if not fields["Technologies"]:
        tech_sections = re.findall(r"(?i)(?:tech stack|using|experience with|skills|looking for)[:\s]+((?:[^\.]+(?:JavaScript|Python|React|Angular|Vue|Node|Django|Flask|Ruby|Rails|PHP|Laravel|AWS|GCP|Azure|SQL|NoSQL|MongoDB|MySQL|PostgreSQL|Docker|Kubernetes|CI/CD|Git)[^\.]+))", text)
        if tech_sections:
            fields["Technologies"] = tech_sections[0].strip()
    
    # Extract a brief description
    if text:
        # Get first few sentences for description if not too long
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if sentences:
            desc_length = min(3, len(sentences))  # First 3 sentences or fewer
            fields["Description"] = ' '.join(sentences[:desc_length])
    
    return fields

def generate_job_summary(fields):
    """Generate a summary based on the job posting information."""
    summary_parts = []
    
    # Add company
    if fields["Company"]:
        summary_parts.append(f"{fields['Company']} is hiring")
    else:
        summary_parts.append("Company is hiring")
    
    # Add position
    if fields["Position"]:
        summary_parts.append(f"for {fields['Position']}")
    
    # Add location/remote
    location_parts = []
    if fields["Location"]:
        location_parts.append(f"in {fields['Location']}")
    if fields["Remote"] and "no" not in fields["Remote"].lower():
        location_parts.append("with remote options")
    
    if location_parts:
        summary_parts.append(' '.join(location_parts))
    
    # Add key technologies if available
    if fields["Technologies"]:
        tech_items = re.split(r'[,;/]', fields["Technologies"])
        if len(tech_items) > 3:
            tech_summary = f"using {', '.join(tech_items[:3])}, and more"
        else:
            tech_summary = f"using {fields['Technologies']}"
        summary_parts.append(tech_summary)
    
    # Add salary if available
    if fields["Salary"]:
        summary_parts.append(f"with compensation {fields['Salary']}")
    
    # Combine all parts
    summary = ' '.join(summary_parts)
    return summary

# ===== Matching functions =====

def normalize_text(text):
    """Normalize text for better comparison."""
    if not text:
        return ""
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove punctuation and extra spaces
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def extract_technologies(text):
    """Extract technology keywords from text."""
    if not text:
        return set()
    
    # Common technology keywords to look for
    tech_keywords = {
        'javascript', 'typescript', 'python', 'java', 'c#', 'c++', 'ruby', 'php', 'swift', 'kotlin',
        'react', 'angular', 'vue', 'node', 'django', 'flask', 'rails', 'spring', 'laravel', 
        'aws', 'azure', 'gcp', 'mongodb', 'mysql', 'postgresql', 'sql', 'nosql', 'docker', 'kubernetes',
        'git', 'devops', 'mobile', 'android', 'ios', 'frontend', 'backend', 'fullstack', 'ui', 'ux',
        'machine learning', 'ml', 'ai', 'data science', 'blockchain', 'eth', 'rust', 'go', 'golang'
    }
    
    # Normalize the text
    norm_text = normalize_text(text)
    
    # Find matching tech keywords
    found_tech = set()
    for keyword in tech_keywords:
        if f' {keyword} ' in f' {norm_text} ':
            found_tech.add(keyword)
    
    return found_tech

def calculate_match_score(candidate, job):
    """Calculate a match score between a candidate and job."""
    score = 0
    score_details = {}
    
    # Check remote preferences
    if job["Remote"] and candidate["Remote"]:
        if "yes" in candidate["Remote"].lower():
            if "yes" in job["Remote"].lower() or "remote" in job["Remote"].lower():
                score += 25
                score_details["remote"] = "Remote preferences match (+25)"
    
    # Check location preferences
    if job["Location"] and candidate["Location"]:
        job_location = normalize_text(job["Location"])
        candidate_location = normalize_text(candidate["Location"])
        
        # If locations match exactly or candidate is willing to relocate
        if job_location in candidate_location or candidate_location in job_location:
            score += 20
            score_details["location"] = "Location matches (+20)"
        elif candidate["Willing to Relocate"] and "yes" in candidate["Willing to Relocate"].lower():
            score += 10
            score_details["location"] = "Candidate willing to relocate (+10)"
    
    # Extract technologies from both
    candidate_tech = extract_technologies(candidate["Technologies"])
    job_tech = extract_technologies(job["Technologies"])
    
    # If both have technology info, compare them
    if candidate_tech and job_tech:
        # Calculate the overlap
        matching_tech = candidate_tech.intersection(job_tech)
        tech_match_percentage = len(matching_tech) / len(job_tech) if job_tech else 0
        
        # Weighted score for technology match (up to 55 points)
        tech_score = int(tech_match_percentage * 55)
        score += tech_score
        
        score_details["technologies"] = f"Technology match: {len(matching_tech)}/{len(job_tech)} ({tech_score} points)"
        score_details["matching_tech"] = list(matching_tech)
    
    # Calculate total score percentage
    score_percentage = min(100, score)
    
    return {
        "score": score_percentage,
        "details": score_details
    }

def find_matches(candidates, jobs, min_score=50):
    """Find matches between candidates and jobs with scores."""
    matches = []
    
    for candidate in candidates:
        candidate_matches = []
        
        for job in jobs:
            match_result = calculate_match_score(candidate, job)
            if match_result["score"] >= min_score:
                candidate_matches.append({
                    "job": job,
                    "match_score": match_result["score"],
                    "match_details": match_result["details"]
                })
        
        # Sort matches by score (descending)
        candidate_matches.sort(key=lambda x: x["match_score"], reverse=True)
        
        if candidate_matches:
            matches.append({
                "candidate": candidate,
                "matches": candidate_matches
            })
    
    # Sort by highest match score
    matches.sort(key=lambda x: max([m["match_score"] for m in x["matches"]]), reverse=True)
    
    return matches

# ===== Main function =====

def main():
    """Main function to scrape candidates, jobs, and find matches."""
    print(f"Fetching candidates from thread ID: {CANDIDATES_THREAD_ID}")
    candidate_comments = fetch_hn_comments(CANDIDATES_THREAD_ID)
    
    print(f"Fetching jobs from thread ID: {JOBS_THREAD_ID}")
    job_comments = fetch_hn_comments(JOBS_THREAD_ID)
    
    if not candidate_comments or not job_comments:
        print("Error: Could not fetch candidates or jobs.")
        return
    
    print(f"Processing {len(candidate_comments)} candidates and {len(job_comments)} jobs...")
    
    # Process candidates
    candidates = []
    for comment in candidate_comments:
        candidate = extract_candidate_fields(comment)
        
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
        
        # Skip entries missing critical fields
        if not job["Company"] and not job["Position"]:
            continue
            
        # Generate summary
        job["Summary"] = generate_job_summary(job)
        jobs.append(job)
    
    print(f"Found {len(candidates)} valid candidates and {len(jobs)} valid job postings.")
    
    # Find matches between candidates and jobs
    min_match_score = 40  # Minimum match score threshold
    matches = find_matches(candidates, jobs, min_score=min_match_score)
    
    # Display all candidates and jobs
    print("\n=== CANDIDATES ===\n")
    for idx, candidate in enumerate(candidates, 1):
        print(f"Candidate {idx}:")
        print(f"Email: {candidate['Email'] or 'Not provided'}")
        print(f"Location: {candidate['Location'] or 'Not provided'}")
        print(f"Remote: {candidate['Remote'] or 'Not provided'}")
        print(f"Technologies: {candidate['Technologies'] or 'Not provided'}")
        print(f"Summary: {candidate['Summary']}")
        print()
    
    print("\n=== JOBS ===\n")
    for idx, job in enumerate(jobs, 1):
        print(f"Job {idx}:")
        print(f"Company: {job['Company'] or 'Not provided'}")
        print(f"Position: {job['Position'] or 'Not provided'}")
        print(f"Location: {job['Location'] or 'Not provided'}")
        print(f"Remote: {job['Remote'] or 'Not provided'}")
        print(f"Technologies: {job['Technologies'] or 'Not provided'}")
        print(f"Summary: {job['Summary']}")
        print()
    
    # Display matches
    print("\n=== MATCHES ===\n")
    if not matches:
        print(f"No matches found with a score of at least {min_match_score}%.")
    else:
        for match in matches:
            candidate = match["candidate"]
            print(f"For candidate: {candidate['Email']} ({candidate['Location'] or 'Unknown location'})")
            
            for job_match in match["matches"]:
                job = job_match["job"]
                score = job_match["match_score"]
                details = job_match["match_details"]
                
                print(f"  → {score}% Match: {job['Company']} - {job['Position']}")
                print(f"    Details: {json.dumps(details, indent=4)}")
                print()
            print("---")
    
    # Save results to a JSON file for further use
    result = {
        "candidates": candidates,
        "jobs": jobs,
        "matches": matches
    }
    
    with open("job_matching_results.json", "w") as f:
        json.dump(result, f, indent=2)
    
    print("\nResults saved to job_matching_results.json")

if __name__ == "__main__":
    main() 