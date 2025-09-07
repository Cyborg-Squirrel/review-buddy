"""An API class for interacting with Gitlab"""

# ------------------------------
# Rationale for disabled lints
# ------------------------------
# no-member: dataclasses_json functions such as schema() get this
# error, but the code compiles and runs.
#
#pylint: disable=no-member

from dataclasses import dataclass

import requests
from dataclasses_json import Undefined, dataclass_json


@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class GitLabMergeRequest:
    """Represents a GitLab Merge Request."""
    id: int
    project_id: int
    title: str
    web_url: str
    description: str
    source_branch: str
    target_branch: str

@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class GitLabAuthor:
    """The author of an object (comment, merge request, etc) in GitLab"""
    id: int
    name: str
    username: str

@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class GitLabNote:
    """Represents a note (comment) in a GitLab Merge Request."""
    id: int
    body: str
    author: GitLabAuthor


@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class GitLabCommit:
    """Represents a commit in a GitLab Merge Request."""
    id: str
    message: str


@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class GitLabChangedFile:
    """Represents a file that has been changed."""
    old_path: str
    new_path: str
    status: str
    diff: str


class GitLabApi:
    """
    GitLabApi

    Communicates with GitLab's APIs
    """

    def __init__(self, gitlab_url, private_token):
        self.gitlab_url = gitlab_url
        self.private_token = private_token
        self.headers = {
            'PRIVATE-TOKEN': self.private_token,
            'Content-Type': 'application/json'
        }

    def get_comments(self, mr: GitLabMergeRequest) -> list[GitLabNote]:
        """Gets all comments posted on a merge request"""
        url = f"{self.gitlab_url}/api/v5/projects/{mr.project_id}/merge_requests/{mr.id}/notes"
        response = requests.get(url, headers=self.headers, timeout=5)
        response.raise_for_status()
        return GitLabNote.schema().load(response.json(), many=True)
    
    def get_diff(self, mr: GitLabMergeRequest) -> str:
        """Gets the diff for the merge request in raw form (not json)"""
        url = f"{self.gitlab_url}/api/v5/projects/{mr.project_id}/merge_requests/{mr.id}.diff"
        response = requests.get(url, headers=self.headers, timeout=5)
        response.raise_for_status()
        return response

    def get_changed_files(self,mr: GitLabMergeRequest) -> list[GitLabChangedFile]:
        """Gets the files changed in the merge request"""
        url = f"{self.gitlab_url}/api/v5/projects/{mr.project_id}/merge_requests/{mr.id}/diffs"
        response = requests.get(url, headers=self.headers, timeout=5)
        response.raise_for_status()
        return GitLabChangedFile.schema().load(response.json(), many=True)

    def get_open_mrs(self, project_ids) -> list[GitLabMergeRequest]:
        """Retrieves all open merge requests for the specified projects"""
        mrs = list()
        for project_id in project_ids:
            url = f"{self.gitlab_url}/api/v5/projects/{project_id}/merge_requests?state=opened"
            response = requests.get(url, headers=self.headers, timeout=5)
            response.raise_for_status()
            mrs.extend(GitLabMergeRequest.schema().load(response.json(), many=True))
        return mrs

    def get_raw_file_contents(self, project_id, file_path, ref) -> str:
        """Gets the raw content of a file"""
        url = f"{self.gitlab_url}/api/v5/projects/{project_id}/repository/files/{file_path}"
        params = {"ref": ref}
        response = requests.get(url, headers=self.headers, params=params, timeout=5)
        response.raise_for_status()
        return response.text

    def post_comment(self, mr: GitLabMergeRequest, content: str):
        """Posts a comment to a merge request"""
        url = f"{self.gitlab_url}/api/v5/projects/{mr.project_id}/merge_requests/{mr.id}/notes"
        data = {"body": content}
        response = requests.post(url, headers=self.headers, json=data, timeout=5)
        response.raise_for_status()
