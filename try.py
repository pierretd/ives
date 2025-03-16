import requests
import re
import html
from bs4 import BeautifulSoup

# Hacker News API URL for the specific thread
ITEM_ID = "43243022"  # Replace with your HN thread ID
HN_API_URL = f"https://hacker-news.firebaseio.com/v0/item/{ITEM_ID}.json"

# Required fields for a valid post
REQUIRED_FIELDS = [
    "Location",
    "Remote",
    "Willing to relocate",
    "Technologies",
    "Résumé/CV",
    "Email"
]

# Minimum number of required fields for a valid post
MIN_REQUIRED_FIELDS = 3

def fetch_hn_comments(item_id):
    """Fetches Hacker News thread data and returns the top comments."""
    url = f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
    response = requests.get(url)
    if response.status_code != 200:
        print("Error fetching data.")
        return []
    
    data = response.json()
    if 'kids' not in data:
        print("No comments found.")
        return []
    
    # Fetch comments (increased from 5 to get more valid posts)
    comments = []
    for kid in data['kids'][:10]:  # Get top 10 comments
        comment_data = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{kid}.json").json()
        if 'text' in comment_data:
            comments.append(html.unescape(comment_data['text']))  # Decode HTML entities
    
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

def extract_fields(text):
    """Extracts structured fields from the job post text."""
    # Define the standard fields we're looking for
    fields = {field: None for field in REQUIRED_FIELDS}
    fields["Additional Info"] = None  # For any additional information

    # Clean the text first
    cleaned_text = clean_html(text)
    
    # Extract key fields using regex patterns
    patterns = {
        "Location": r"(?i)(?:^|\n|\s)Location:\s*([^\n]+)",
        "Remote": r"(?i)(?:^|\n|\s)Remote:\s*([^\n]+)",
        "Willing to relocate": r"(?i)(?:^|\n|\s)Willing to relocate:\s*([^\n]+)",
        "Technologies": r"(?i)(?:^|\n|\s)Technologies:\s*([^\n]+)",
        "Résumé/CV": r"(?i)(?:^|\n|\s)(?:Résumé|Resume|CV)(?:/CV)?:\s*(https?://[^\s]+)",
        "Email": r"(?i)(?:^|\n|\s)Email:\s*([\w\.-]+@[\w\.-]+)"
    }
    
    # Apply each pattern
    for field, pattern in patterns.items():
        match = re.search(pattern, cleaned_text)
        if match:
            fields[field] = match.group(1).strip()
    
    # Special handling for URLs which might be broken across lines
    if fields["Résumé/CV"] is None:
        url_pattern = r"(?i)(?:résumé|resume|cv)(?:/cv)?:?\s*(https?://[^\s\n]+)"
        match = re.search(url_pattern, cleaned_text)
        if match:
            fields["Résumé/CV"] = match.group(1).strip()
    
    # If email not found, check for contact info
    if fields["Email"] is None:
        email_pattern = r"(?i)(?:contact|e-mail):\s*([\w\.-]+@[\w\.-]+)"
        match = re.search(email_pattern, cleaned_text)
        if match:
            fields["Email"] = match.group(1).strip()
    
    # Extract additional info - everything that's not part of the standard fields
    lines = cleaned_text.split('\n')
    additional_info = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check if this line contains standard field info
        is_standard_field = False
        for field in REQUIRED_FIELDS:
            if re.search(rf"(?i)^{field}:", line):
                is_standard_field = True
                break
        
        # If not a standard field line, add to additional info
        if not is_standard_field:
            # Check if line contains any of the extracted values
            contains_extracted_value = False
            for value in fields.values():
                if value and value in line:
                    contains_extracted_value = True
                    break
            
            if not contains_extracted_value:
                additional_info.append(line)
    
    if additional_info:
        fields["Additional Info"] = "\n".join(additional_info)
    
    # Count how many required fields are present
    filled_fields = sum(1 for field in REQUIRED_FIELDS if fields[field] is not None)
    
    # Return None if post doesn't meet minimum required fields
    if filled_fields < MIN_REQUIRED_FIELDS:
        return None
    
    return fields

def main():
    """Main function to scrape and process posts."""
    print("Fetching comments from Hacker News thread ID:", ITEM_ID)
    comments = fetch_hn_comments(ITEM_ID)
    
    if not comments:
        print("No comments found or error fetching data.")
        return
    
    print(f"Retrieved {len(comments)} comments. Processing...")
    
    parsed_posts = []
    for comment in comments:
        parsed_post = extract_fields(comment)
        if parsed_post:  # Only add if post meets requirements
            parsed_posts.append(parsed_post)
    
    print(f"Found {len(parsed_posts)} valid posts.")
    print()
    
    # Print extracted posts
    for idx, post in enumerate(parsed_posts, 1):
        print(f"### Post {idx} ###")
        # Print required fields first
        for field in REQUIRED_FIELDS:
            if post[field]:
                print(f"{field}: {post[field]}")
            else:
                print(f"{field}: [Not provided]")
        
        # Print additional info last
        if post["Additional Info"]:
            print("\nInfo about the candidate:")
            print(post["Additional Info"])
        
        print("\n~~~\n")

if __name__ == "__main__":
    main()
