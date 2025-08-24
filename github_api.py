"""An API class for interacting with Github"""

import json
from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class GitHubUser:
    """A GitHub user retrieved from the API"""
    login: str

@dataclass
class GitHubRepo:
    """A single Git repo - contains the owner and the name of the repository"""
    name: str
    owner: GitHubUser

@dataclass
class GitHubApiConfig:
    """GitHubApi config - contains an auth token and repos in use"""
    repo_list: list[GitHubRepo]
    token: str

class GitHubComment:
    """GitHub pull request comment model.

    Attributes:
        json_data (dict): The raw JSON data from the GitHub API.
    """

    json_data: dict

    def __init__(self, json_data: dict):
        self.json_data = json_data

    def get_username(self) -> str:
        """Gets the username of the comment author"""
        return self.json_data['user']['login']

    def get_comment_body(self) -> str:
        """Gets the comment text content"""
        return self.json_data['body']

@dataclass
class GitHubPr:
    """GitHub pull request model"""
    url: str
    number: int
    title: str
    comments_url: str
    owner: GitHubUser
    repo: GitHubRepo

@dataclass
class GitHubChangedFile:
    """GitHub API list of changed files"""

    filename: str
    raw_url: str
    patch: str

class GitHubApi:
    """API for interacting with GitHub"""

    __API_BASE = "https://api.github.com"
    config: GitHubApiConfig

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

    def get_open_prs(self) -> list[GitHubPr]:
        """Checks the configured repositories for open pull requests"""
        print("Checking for open pull requests")
        open_prs = list[GitHubPr]()
        for repo in self.config.repo_list:
            open_prs_url = f"{self.__API_BASE}/repos/{repo.owner}/{repo.name}/pulls?state=open"
            open_prs_for_repo = self.__do_json_api_get(open_prs_url)
            if open_prs_for_repo is not None and len(open_prs_for_repo) > 0:
                for open_pr in open_prs_for_repo:
                    open_prs.append(GitHubPr(**json.loads(open_pr)))
        return open_prs

    def get_comments_for_pr(self, pr: GitHubPr) -> list[GitHubComment]:
        """Gets all comments posted on a specified pr"""
        print(f"\n=== PR #{pr.number}: {pr.title} ===")
        comments = self.__do_json_api_get(pr.comments_url)
        github_comments = list[GitHubComment]()
        for comment in comments:
            github_comments.append(GitHubComment(comment))
        return github_comments

    def get_pr_diff(self, pr) -> str:
        """Gets the diff for the pull request in raw form (not json)"""
        pr_url = pr["url"]
        diff_headers = self.__get_json_response_headers()
        diff_headers["Accept"] = "application/vnd.github.diff"
        return self.__do_json_api_request_raw_response(pr_url, diff_headers)

    def get_changed_files(self, pr: GitHubPr) -> list[GitHubChangedFile]:
        """Gets the files changed in the PR"""
        changed_files = list[GitHubChangedFile]()
        pr_files_url = f"""{self.__API_BASE}/repos/{pr.owner.login}/{pr.repo.name}
                            /pulls/{pr.number}/files"""
        pr_changed_files = self.__do_json_api_get(pr_files_url)
        for pr_changed_file in pr_changed_files:
            changed_files.append(GitHubChangedFile(**json.loads(pr_changed_file)))
        return changed_files

    def get_changed_file_whole_contents(self, file: GitHubChangedFile) -> str:
        """Gets the entire file contents"""
        raw_headers = self.__get_json_response_headers()
        raw_headers.pop("Accept")
        return self.__do_json_api_request_raw_response(file.raw_url, raw_headers)

    def post_comment(self, pr, content: str):
        """Posts a comment to the specified pull request"""
        comments_url = pr["comments_url"]
        self.__do_json_api_post(comments_url, {'body': content})
