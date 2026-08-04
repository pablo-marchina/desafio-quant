from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


@dataclass
class GitHubOrgProfile:
    org_name: str
    description: str = ""
    location: str = ""
    blog: str = ""
    email: str = ""
    public_repos: int = 0
    followers: int = 0
    avatar_url: str = ""
    html_url: str = ""


@dataclass
class GitHubRepo:
    name: str
    full_name: str
    description: str = ""
    url: str = ""
    stars: int = 0
    forks: int = 0
    language: str = ""
    topics: list[str] = field(default_factory=list)
    readme_text: str = ""


@dataclass
class GitHubUserProfile:
    login: str
    name: str = ""
    bio: str = ""
    location: str = ""
    blog: str = ""
    company: str = ""
    public_repos: int = 0
    followers: int = 0
    following: int = 0
    html_url: str = ""


class GitHubCollector:
    """Collect public GitHub profile and repository data.

    Requires ``GITHUB_TOKEN`` environment variable for authenticated requests
    (5,000 req/h rate limit). Without a token, only 60 req/h are allowed.
    """

    def __init__(self, token: str | None = None):
        self._token = token or os.environ.get("GITHUB_TOKEN", "")
        self._client = httpx.Client(
            base_url=GITHUB_API_BASE,
            headers=self._build_headers(),
            timeout=15,
            follow_redirects=True,
        )

    def _build_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "NVIDIA-Startup-AI-Radar/1.0"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def collect_organization(self, org_name: str) -> GitHubOrgProfile | None:
        """Collect GitHub organization profile."""
        try:
            resp = self._client.get(f"/orgs/{org_name}")
            resp.raise_for_status()
            data = resp.json()
            return GitHubOrgProfile(
                org_name=data.get("login", org_name),
                description=data.get("description") or "",
                location=data.get("location") or "",
                blog=data.get("blog") or "",
                email=data.get("email") or "",
                public_repos=data.get("public_repos", 0),
                followers=data.get("followers", 0),
                avatar_url=data.get("avatar_url", ""),
                html_url=data.get("html_url", ""),
            )
        except Exception as exc:
            logger.warning("Failed to collect GitHub org %s: %s", org_name, exc)
            return None

    def collect_user(self, username: str) -> GitHubUserProfile | None:
        """Collect public GitHub user profile."""
        try:
            resp = self._client.get(f"/users/{username}")
            resp.raise_for_status()
            data = resp.json()
            return GitHubUserProfile(
                login=data.get("login", username),
                name=data.get("name") or "",
                bio=data.get("bio") or "",
                location=data.get("location") or "",
                blog=data.get("blog") or "",
                company=data.get("company") or "",
                public_repos=data.get("public_repos", 0),
                followers=data.get("followers", 0),
                following=data.get("following", 0),
                html_url=data.get("html_url", ""),
            )
        except Exception as exc:
            logger.warning("Failed to collect GitHub user %s: %s", username, exc)
            return None

    def list_repos(self, org_or_user: str, *, max_repos: int = 10) -> list[GitHubRepo]:
        """List repositories for an organization or user, sorted by stars."""
        try:
            resp = self._client.get(
                f"/orgs/{org_or_user}/repos",
                params={"sort": "stars", "per_page": max_repos, "type": "public"},
            )
            if resp.status_code == 404:
                # Try user repos instead
                resp = self._client.get(
                    f"/users/{org_or_user}/repos",
                    params={"sort": "stars", "per_page": max_repos, "type": "public"},
                )
            resp.raise_for_status()
            repos_data = resp.json()
        except Exception as exc:
            logger.warning("Failed to list repos for %s: %s", org_or_user, exc)
            return []

        repos: list[GitHubRepo] = []
        for item in repos_data:
            repo = GitHubRepo(
                name=item.get("name", ""),
                full_name=item.get("full_name", ""),
                description=item.get("description") or "",
                url=item.get("html_url", ""),
                stars=item.get("stargazers_count", 0),
                forks=item.get("forks_count", 0),
                language=item.get("language") or "",
                topics=item.get("topics", []),
            )
            # Try to fetch README
            readme = self._fetch_readme(item.get("full_name", ""))
            if readme:
                repo.readme_text = readme
            repos.append(repo)

        return repos

    def _fetch_readme(self, full_name: str) -> str | None:
        """Fetch the repository README content (rendered as text).

        Returns ``None`` on error to distinguish from "no content".
        """
        try:
            resp = self._client.get(
                f"/repos/{full_name}/readme",
                headers={**self._build_headers(), "Accept": "application/vnd.github.v3.raw"},
            )
            if resp.status_code == 200:
                return resp.text[:50_000]  # cap at 50KB
        except Exception as exc:
            logger.warning("Failed to fetch README for %s: %s", full_name, exc)
        return None

    def close(self) -> None:
        self._client.close()
