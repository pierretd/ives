#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def print_header():
    """Print the application header."""
    print("\n" + "=" * 50)
    print(" HN JOBS & CANDIDATES MATCHING SYSTEM")
    print("=" * 50)

def check_requirements():
    """Check if all required modules are installed."""
    required_modules = [
        "requests", "bs4", "openai", "qdrant_client"
    ]
    
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        print("Missing required modules. Please install:")
        print(f"pip install {' '.join(missing_modules)}")
        return False
    
    return True

def check_api_key():
    """Check if OpenAI API key is set."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or api_key == "your_openai_api_key_here":
        print("ERROR: OpenAI API key is not set.")
        print("Please set OPENAI_API_KEY in your .env file or environment variables.")
        return False
    return True

def check_qdrant_config():
    """Check if Qdrant configuration is set properly."""
    qdrant_url = os.environ.get("QDRANT_URL")
    
    # Check for Qdrant Cloud configuration
    if qdrant_url and qdrant_url != "localhost" and "cloud.qdrant.io" in qdrant_url:
        api_key = os.environ.get("QDRANT_API_KEY")
        if not api_key:
            print("WARNING: Using Qdrant Cloud but QDRANT_API_KEY is not set.")
            print("Please set QDRANT_API_KEY in your .env file or environment variables.")
            return False
        
        print(f"Qdrant Cloud configuration detected: {qdrant_url}")
        return True
    
    # If using local Qdrant or other URL
    print(f"Using Qdrant at: {qdrant_url or 'localhost'}")
    return True

def run_script(script_name):
    """Run a Python script and return its exit code."""
    print(f"\nRunning {script_name}...\n")
    
    # For the upsert script, capture the output to a file
    if script_name == "upsert_to_qdrant.py":
        exit_code = os.system(f"python {script_name} > upsert_output.txt 2>&1")
    else:
        exit_code = os.system(f"python {script_name}")
    
    return exit_code

def main():
    """Main function to automatically extract data and upsert to Qdrant."""
    print_header()
    
    # Check if all requirements are met
    if not check_requirements():
        print("Please install the required dependencies and try again.")
        sys.exit(1)
    
    # Check Qdrant configuration
    if not check_qdrant_config():
        print("ERROR: Qdrant configuration is missing or incomplete.")
        sys.exit(1)
    
    # Check if OpenAI API key is set
    if not check_api_key():
        print("ERROR: OpenAI API key is not set.")
        sys.exit(1)
    
    print("\nAutomatically extracting data and upserting to Qdrant...")
    
    # Step 1: Extract candidate data
    print("\n[Step 1/4] Extracting candidate data...")
    run_script("extract_hn_candidates.py")
    
    # Step 2: Extract job data
    print("\n[Step 2/4] Extracting job data...")
    run_script("extract_hn_jobs.py")
    
    # Step 3: Run basic matching to generate job_matching_results.json
    print("\n[Step 3/4] Running basic matching...")
    run_script("job_matcher.py")
    
    # Step 4: Generate embeddings and upload to Qdrant
    print("\n[Step 4/4] Generating embeddings and upserting to Qdrant...")
    exit_code = run_script("upsert_to_qdrant.py")
    
    # Check if operation was successful by looking for the success message in the output
    success = False
    if os.path.exists("upsert_output.txt"):
        with open("upsert_output.txt", "r") as f:
            output = f.read()
            if "Successfully upserted" in output:
                success = True
    
    if success or exit_code == 0:
        print("\n✅ Success! Data has been extracted and upserted to Qdrant.")
        print("Collection name: hacker_news_jobs")
        print("\nYou can now query the data using a vector search.")
    else:
        print("\n❌ Error occurred during the process. Please check the logs above.")
        # Show the error from the output file
        if os.path.exists("upsert_output.txt"):
            with open("upsert_output.txt", "r") as f:
                print("\nError details from upsert operation:")
                error_lines = [line for line in f.readlines() if "Error" in line or "Exception" in line]
                for line in error_lines[-5:]:  # Show the last 5 error lines
                    print(line.strip())

if __name__ == "__main__":
    main() 