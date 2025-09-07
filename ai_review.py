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
import re
import textwrap
import time
from typing import Optional

from github_api import (GitHubApi, GitHubChangedFile, GitHubComment, GitHubPr,
                        GitHubRepo)
from gitlab_api import GitLabApi, GitLabMergeRequest, GitLabNote
from ollama_api import OllamaApi, OllamaConfig

# ------------------------------
# CONFIG
# ------------------------------
REPO_OWNER_KEY = "owner"
REPO_NAME_KEY = "name"
REPO_LIST_KEY = "repositories"
PROJECT_LIST_KEY = "projects"
GIT_BASE_URL = "git-url"
GIT_TOKEN_KEY = "token"
GITHUB_USERNAME_KEY = "username"
OLLAMA_URL_KEY = "ollama-url"
OLLAMA_DEFAULT_URL = "http://localhost:11434"
AI_MODEL_NAME_KEY = "ai-model"
DEFAULT_AI_MODEL = "codellama"

ollama_api: OllamaApi
git_username: str
gitlab_api: GitLabApi
gitlab_projects = list[str]
github_api: GitHubApi
github_repos: list[GitHubRepo]

ALLOWED_MODELS_KEY = "allowed-models"
allowed_models = []
# ------------------------------

def get_api() -> GitHubApi | GitLabApi:
    """Returns the configured Git API"""
    if github_api is not None:
        return github_api
    if gitlab_api is not None:
        return gitlab_api
    raise Exception('No APIs available! Check your configuration.')

#pylint: disable=too-many-branches
def read_config():
    """Reads the config in from config.json"""
    print("Reading config from config.json")
    try:
        with open('config.json', 'r', encoding='utf-8') as file:
            data = json.load(file)

            if GIT_TOKEN_KEY not in data or len(data[GIT_TOKEN_KEY]) == 0:
                raise Exception("git-token not found in config file!")
            git_token = data[GIT_TOKEN_KEY]

            if GIT_BASE_URL not in data or len(data[GIT_BASE_URL]) == 0:
                raise Exception("git-url not found in config file!")

            git_url = data[GIT_BASE_URL]

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

            projects = data[PROJECT_LIST_KEY]

            for repo in repos:
                name = repo[REPO_NAME_KEY]
                if name is None or len(name) == 0:
                    raise Exception("Repository name is not set! "\
                                    "Please ensure it is present for all "\
                                    "entries in the repo-list.")
                owner = repo[REPO_OWNER_KEY]
                if owner is None or len(owner) == 0:
                    raise Exception("Repository owner is not set! " +
                                    "Please ensure it is present for all "\
                                    "entries in the repo-list.")
                repo_list.append(GitHubRepo(name=name, owner=owner, html_url=""))

            if len(repo_list) > 0:
                global github_repos, github_api
                github_repos = repo_list
                github_api = GitHubApi(git_token)
            elif len(projects) > 0:
                global gitlab_projects, gitlab_api
                gitlab_projects = projects
                gitlab_api = GitLabApi(git_url, git_token)
            else:
                raise Exception("No GitHub repositories or GitLab projects found in the config!")
    except FileNotFoundError as file_not_found_err:
        print("config.json not found! Please create it. See: config_template.json "\
              "for a starting point")
        raise file_not_found_err

def do_review(pull: GitLabMergeRequest | GitHubPr, code_changes: str,
              model: Optional[str] = None) -> str:
    """Sends the git diff to Ollama for review, returns the review text."""
    prompt = textwrap.dedent("You are a senior software engineer. Review this open "\
                              f"pull request titled \"{pull.title}\". Point out "\
                              "potential bugs, style issues, and improvements. "\
                              "You do not need to summarize the changes. "\
                              "Include example code in your feedback.\n"\
                              f"{code_changes}")

    print("\n")
    print(f"Sending pull request {pull.title} to Ollama for review...")
    review = ollama_api.do_generation(prompt, model)
    print("\n--- Ollama Review ---")
    print(review)
    return review

def create_description_of_changes(
        file: GitHubChangedFile, changed_file_text: str
) -> str:
    """Creates a description of all changes in changed_files_dict."""
    return f"File name:\n{file.filename}\n"\
            f"The proposed code changes:\n{changed_file_text}\n"\

def do_review_with_full_file(pr: GitHubPr):
    """Collects diff and original file for review context"""
    changed_files = github_api.get_changed_files(pr)
    description_of_changes_list = []
    for changed_file in changed_files:
        changed_file_text = github_api.get_changed_file_whole_contents(changed_file)
        description_of_changes = create_description_of_changes(changed_file, changed_file_text)
        description_of_changes_list.append(description_of_changes)
    code_changes_prompt_text = "\n".join(description_of_changes_list)
    return do_review(pr, code_changes_prompt_text)

def get_requested_model(text: str) -> Optional[str]:
    """
    Return the word that immediately follows the first occurrence of
    "use" or "using" in *text*.
    """
    pattern = r'\b(use|using)\s+([a-zA-Z0-9\-\:\.]+)'
    match = re.search(pattern, text, flags=re.IGNORECASE)

    if match and len(match.groups()) == 2:
        return match.group(2)
    return None

def process_pull_requests(pulls: list[GitLabMergeRequest] | list[GitHubPr]):
    """Checks comments on pull requests and requests Ollama for code reviews"""
    api = get_api()
    for pr in pulls:
        is_github = isinstance(c, GitHubComment)
        comments = api.get_comments(pr)
        if comments:
            print("Comments:")
            review_requested = False
            latest_comment_text = ''
            for c in comments:
                comment_username = c.user.login if is_github else c.author.username
                comment_body = c.body
                print(f"- {comment_username}: {comment_body[:80]}")
                if git_username in comment_username:
                    review_requested = False
                elif f"@{git_username}" in comment_body:
                    review_requested = True
                    latest_comment_text = comment_body
            if review_requested:
                model = get_requested_model(latest_comment_text)
                print(f"Using model {model}")
                if model is not None:
                    if model not in allowed_models:
                        api.post_comment(pr, f"{model} is not an allowed model. "\
                                             "Please use on of the following models: "\
                                            f"{', '.join(allowed_models)}.")
                        continue
                diff = api.get_diff(pr)
                prompt_text = f"Git diff\n{diff}"
                review_content = do_review(pr, prompt_text, model)
                api.post_comment(pr, review_content)
            else:
                print(f"\nNot doing a review. No @{git_username} comment found " +
                      f"or the last comment was posted by {git_username}.")
        else:
            print("No GitHub comments.")

def get_pull_requests():
    """Gets all open pull/merge requests for the configured repositories"""
    api = get_api()
    if isinstance(api, GitLabApi):
        return api.get_open_mrs(gitlab_projects)
    if isinstance(api, GitHubApi):
        return api.get_open_prs(github_repos)
    raise Exception(f"Unsupported API: {api}")

# Pylint added because the loop just prints any error
# Then waits for longer than normal to loop again
#pylint: disable=bare-except
def main():
    """Reads in the config then runs the loop to check specified repos 
    for pull requests then post code reviews from Ollama"""
    try:
        read_config()
    except Exception as e:
        print("Error while trying to read in config:", e)
        return -1
    while True:
        try:
            print("Checking repositories for open PRs")
            open_prs = get_pull_requests()
            if open_prs is not None and len(open_prs) > 0:
                process_pull_requests(open_prs)
            print("Waiting one minute...")
            time.sleep(60)
        except Exception as e:
            print(f"ERROR {e}")
            # Wait 5 minutes
            time.sleep(60*5)

if __name__ == "__main__":
    main()
