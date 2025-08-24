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

from github_api import GitHubApi, GitHubComment, GitHubConfig, GitHubRepo
from ollama_api import OllamaApi, OllamaConfig

# ------------------------------
# CONFIG
# ------------------------------
REPO_OWNER_KEY = "owner"
REPO_NAME_KEY = "name"
REPO_LIST_KEY = "repositories"
GIT_TOKEN_KEY = "git-token"
GITHUB_USERNAME_KEY = "git-username"
git_username: str
config: GitHubConfig
git_api: GitHubApi

OLLAMA_URL_KEY = "ollama-url"
OLLAMA_DEFAULT_URL = "http://localhost:11434"
AI_MODEL_NAME_KEY = "ai-model"
DEFAULT_AI_MODEL = "codellama"
ollama_api: OllamaApi

ALLOWED_MODELS_KEY = "allowed-models"
allowed_models = []
# ------------------------------

#pylint: disable=too-many-branches
def read_config():
    """Reads the config in from config.json"""
    print("Reading config from config.json")
    with open('config.json', 'r', encoding='utf-8') as file:
        data = json.load(file)

        if GIT_TOKEN_KEY not in data or len(data[GIT_TOKEN_KEY]) == 0:
            raise Exception("git-token not found in config file!")
        github_token = data[GIT_TOKEN_KEY]

        ollama_url: str
        if OLLAMA_URL_KEY in data and len(data[OLLAMA_URL_KEY]) > 0:
            ollama_url = data[OLLAMA_URL_KEY]
        else:
            ollama_url = OLLAMA_DEFAULT_URL

        print(f"Ollama url: {ollama_url}")

        model_name = DEFAULT_AI_MODEL
        if AI_MODEL_NAME_KEY in data and len(data[AI_MODEL_NAME_KEY]) > 0:
            model_name = data[AI_MODEL_NAME_KEY]

        global ollama_api
        ollama_config = OllamaConfig(ollama_url, model_name)
        ollama_api = OllamaApi(ollama_config)

        if ALLOWED_MODELS_KEY in data and len(data[ALLOWED_MODELS_KEY]) > 0:
            allowed_models.clear()
            for model in data[ALLOWED_MODELS_KEY]:
                allowed_models.append(model)

        if len(allowed_models) > 0:
            if model_name not in allowed_models:
                raise Exception(f"{model_name} is not in allowed models list {allowed_models}!")

        if GITHUB_USERNAME_KEY not in data or len(data[GITHUB_USERNAME_KEY]) == 0:
            raise Exception("git-username not found in config file!")

        global git_username
        git_username = data[GITHUB_USERNAME_KEY]

        repos = data[REPO_LIST_KEY]
        repo_list = []

        for repo in repos:
            name = repo[REPO_NAME_KEY]
            if name is None or len(name) == 0:
                raise Exception("Repository name is not set! " +
                                "Please ensure it is present for all " +
                                "entries in the repo-list.")
            owner = repo[REPO_OWNER_KEY]
            if owner is None or len(owner) == 0:
                raise Exception("Repository owner is not set! " +
                                "Please ensure it is present for all " +
                                "entries in the repo-list.")
            repo_list.append(GitHubRepo(name=name, owner=owner))

        if len(repo_list) == 0:
            raise Exception("Repository list is empty! Please include a " +
                            "list of objects with a name and owner.")

        global config, git_api
        config = GitHubConfig(repo_list=repo_list, token=github_token)
        git_api = GitHubApi(config=config)

def do_review(pull) -> str:
    """Sends the git diff to Ollama for review, returns the review text."""
    pr_title = pull["title"]
    diff = git_api.get_pr_diff(pull)
    print("\nSending diff to Ollama for review...")

    # The prompt - truncate diff to 4000 characters to avoid overly large prompt
    request = textwrap.dedent(f"""
                              You are a senior software engineer. Review the included
                              code from a pull reuqest titled {pr_title}.
                              Point out potential bugs, style issues,
                              and improvements. Include example code in review feedback.
                              {diff[:4000]}""")

    # trim to avoid overly large prompt
    review = ollama_api.do_generation(request)
    print("\n--- Ollama Review ---")
    print(review)
    return review

def process_pull_requests(pulls):
    """Checks comments on pull requests and requests Ollama for code reviews"""
    for pr in pulls:
        comments = git_api.get_comments_for_pr(pr)
        if comments:
            print("GitHub Comments:")
            review_requested = False
            for c in comments:
                comment_username = c.get_username()
                comment_body = c.get_comment_body()
                print(f"- {comment_username}: {comment_body[:140]}")
                if git_username in comment_username:
                    review_requested = False
                elif f"@{git_username}" in comment_body:
                    review_requested = True
            if review_requested:
                review_content = do_review(pr)
                git_api.post_comment(pr, review_content)
            else:
                print(f"\nNot doing a review. No @{git_username} comment found " +
                      f"or the last comment was posted by {git_username}.")
        else:
            print("No GitHub comments.")

# Pylint added because the loop just prints any error
# Then waits for longer than normal to loop again
#pylint: disable=bare-except
def main():
    """Reads in the config then runs the loop to check specified repos 
    for pull requests then post code reviews from Ollama"""
    try:
        read_config()
        repo_list_printable = list(map(
            lambda x: f"""{x.owner}/{x.name}""",
            config.repo_list))
        print("Watching repositories: ", repo_list_printable)
    except Exception as e:
        print("Error while trying to read in config:", e)
        return -1
    while True:
        try:
            open_prs = git_api.get_open_prs()
            if open_prs is not None and len(open_prs) > 0:
                process_pull_requests(open_prs)
            time.sleep(30)
        except Exception as e:
            print(f"ERROR {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
