import json
import textwrap
import time

import requests

# ------------------------------
# CONFIG
# ------------------------------
github_token = ""
REPO_OWNER_KEY = "owner"
REPO_NAME_KEY = "name"
REPO_LIST_KEY = "repositories"
repo_list = []
GIT_TOKEN_KEY = "git-token"
API_BASE = "https://api.github.com"

OLLAMA_URL_KEY = "ollama-url"
OLLAMA_DEFAULT_URL = "http://localhost:11434/api/generate"
ollama_url = OLLAMA_DEFAULT_URL
OLLAMA_DEFAULT_MODEL = "codellama"
# ------------------------------

def get_headers():
    return {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.raw+json",
        "X-GitHub-Api-Version": "2022-11-28"
        }

def get_pull_requests(owner, repo):
    url = f"{API_BASE}/repos/{owner}/{repo}/pulls?state=open"
    r = requests.get(url, headers=get_headers())
    r.raise_for_status()
    return r.json()


def get_pull_request_comments(owner, repo, pr_number):
    url = f"{API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/comments"
    r = requests.get(url, headers=get_headers())
    r.raise_for_status()
    return r.json()


def get_pull_request_diff(owner, repo, pr_number):
    url = f"{API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}"
    diff_headers = get_headers().copy()
    diff_headers["Accept"] = "application/vnd.github.diff"
    r = requests.get(url, headers=diff_headers)
    r.raise_for_status()
    return r.text


def ask_ollama_for_review(title, diff_text):
    """Send the diff to Ollama and request a code review"""
    prompt = textwrap.dedent(f"""
    You are a senior software engineer. Review the Git diff which came from 
    a pull request titled {title}. Point out potential bugs, style issues, 
    and improvements. Include example code in review feedback.

    Diff:
    {diff_text}
    """)
    
    payload = {
        "model": OLLAMA_DEFAULT_MODEL,
        "prompt": prompt,
        "stream": False
    }

    r = requests.post(ollama_url, json=payload)
    r.raise_for_status()
    result = r.json()
    return result.get("response", "").strip()

def read_config():
    """Reads the config in from config.json"""
    print("Reading config from config.json")
    with open('config.json', 'r') as file:
        data = json.load(file)

        global github_token
        github_token = data[GIT_TOKEN_KEY]
        if len(github_token) == 0:
            raise Exception("git-token not found in config file!")
        
        global ollama_url
        optional_ollama_url = data[OLLAMA_URL_KEY]
        if OLLAMA_URL_KEY in data and len(optional_ollama_url) > 0:
            ollama_url = optional_ollama_url
        else:
            ollama_url = OLLAMA_DEFAULT_URL

        repos = data[REPO_LIST_KEY]

        for repo in repos:
            name = repo[REPO_NAME_KEY]
            if name is None or len(name) == 0:
                raise Exception("""Repository name is not set! 
                                Please ensure it is present for all 
                                entries in the repo-list.""")
            owner = repo[REPO_OWNER_KEY]
            if owner is None or len(owner) == 0:
                raise Exception("""Repository owner is not set! 
                                Please ensure it is present for all 
                                entries in the repo-list.""")
            repo_list.append({REPO_NAME_KEY:name, REPO_OWNER_KEY:owner})
        
        if repo_list.count == 0:
            raise Exception("""repos list is empty! Please include a 
                            list of objects with a name and owner.""")

def do_reviews():
    """Checks the configured repositories for open pull requests to review 
    and sends git diff to Ollama for review"""
    print("Checking for open pull requests")
    try:
        for repo in repo_list:
            owner = repo[REPO_OWNER_KEY]
            name = repo[REPO_NAME_KEY]
            pulls = get_pull_requests(owner, name)

            if not pulls:
                print("No open pull requests.")
            else:
                for pr in pulls:
                    pr_number = pr["number"]
                    pr_title = pr["title"]
                    print(f"\n=== PR #{pr_number}: {pr_title} ===")

                    comments = get_pull_request_comments(owner, name, pr_number)
                    if comments:
                        print("GitHub Comments:")
                        for c in comments:
                            print(f"- {c['user']['login']}: {c['body']}")
                    else:
                        print("No GitHub comments.")

                    diff = get_pull_request_diff(owner, name, pr_number)
                    print("\nSending diff to Ollama for review...")

                    # trim to avoid overly large prompt
                    review = ask_ollama_for_review(pr_title, diff[:4000])
                    print("\n--- Ollama Review ---")
                    print(review)
        print("Waiting one minute...")
        time.sleep(60)
    except Exception as e:
        print("Encountered error:", e)
        time.sleep(5 * 60)

def main():
    """Reads in the config then runs the loop to check specified repos 
    for pull requests then post code reviews from Ollama"""
    try:
        read_config()
        print(f"Ollama url: {ollama_url}")
        repo_list_printable = list(map(lambda x: f"{x[REPO_OWNER_KEY]}/{x[REPO_NAME_KEY]}", repo_list))
        print("Watching repositories: ", repo_list_printable)
    except Exception as e:
        print("Error while trying to read in config:", e)
        return -1
    while True:
        do_reviews()

if __name__ == "__main__":
    main()
