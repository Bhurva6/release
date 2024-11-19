import base64
import requests
import os
import streamlit as st
from dotenv import load_dotenv
from io import BytesIO
from urllib.parse import quote  # For URL encoding

# Load environment variables
load_dotenv()

# Azure DevOps configuration
organization = "BFLDevOpsOrg"
project = "Martech_Unit_Projects"
repository = "3in1cms"  # Verify the exact repository name or use repository ID if necessary
pat = os.getenv("AZURE_DEVOPS_PAT")

if not pat:
    st.error("PAT token not found. Please set AZURE_DEVOPS_PAT in your .env file.")
    st.stop()

# Create proper base64 encoded authorization header
auth_string = base64.b64encode(f":{pat}".encode()).decode()

# Set headers with correct authentication
headers = {
    "Authorization": f"Basic {auth_string}",
    "Accept": "application/json"
}

# Helper function to get pull requests merged into a specified branch
def get_pull_requests(repo_id, branch_name):
    url_prs = (f"https://dev.azure.com/{organization}/{project}/_apis/git/repositories/{repo_id}/pullrequests"
               f"?searchCriteria.targetRefName=refs/heads/{branch_name}&searchCriteria.status=completed&api-version=6.0")
    response_prs = requests.get(url_prs, headers=headers)
    response_prs.raise_for_status()
    return response_prs.json()["value"]

# Helper function to get work items linked to a pull request
def get_work_items_from_pr(repo_id, pr_id):
    url_work_items = (f"https://dev.azure.com/{organization}/{project}/_apis/git/repositories/{repo_id}/pullRequests/{pr_id}/workItems?api-version=6.0")
    response_work_items = requests.get(url_work_items, headers=headers)
    
    if response_work_items.status_code == 404:
        return []
    response_work_items.raise_for_status()
    return response_work_items.json()["value"]

# Main function to generate release notes
def generate_release_notes(branch_name):
    pull_requests = get_pull_requests(repository, branch_name)
    
    user_stories = []
    bugs = []
    release_notes = f"Release Notes for {branch_name}\n\n"

    for pr in pull_requests:
        work_items = get_work_items_from_pr(repository, pr["pullRequestId"])
        
        for work_item in work_items:
            work_item_url = f"https://dev.azure.com/{organization}/{project}/_apis/wit/workitems/{work_item['id']}?api-version=6.0"
            work_item_response = requests.get(work_item_url, headers=headers)
            work_item_details = work_item_response.json()
            
            work_item_type = work_item_details['fields']['System.WorkItemType']
            work_item_title = work_item_details['fields']['System.Title']
            
            item_info = {
                'id': work_item['id'],
                'title': work_item_title,
                'pr_id': pr['pullRequestId'],
                'pr_title': pr['title']
            }
            
            if work_item_type == 'User Story':
                user_stories.append(item_info)
            elif work_item_type == 'Bug':
                bugs.append(item_info)

    release_notes += f"Number of User Stories: {len(user_stories)}\n"
    release_notes += f"Number of Bugs: {len(bugs)}\n\n"

    release_notes += "User Stories:\n\n"
    for story in user_stories:
        release_notes += f"User story {story['id']}: {story['title']}\n"
        release_notes += f"PR {story['pr_id']}: {story['pr_title']}\n\n"

    release_notes += "Bugs:\n\n"
    for bug in bugs:
        release_notes += f"Bug {bug['id']}: {bug['title']}\n"
        release_notes += f"PR {bug['pr_id']}: {bug['pr_title']}\n\n"

    return release_notes

# Helper functions to save release notes to different file formats
def save_as_md(content):
    return BytesIO(content.encode())


# Streamlit UI
st.title("Release Notes")

branch_name = st.text_input("Enter the branch name", value="")

if st.button("Make Release Notes"):
    try:
        release_notes = generate_release_notes(branch_name)
        st.text_area("Release Notes", release_notes, height=300)

        # Encode the release notes for the mailto link
        subject = f"Release Notes for {branch_name}"
        body = quote(release_notes)  # URL-encode the release notes content
  
    except requests.exceptions.HTTPError as e:
        st.error(f"Failed to fetch data: {e}")
