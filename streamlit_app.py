import streamlit as st
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Set page config
st.set_page_config(
    page_title="Job Matcher Dashboard",
    page_icon="💼",
    layout="wide"
)

# Title and description
st.title("Hacker News Job Matcher Dashboard")
st.markdown("This dashboard shows matches between job seekers and job postings from Hacker News 'Who wants to be hired' and 'Who is hiring' threads.")

# Load data from JSON file
@st.cache_data
def load_data():
    if Path("job_matching_results.json").exists():
        with open("job_matching_results.json", "r") as f:
            data = json.load(f)
        return data
    else:
        st.error("Data file not found. Please run job_matcher.py first to generate the data.")
        return None

data = load_data()

if data:
    # Create tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["Matches", "Candidates", "Jobs", "Analytics"])
    
    # Tab 1: Matches
    with tab1:
        st.header("Matches")
        
        # Sidebar filters for matches
        st.sidebar.header("Match Filters")
        min_score = st.sidebar.slider("Minimum Match Score", 0, 100, 40)
        
        if 'matches' in data:
            # Filter matches by score
            filtered_matches = []
            for match_group in data['matches']:
                candidate = match_group['candidate']
                job_matches = [m for m in match_group['matches'] if m['match_score'] >= min_score]
                
                if job_matches:
                    filtered_matches.append({
                        'candidate': candidate,
                        'matches': job_matches
                    })
            
            # Display matches
            if not filtered_matches:
                st.info(f"No matches found with a score of at least {min_score}%.")
            else:
                for idx, match in enumerate(filtered_matches, 1):
                    candidate = match['candidate']
                    
                    with st.expander(f"Candidate: {candidate['Email'] or 'Anonymous'} ({candidate['Location'] or 'Unknown location'})"):
                        # Display candidate info
                        col1, col2 = st.columns(2)
                        with col1:
                            st.subheader("Candidate Information")
                            st.write(f"**Email:** {candidate['Email'] or 'Not provided'}")
                            st.write(f"**Location:** {candidate['Location'] or 'Not provided'}")
                            st.write(f"**Remote:** {candidate['Remote'] or 'Not provided'}")
                            st.write(f"**Technologies:** {candidate['Technologies'] or 'Not provided'}")
                            
                            if candidate['Resume']:
                                st.write(f"**Resume:** [Link]({candidate['Resume']})")
                            
                            st.write(f"**HN Link:** [Link to thread]({candidate['Link to HN']})")
                        
                        with col2:
                            st.subheader("Matching Jobs")
                            for job_match in match['matches']:
                                job = job_match['job']
                                score = job_match['match_score']
                                details = job_match['match_details']
                                
                                job_card = f"""
                                **{score}% Match: {job['Company'] or 'Unknown company'} - {job['Position'] or 'Unknown position'}**
                                
                                * **Location:** {job['Location'] or 'Not specified'}
                                * **Remote:** {job['Remote'] or 'Not specified'}
                                * **Technologies:** {job['Technologies'] or 'Not specified'}
                                * **Match Details:** {', '.join([f"{k}: {v}" for k, v in details.items() if k != 'matching_tech'])}
                                """
                                
                                if 'matching_tech' in details:
                                    job_card += f"\n* **Matching Technologies:** {', '.join(details['matching_tech'])}"
                                
                                st.markdown(job_card)
                                st.markdown("---")
    
    # Tab 2: Candidates
    with tab2:
        st.header("Candidates")
        
        if 'candidates' in data:
            # Sidebar filters for candidates
            st.sidebar.header("Candidate Filters")
            remote_filter = st.sidebar.radio("Remote Preference", ["All", "Yes", "No"])
            
            location_list = sorted(list(set([c['Location'] for c in data['candidates'] if c['Location']])))
            location_filter = st.sidebar.multiselect("Location", ["All"] + location_list, default="All")
            
            # Extract unique technologies across all candidates
            all_tech = set()
            for candidate in data['candidates']:
                if candidate['Technologies']:
                    tech_list = [t.strip().lower() for t in candidate['Technologies'].split(',')]
                    all_tech.update(tech_list)
            
            tech_filter = st.sidebar.multiselect("Technologies", ["All"] + sorted(list(all_tech)), default="All")
            
            # Apply filters
            filtered_candidates = data['candidates']
            
            if remote_filter != "All":
                filtered_candidates = [c for c in filtered_candidates if c['Remote'] and remote_filter.lower() in c['Remote'].lower()]
            
            if "All" not in location_filter:
                filtered_candidates = [c for c in filtered_candidates if c['Location'] and any(loc in c['Location'] for loc in location_filter)]
            
            if "All" not in tech_filter:
                filtered_candidates = [c for c in filtered_candidates if c['Technologies'] and any(tech.lower() in c['Technologies'].lower() for tech in tech_filter)]
            
            # Display candidates
            st.write(f"Showing {len(filtered_candidates)} candidates")
            
            for idx, candidate in enumerate(filtered_candidates, 1):
                with st.expander(f"{candidate['Email'] or 'Anonymous'} - {candidate['Location'] or 'Unknown location'}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Email:** {candidate['Email'] or 'Not provided'}")
                        st.write(f"**Location:** {candidate['Location'] or 'Not provided'}")
                        st.write(f"**Remote:** {candidate['Remote'] or 'Not provided'}")
                        st.write(f"**Willing to Relocate:** {candidate['Willing to Relocate'] or 'Not provided'}")
                        
                        if candidate['Resume']:
                            st.write(f"**Resume:** [Link]({candidate['Resume']})")
                        
                        st.write(f"**HN Link:** [Link to thread]({candidate['Link to HN']})")
                    
                    with col2:
                        st.write(f"**Technologies:** {candidate['Technologies'] or 'Not provided'}")
                        st.write(f"**Summary:** {candidate['Summary']}")
    
    # Tab 3: Jobs
    with tab3:
        st.header("Jobs")
        
        if 'jobs' in data:
            # Sidebar filters for jobs
            st.sidebar.header("Job Filters")
            remote_job_filter = st.sidebar.radio("Remote Job", ["All", "Yes", "No"], key="remote_job")
            
            job_location_list = sorted(list(set([j['Location'] for j in data['jobs'] if j['Location']])))
            job_location_filter = st.sidebar.multiselect("Job Location", ["All"] + job_location_list, default="All", key="job_loc")
            
            # Extract unique technologies across all jobs
            all_job_tech = set()
            for job in data['jobs']:
                if job['Technologies']:
                    job_tech_list = [t.strip().lower() for t in job['Technologies'].split(',')]
                    all_job_tech.update(job_tech_list)
            
            job_tech_filter = st.sidebar.multiselect("Job Technologies", ["All"] + sorted(list(all_job_tech)), default="All", key="job_tech")
            
            # Apply filters
            filtered_jobs = data['jobs']
            
            if remote_job_filter != "All":
                filtered_jobs = [j for j in filtered_jobs if j['Remote'] and remote_job_filter.lower() in j['Remote'].lower()]
            
            if "All" not in job_location_filter:
                filtered_jobs = [j for j in filtered_jobs if j['Location'] and any(loc in j['Location'] for loc in job_location_filter)]
            
            if "All" not in job_tech_filter:
                filtered_jobs = [j for j in filtered_jobs if j['Technologies'] and any(tech.lower() in j['Technologies'].lower() for tech in job_tech_filter)]
            
            # Display jobs
            st.write(f"Showing {len(filtered_jobs)} jobs")
            
            for idx, job in enumerate(filtered_jobs, 1):
                with st.expander(f"{job['Company'] or 'Unknown company'} - {job['Position'] or 'Unknown position'}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Company:** {job['Company'] or 'Not provided'}")
                        st.write(f"**Position:** {job['Position'] or 'Not provided'}")
                        st.write(f"**Location:** {job['Location'] or 'Not provided'}")
                        st.write(f"**Remote:** {job['Remote'] or 'Not provided'}")
                        st.write(f"**Salary:** {job['Salary'] or 'Not provided'}")
                        st.write(f"**HN Link:** [Link to thread]({job['Link to HN']})")
                    
                    with col2:
                        st.write(f"**Technologies:** {job['Technologies'] or 'Not provided'}")
                        st.write(f"**Description:** {job['Description'] or 'Not provided'}")
                        st.write(f"**Apply:** {job['Apply'] or 'Not provided'}")
                        st.write(f"**Summary:** {job['Summary']}")
    
    # Tab 4: Analytics
    with tab4:
        st.header("Analytics")
        
        if all(k in data for k in ['candidates', 'jobs', 'matches']):
            col1, col2 = st.columns(2)
            
            with col1:
                # Top technologies in demand
                st.subheader("Top Technologies in Demand")
                
                job_technologies = {}
                for job in data['jobs']:
                    if job['Technologies']:
                        tech_list = extract_technologies(job['Technologies'])
                        for tech in tech_list:
                            job_technologies[tech] = job_technologies.get(tech, 0) + 1
                
                if job_technologies:
                    # Sort and get top 10
                    top_job_tech = dict(sorted(job_technologies.items(), key=lambda x: x[1], reverse=True)[:10])
                    
                    # Create bar chart
                    fig, ax = plt.subplots(figsize=(10, 6))
                    sns.barplot(x=list(top_job_tech.values()), y=list(top_job_tech.keys()), palette="viridis")
                    ax.set_title("Top 10 Technologies in Job Postings")
                    ax.set_xlabel("Number of Jobs")
                    st.pyplot(fig)
            
            with col2:
                # Top candidate technologies
                st.subheader("Top Candidate Technologies")
                
                candidate_technologies = {}
                for candidate in data['candidates']:
                    if candidate['Technologies']:
                        tech_list = extract_technologies(candidate['Technologies'])
                        for tech in tech_list:
                            candidate_technologies[tech] = candidate_technologies.get(tech, 0) + 1
                
                if candidate_technologies:
                    # Sort and get top 10
                    top_candidate_tech = dict(sorted(candidate_technologies.items(), key=lambda x: x[1], reverse=True)[:10])
                    
                    # Create bar chart
                    fig, ax = plt.subplots(figsize=(10, 6))
                    sns.barplot(x=list(top_candidate_tech.values()), y=list(top_candidate_tech.keys()), palette="rocket")
                    ax.set_title("Top 10 Technologies Among Candidates")
                    ax.set_xlabel("Number of Candidates")
                    st.pyplot(fig)
            
            # Distribution of match scores
            st.subheader("Match Score Distribution")
            all_scores = []
            for match_group in data['matches']:
                for job_match in match_group['matches']:
                    all_scores.append(job_match['match_score'])
            
            if all_scores:
                fig, ax = plt.subplots(figsize=(10, 6))
                sns.histplot(all_scores, bins=10, kde=True)
                ax.set_title("Distribution of Match Scores")
                ax.set_xlabel("Match Score")
                ax.set_ylabel("Frequency")
                st.pyplot(fig)
            
            # Remote job availability
            st.subheader("Remote Work Preferences")
            
            # Count remote preferences in jobs and candidates
            remote_stats = {
                "Jobs": {"Yes": 0, "No": 0, "Not Specified": 0},
                "Candidates": {"Yes": 0, "No": 0, "Not Specified": 0}
            }
            
            for job in data['jobs']:
                if not job['Remote']:
                    remote_stats["Jobs"]["Not Specified"] += 1
                elif "yes" in job['Remote'].lower() or "remote" in job['Remote'].lower():
                    remote_stats["Jobs"]["Yes"] += 1
                else:
                    remote_stats["Jobs"]["No"] += 1
            
            for candidate in data['candidates']:
                if not candidate['Remote']:
                    remote_stats["Candidates"]["Not Specified"] += 1
                elif "yes" in candidate['Remote'].lower():
                    remote_stats["Candidates"]["Yes"] += 1
                else:
                    remote_stats["Candidates"]["No"] += 1
            
            # Create DataFrame for plotting
            remote_df = pd.DataFrame({
                "Jobs": [remote_stats["Jobs"]["Yes"], remote_stats["Jobs"]["No"], remote_stats["Jobs"]["Not Specified"]],
                "Candidates": [remote_stats["Candidates"]["Yes"], remote_stats["Candidates"]["No"], remote_stats["Candidates"]["Not Specified"]]
            }, index=["Yes", "No", "Not Specified"])
            
            # Plot
            fig, ax = plt.subplots(figsize=(10, 6))
            remote_df.plot(kind="bar", ax=ax)
            ax.set_title("Remote Work Preferences")
            ax.set_ylabel("Count")
            ax.legend(title="Category")
            st.pyplot(fig)

# Helper function to extract technologies from text
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
    import re
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    # Find matching tech keywords
    found_tech = set()
    for keyword in tech_keywords:
        if f' {keyword} ' in f' {text} ' or keyword in text.split():
            found_tech.add(keyword)
    
    return found_tech 