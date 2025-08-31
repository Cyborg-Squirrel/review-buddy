"""An API class for interacting with Github"""

# ------------------------------
# Rationale for disabled lints
# ------------------------------
# no-member: dataclasses_json functions such as schema() get this
# error, but the code compiles and runs.
#
#pylint: disable=no-member
import json
from dataclasses import dataclass
from typing import Optional

import requests
from dataclasses_json import Undefined, dataclass_json


@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class GitHubUser:
    """A GitHub user retrieved from the API"""
    login: str

@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class GitHubRepo:
    """A Git repo - contains the owner and the name of the repository"""
    name: str
    html_url: str
    owner: GitHubUser

@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class GitHubRef:
    """A Git ref - contains information about a ref"""
    repo: GitHubRepo
    ref: str
    sha: str

@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class GitHubComment:
    """GitHub pull request comment model"""
    user: GitHubUser
    body: str

@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class GitHubPr:
    """GitHub pull request model"""
    url: str
    number: int
    title: str
    comments_url: str
    # The latest branch commit ref
    head: GitHubRef
    # The pull request target branch ref
    base: GitHubRef

@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class GitHubChangedFile:
    """GitHub API list of changed files"""
    filename: str
    raw_url: str
    patch: str
    previous_filename: Optional[str] = None

@dataclass
class GitHubApiConfig:
    """GitHubApi config - contains an auth token and repos in use"""
    repo_list: list[GitHubRepo]
    token: str

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

    def __paginated_response_has_more_pages(self, headers) -> bool:
        """Checks if the GitHub API response indicates there are more pages"""
        link_header_present = 'Link' in headers.keys()
        if link_header_present:
            return '; rel="next"' in headers.get('Link')
        return False

    def __do_post(self, url, request):
        """POSTs a Github api request, returns the response json"""
        req = json.dumps(request)
        print(f"Request: {req}")
        r = requests.post(url, headers=self.__get_json_response_headers(), timeout=5, data=req)
        r.raise_for_status()
        return r.json()

    def __do_json_api_get(self, url) -> requests.Response:
        """Does a Github api request, returns the response json"""
        r = requests.get(url, headers=self.__get_json_response_headers(), timeout=5)
        r.raise_for_status()
        return r

    def __do_json_api_request_raw_response(self, url, headers):
        """Does a Github api request, returns the raw text"""
        r = requests.get(url, headers=headers, timeout=5)
        r.raise_for_status()
        return r.text

    def __do_paginated_request(self, url: str, page_param: str) -> list:
        response_list = []
        has_pages_remaining = True
        page = 0
        while has_pages_remaining:
            page = page + 1
            paginated_url = f"{url}{page_param}{page}"
            response = self.__do_json_api_get(paginated_url)
            has_pages_remaining = self.__paginated_response_has_more_pages(response.headers)
            response_list.extend(response.json())
        return response_list

    def get_open_prs(self) -> list[GitHubPr]:
        """Checks the configured repositories for open pull requests"""
        print("Checking for open pull requests")
        pr_list = []
        for repo in self.config.repo_list:
            open_prs_url = f"{self.__API_BASE}/repos/{repo.owner}/{repo.name}/pulls?state=open"
            json_list = self.__do_paginated_request(open_prs_url, '&page=')
            for json_obj in json_list:
                if json_obj is list:
                    pr_list.extend(GitHubPr.schema().load(json_obj, many=True))
                else:
                    pr_list.append(GitHubPr.schema().load(json_obj))
        return pr_list

    def get_comments_for_pr(self, pr: GitHubPr) -> list[GitHubComment]:
        """Gets all comments posted on a specified pr"""
        comments = []
        json_list = self.__do_paginated_request(pr.comments_url, '?page=')
        for json_obj in json_list:
            if json_obj is list:
                comments.extend(GitHubComment.schema().load(json_obj, many=True))
            else:
                comments.append(GitHubComment.schema().load(json_obj))
        return comments

    def get_pr_diff(self, pr: GitHubPr) -> str:
        """Gets the diff for the pull request in raw form (not json)"""
        diff_headers = self.__get_json_response_headers()
        diff_headers["Accept"] = "application/vnd.github.diff"
        return self.__do_json_api_request_raw_response(pr.url, diff_headers)

    def get_changed_files(self, pr: GitHubPr) -> list[GitHubChangedFile]:
        """Gets the files changed in the PR"""
        repo = pr.head.repo
        pr_files_url = f"{self.__API_BASE}/repos/{repo.owner.login}/{repo.name}"\
            f"/pulls/{pr.number}/files"
        files = []
        json_list = self.__do_paginated_request(pr_files_url, '?page=')
        for json_obj in json_list:
            if json_obj is list:
                files.extend(GitHubChangedFile.schema().load(json_obj, many=True))
            else:
                files.append(GitHubChangedFile.schema().load(json_obj))
        return files

    def get_changed_file_whole_contents(self, file: GitHubChangedFile) -> str:
        """Gets the entire file contents"""
        raw_headers = self.__get_json_response_headers()
        raw_headers.pop("Accept")
        return self.__do_json_api_request_raw_response(file.raw_url, raw_headers)

    def get_upstream_file_whole_contents(self, pr: GitHubPr, file: GitHubChangedFile) -> str:
        """Gets the entire file contents of the file from the source branch"""
        filename = file.filename if file.previous_filename is None else file.previous_filename
        request_url = f"{pr.base.repo.html_url}/raw/{pr.base.ref}/{filename}"
        raw_headers = self.__get_json_response_headers()
        raw_headers.pop("Accept")
        return self.__do_json_api_request_raw_response(request_url, raw_headers)

    def post_comment(self, pr: GitHubPr, content: str):
        """Posts a comment to the specified pull request"""
        comments_url = pr.comments_url
        self.__do_post(comments_url, {'body': content})
