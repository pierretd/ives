import requests
import re
import html
from bs4 import BeautifulSoup
from datetime import datetime

# Hacker News API URL for the "Who is hiring" thread
ITEM_ID = "43243024"  # Who is hiring thread ID
HN_BASE_URL = "https://news.ycombinator.com/item?id="

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
        "Link to HN": f"{HN_BASE_URL}{ITEM_ID}#{comment['id']}",
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
        match = re.search(pattern, text)
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

def main():
    """Main function to scrape and process job postings."""
    print(f"Fetching job postings from Hacker News thread ID: {ITEM_ID}")
    # Get all job postings
    comments = fetch_hn_comments(ITEM_ID)
    
    if not comments:
        print("No job postings found or error fetching data.")
        return
    
    print(f"Retrieved {len(comments)} job postings. Processing...")
    
    # Process each job posting
    jobs = []
    for comment in comments:
        job = extract_job_fields(comment)
        
        # Skip entries missing critical fields - must have either company or position
        if not job["Company"] and not job["Position"]:
            continue
            
        # Generate summary
        job["Summary"] = generate_job_summary(job)
        jobs.append(job)
    
    print(f"Found {len(jobs)} valid job postings.")
    
    # Print in the desired format
    for job in jobs:
        print("Date:", job["Date"])
        print("Company:", job["Company"] or "Not provided")
        print("Position:", job["Position"] or "Not provided")
        print("Location:", job["Location"] or "Not provided")
        print("Remote:", job["Remote"] or "Not provided")
        print("Salary:", job["Salary"] or "Not provided")
        print("Technologies:", job["Technologies"] or "Not provided")
        print("Description:", job["Description"] or "Not provided")
        print("Apply:", job["Apply"] or "Not provided")
        print("Link to HN:", job["Link to HN"])
        print("Summary:", job["Summary"])
        print("\n---\n")

if __name__ == "__main__":
    main() 