"""A script for doing AI code reviews using Ollama"""

# ------------------------------
# Rationale for disabled lints
# ------------------------------
# invalid-name: global vars are lowercase, PyLint considers them
# to be consts and flags them.
# global-statement: not typically ideal at scale but this is just
# a small script.
# broad-exception-caught, broad-exception-raised: Similar to ignoring
# global-statement this is for brevity and not ideal at scale.
# Console output will contain error details as much as reasonably possible.
#
#pylint: disable=invalid-name, global-statement, broad-exception-caught, broad-exception-raised

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
GITHUB_USERNAME_KEY = "git-username"
git_username = ""

OLLAMA_URL_KEY = "ollama-url"
OLLAMA_DEFAULT_URL = "http://localhost:11434/api/generate"
ollama_url = OLLAMA_DEFAULT_URL
OLLAMA_DEFAULT_MODEL = "codellama"
ALLOWED_MODELS_KEY = "allowed-models"
allowed_ollama_models = [OLLAMA_DEFAULT_MODEL]
# ------------------------------

def get_json_response_headers():
    """Returns a dict of the default Github api headers"""
    return {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.raw+json",
        "X-GitHub-Api-Version": "2022-11-28"
        }

def do_json_api_post(url, request):
    """POSTs a Github api request, returns the response json"""
    req_body = json.dumps(request)
    r = requests.post(url, headers=get_json_response_headers(), timeout=5, json=req_body)
    r.raise_for_status()
    return r.json()

def do_json_api_get(url):
    """Does a Github api request, returns the response json"""
    r = requests.get(url, headers=get_json_response_headers(), timeout=5)
    r.raise_for_status()
    return r.json()

def do_json_api_request_raw_response(url, headers):
    """Does a Github api request, returns the raw text"""
    r = requests.get(url, headers=headers, timeout=5)
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

    r = requests.post(ollama_url, json=payload, timeout=60)
    r.raise_for_status()
    result = r.json()
    return result.get("response", "").strip()

def read_config():
    """Reads the config in from config.json"""
    print("Reading config from config.json")
    with open('config.json', 'r', encoding='utf-8') as file:
        data = json.load(file)

        if GIT_TOKEN_KEY not in data or len(data[GIT_TOKEN_KEY]) == 0:
            raise Exception("git-token not found in config file!")

        global github_token
        github_token = data[GIT_TOKEN_KEY]

        global ollama_url
        if OLLAMA_URL_KEY in data and len(data[OLLAMA_URL_KEY]) > 0:
            ollama_url = data[OLLAMA_URL_KEY]
        else:
            ollama_url = OLLAMA_DEFAULT_URL

        if ALLOWED_MODELS_KEY in data and len(data[ALLOWED_MODELS_KEY]) > 0:
            allowed_ollama_models.clear()
            for model in data[ALLOWED_MODELS_KEY]:
                allowed_ollama_models.append(model)

        if GITHUB_USERNAME_KEY not in data or len(data[GITHUB_USERNAME_KEY]) == 0:
            raise Exception("git-username not found in config file!")

        global git_username
        git_username = data[GITHUB_USERNAME_KEY]

        repos = data[REPO_LIST_KEY]

        for repo in repos:
            name = repo[REPO_NAME_KEY]
            if name is None or len(name) == 0:
                raise Exception("Repository name is not set! " \
                                "Please ensure it is present for all " \
                                "entries in the repo-list.")
            owner = repo[REPO_OWNER_KEY]
            if owner is None or len(owner) == 0:
                raise Exception("Repository owner is not set! " \
                                "Please ensure it is present for all " \
                                "entries in the repo-list.")
            repo_list.append({REPO_NAME_KEY:name, REPO_OWNER_KEY:owner})

        if len(repo_list) == 0:
            raise Exception("Repository list is empty! Please include a " \
                            "list of objects with a name and owner.")

def do_review(pull) -> str:
    """Sends the git diff to Ollama for review, returns the review text."""
    pr_title = pull["title"]
    pr_url = pull["url"]
    diff_headers = get_json_response_headers()
    diff_headers["Accept"] = "application/vnd.github.diff"
    diff = do_json_api_request_raw_response(pr_url, diff_headers)
    print("\nSending diff to Ollama for review...")

    # trim to avoid overly large prompt
    review = ask_ollama_for_review(pr_title, diff[:4000])
    print("\n--- Ollama Review ---")
    print(review)
    return review

def process_pull_requests(pulls):
    """Checks comments on pull requests and requests Ollama for code reviews"""
    for pr in pulls:
        pr_number = pr["number"]
        pr_title = pr["title"]
        comments_url = pr["review_comments_url"]
        print(f"\n=== PR #{pr_number}: {pr_title} ===")

        comments = do_json_api_get(comments_url)
        if comments:
            print("GitHub Comments:")
            for c in comments:
                comment_body = c['body']
                print(f"- {c['user']['login']}: {comment_body}")
                if f"@{git_username}" in comment_body:
                    comment_api_url = pr["review_comments_url"]
                    review_content = do_review(pr)
                    do_json_api_post(comment_api_url, {'body': review_content})
                else:
                    print(f"Comment does not mention {git_username}. Ignoring...")
        else:
            print("No GitHub comments.")


def do_reviews():
    """Checks the configured repositories for open pull requests to review 
    and sends git diff to Ollama for review"""
    print("Checking for open pull requests")
    try:
        for repo in repo_list:
            owner = repo[REPO_OWNER_KEY]
            name = repo[REPO_NAME_KEY]
            open_prs_url = f"{API_BASE}/repos/{owner}/{name}/pulls?state=open"
            pulls = do_json_api_get(open_prs_url)

            if not pulls:
                print("No open pull requests.")
            else:
                process_pull_requests(pulls)
        print("\nWaiting one minute...")
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
        repo_list_printable = list(map(
            lambda x: f"""{x[REPO_OWNER_KEY]}/{x[REPO_NAME_KEY]}""",
            repo_list))
        print("Watching repositories: ", repo_list_printable)
    except Exception as e:
        print("Error while trying to read in config:", e)
        return -1
    while True:
        do_reviews()

if __name__ == "__main__":
    main()
