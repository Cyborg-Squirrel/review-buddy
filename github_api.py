"""An API class for interacting with Github"""

# ------------------------------
# Rationale for disabled lints
# ------------------------------
# too-few-public-methods: PyLint flags model type classes with less than
# two public functions. This seems like a bad idea for a linter rule.
#pylint: disable=too-few-public-methods

import json
from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class GitHubRepo:
    """A single Git repo - contains the owner and the name of the repository"""
    name: str
    owner: str

@dataclass
class GitHubConfig:
    """GithubApi config - contains an auth token and repos in use"""
    repo_list: list[GitHubRepo]
    token: str

class GitHubApi:
    """API for interacting with GitHub"""

    __API_BASE = "https://api.github.com"
    config: GitHubConfig

    def __init__(self, config):
        self.config = config

    def __get_json_response_headers(self):
        """Returns a dict of the default Github api headers"""
        return {
            "Authorization": f"Bearer {self.config.token}",
            "Accept": "application/vnd.github.raw+json",
            "X-GitHub-Api-Version": "2022-11-28"
            }

    def __do_json_api_post(self, url, request):
        """POSTs a Github api request, returns the response json"""
        req = json.dumps(request)
        print(f"Request: {req}")
        r = requests.post(url, headers=self.__get_json_response_headers(), timeout=5, data=req)
        r.raise_for_status()
        return r.json()

    def __do_json_api_get(self, url) -> Any:
        """Does a Github api request, returns the response json"""
        r = requests.get(url, headers=self.__get_json_response_headers(), timeout=5)
        r.raise_for_status()
        return r.json()

    def __do_json_api_request_raw_response(self, url, headers):
        """Does a Github api request, returns the raw text"""
        r = requests.get(url, headers=headers, timeout=5)
        r.raise_for_status()
        return r.text

    def get_open_prs(self):
        """Checks the configured repositories for open pull requests"""
        print("Checking for open pull requests")
        open_prs = list()
        for repo in self.config.repo_list:
            open_prs_url = f"{self.__API_BASE}/repos/{repo.owner}/{repo.name}/pulls?state=open"
            open_prs_for_repo = self.__do_json_api_get(open_prs_url)
            if open_prs_for_repo is not None and len(open_prs_for_repo) > 0:
                for pr_for_repo in open_prs_for_repo:
                    open_prs.append(pr_for_repo)
        return open_prs

    def get_comments_for_pr(self, pr):
        """Gets all comments posted on a specified pr"""
        pr_number = pr["number"]
        pr_title = pr["title"]
        comments_url = pr["comments_url"]
        print(f"\n=== PR #{pr_number}: {pr_title} ===")
        return self.__do_json_api_get(comments_url)

    def get_pr_diff(self, pr):
        """Gets the diff for the pull request in raw form (not json)"""
        pr_url = pr["url"]
        diff_headers = self.__get_json_response_headers()
        diff_headers["Accept"] = "application/vnd.github.diff"
        return self.__do_json_api_request_raw_response(pr_url, diff_headers)

    def post_comment(self, pr, content: str):
        """Posts a comment to the specified pull request"""
        comments_url = pr["comments_url"]
        self.__do_json_api_post(comments_url, {'body': content})
