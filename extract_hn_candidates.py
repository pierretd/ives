import requests
import re
import html
from bs4 import BeautifulSoup
from datetime import datetime

# Hacker News API URL for the specific thread
ITEM_ID = "43243022"  # Replace with your HN thread ID
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

def extract_fields(comment):
    """Extracts structured fields from a HN comment."""
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
        "Link to HN": f"{HN_BASE_URL}{ITEM_ID}#{comment['id']}",
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

def generate_summary(fields):
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

def main():
    """Main function to scrape and process job seekers."""
    print(f"Fetching comments from Hacker News thread ID: {ITEM_ID}")
    # Get all comments without a limit
    comments = fetch_hn_comments(ITEM_ID)
    
    if not comments:
        print("No comments found or error fetching data.")
        return
    
    print(f"Retrieved {len(comments)} comments. Processing...")
    
    # Process each comment
    candidates = []
    for comment in comments:
        candidate = extract_fields(comment)
        
        # Skip entries missing critical fields
        if not candidate["Email"] and not candidate["Resume"] and not candidate["Location"]:
            continue
            
        # Generate summary
        candidate["Summary"] = generate_summary(candidate)
        candidates.append(candidate)
    
    print(f"Found {len(candidates)} valid candidate listings.")
    
    # Print in the desired format
    for candidate in candidates:
        print("Date:", candidate["Date"])
        print("Email:", candidate["Email"] or "Not provided")
        print("Resume:", candidate["Resume"] or "Not provided")
        print("Location:", candidate["Location"] or "Not provided")
        print("Remote:", candidate["Remote"] or "Not provided")
        print("Willing to Relocate:", candidate["Willing to Relocate"] or "Not provided")
        print("Technologies:", candidate["Technologies"] or "Not provided")
        print("Link to HN:", candidate["Link to HN"])
        print("Summary:", candidate["Summary"])
        print("\n---\n")

if __name__ == "__main__":
    main() 