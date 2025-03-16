import requests
from bs4 import BeautifulSoup
import time
import json

# Required fields we want to extract
REQUIRED_FIELDS = [
    "Location",
    "Remote",
    "Willing to relocate",
    "Technologies",
    "Résumé/CV",
    "Email"
]

def scrape_wantstobehired(page=1, per_page=10):
    """
    Scrape job seekers from wantstobehired.com
    """
    url = f"https://www.wantstobehired.com/api/candidates?page={page}&perPage={per_page}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Error: Received status code {response.status_code}")
            return []
            
        data = response.json()
        return data
    except Exception as e:
        print(f"Error fetching data: {e}")
        return []

def extract_fields_from_html(html_content):
    """
    Extract required fields from the HTML content of a candidate profile
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    fields = {field: None for field in REQUIRED_FIELDS}
    fields["Additional Info"] = None
    
    # Find all the field sections in the profile
    field_sections = soup.find_all('p', class_='field')
    
    for section in field_sections:
        label = section.find('span', class_='label')
        value = section.find('span', class_='value')
        
        if label and value:
            label_text = label.text.strip().rstrip(':')
            value_text = value.text.strip()
            
            if label_text in REQUIRED_FIELDS:
                fields[label_text] = value_text
    
    # Extract additional info (usually at the bottom of the profile)
    additional_info_section = soup.find('div', class_='additional-info')
    if additional_info_section:
        fields["Additional Info"] = additional_info_section.text.strip()
    
    return fields

def fetch_candidates(num_candidates=5):
    """
    Fetch a specified number of candidates from wantstobehired.com
    """
    all_candidates = []
    page = 1
    per_page = 10  # Number of candidates per API request
    
    while len(all_candidates) < num_candidates:
        print(f"Fetching page {page}...")
        
        candidates = scrape_wantstobehired(page, per_page)
        if not candidates:
            break
            
        all_candidates.extend(candidates)
        
        # Avoid rate limiting
        time.sleep(1)
        page += 1
    
    return all_candidates[:num_candidates]

def main():
    """Main function to scrape and process job seekers"""
    print("Scraping candidates from wantstobehired.com...")
    
    # Number of candidates to fetch
    num_candidates = 5
    
    candidates = fetch_candidates(num_candidates)
    
    if not candidates:
        print("No candidates found or error fetching data.")
        return
    
    print(f"Retrieved {len(candidates)} candidates. Processing...")
    
    # Process and display each candidate
    for idx, candidate in enumerate(candidates, 1):
        print(f"### Candidate {idx} ###")
        
        # Print required fields first
        for field in REQUIRED_FIELDS:
            field_value = candidate.get(field.lower().replace(' ', '_'), '[Not provided]')
            print(f"{field}: {field_value}")
        
        # Print additional info if available
        additional_info = candidate.get('additional_info', '')
        if additional_info:
            print("\nInfo about the candidate:")
            print(additional_info)
        
        print("\n~~~\n")

if __name__ == "__main__":
    main() 