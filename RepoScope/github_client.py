import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import parse_qs, quote, unquote, urlencode, urlsplit

import config


class GitHubError(Exception):
    pass


class InvalidSourceError(GitHubError):
    pass


class AuthError(GitHubError):
    pass


class NotFoundError(GitHubError):
    pass


class NetworkError(GitHubError):
    pass


class ApiError(GitHubError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class RateLimitError(GitHubError):
    def __init__(self, wait_seconds, message=None):
        super().__init__(message or f"GitHub rate limit reached. Retry in {wait_seconds} seconds.")
        self.wait_seconds = wait_seconds


@dataclass
class SourceSpec:
    kind: str  # "repo", "search" or "bulk"
    key: str  # identifies the source in the saved progress table
    title: str
    queries: list = field(default_factory=list)
    repo_path: str = ""


SUPPORTED_FORMATS_HELP = (
    "Supported inputs:\n"
    "  https://github.com/owner/repo            one repository\n"
    "  https://github.com/owner                 all public repositories of a user or organization\n"
    "  https://github.com/topics/python         repositories with a topic\n"
    "  https://github.com/search?q=language%3APython+stars%3A%3E1000&type=repositories\n"
    "  https://api.github.com/search/repositories?q=...   (a search API URL)\n"
    "A search or owner source returns at most 1000 repositories (a GitHub limit)."
)

ALLOWED_HOSTS = {"github.com", "www.github.com", "api.github.com"}
RESERVED_FIRST_SEGMENTS = {
    "search", "topics", "orgs", "settings", "marketplace", "features", "explore", "login",
    "sponsors", "pricing", "about", "notifications", "pulls", "issues", "new", "collections",
    "trending", "enterprise", "organizations", "apps", "codespaces", "stars",
}
NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


def _check_name(name, what):
    if not NAME_PATTERN.match(name):
        raise InvalidSourceError(f"'{name}' is not a valid GitHub {what} name.")


def _search_spec(query):
    query = query.strip()
    if not query:
        raise InvalidSourceError("The search URL has an empty query (q=).")
    return SourceSpec("search", f"search:{query}", f"Search: {query}", queries=[query])


def _repo_spec(owner, repo):
    repo = repo[:-4] if repo.endswith(".git") else repo
    _check_name(owner, "owner")
    _check_name(repo, "repository")
    return SourceSpec("repo", f"repo:{owner}/{repo}".lower(), f"Repository: {owner}/{repo}",
                      repo_path=f"{owner}/{repo}")


def parse_source_url(text):
    """Validate a URL typed by the user and describe what should be collected."""
    text = (text or "").strip()
    if not text:
        raise InvalidSourceError("Please enter a GitHub URL.")
    if "://" not in text:
        text = "https://" + text
    parts = urlsplit(text)
    if parts.scheme not in ("http", "https") or parts.netloc.lower() not in ALLOWED_HOSTS:
        raise InvalidSourceError("Only github.com and api.github.com URLs are supported.")
    segments = [unquote(segment) for segment in parts.path.split("/") if segment]
    query = parse_qs(parts.query)  # also turns '+' into a space and %3A into ':'

    if parts.netloc.lower() == "api.github.com":
        if segments == ["search", "repositories"] and query.get("q"):
            return _search_spec(query["q"][0])
        if len(segments) == 3 and segments[0] == "repos":
            return _repo_spec(segments[1], segments[2])
        raise InvalidSourceError("Supported API URLs: /search/repositories?q=... and /repos/owner/repo.")

    if not segments:
        raise InvalidSourceError("Please give a repository, user, topic or search URL, not just github.com.")
    if segments[0] == "search":
        kind = query.get("type", ["repositories"])[0]
        if kind != "repositories":
            raise InvalidSourceError("Only repository searches are supported (type=repositories).")
        if not query.get("q"):
            raise InvalidSourceError("The search URL has no q= parameter.")
        return _search_spec(query["q"][0])
    if segments[0] == "topics":
        if len(segments) < 2:
            raise InvalidSourceError("Topic URLs look like https://github.com/topics/python.")
        _check_name(segments[1], "topic")
        return _search_spec(f"topic:{segments[1]}")
    if segments[0] in RESERVED_FIRST_SEGMENTS:
        raise InvalidSourceError(f"'{segments[0]}' pages are not supported.")
    if len(segments) == 1:
        _check_name(segments[0], "owner")
        return _search_spec(f"user:{segments[0]}")
    return _repo_spec(segments[0], segments[1])


def build_bulk_plan():
    queries = []
    for star_range in config.BULK_STAR_RANGES:
        for language in config.BULK_LANGUAGES:
            queries.append(f'language:"{language}" stars:{star_range}')
    return SourceSpec("bulk", "bulk", "Automatic large dataset plan", queries=queries)


def default_token():
    return os.environ.get(config.TOKEN_ENVIRONMENT_VARIABLE, "").strip()


class GitHubClient:
    def __init__(self, token=None):
        self._token = (token or "").strip() or None
        self.rate_limit = None
        self.rate_remaining = None
        self.rate_reset = None

    @property
    def has_token(self):
        return self._token is not None

    def seconds_until_reset(self):
        if self.rate_reset is None:
            return 0
        return max(0, int(self.rate_reset - time.time()))

    def _remember_rate_limit(self, headers):
        try:
            self.rate_limit = int(headers.get("X-RateLimit-Limit"))
            self.rate_remaining = int(headers.get("X-RateLimit-Remaining"))
            self.rate_reset = int(headers.get("X-RateLimit-Reset"))
        except (TypeError, ValueError):
            pass

    def _error_message(self, error):
        try:
            return json.loads(error.read().decode("utf-8")).get("message", "")
        except (ValueError, OSError, AttributeError):
            return ""

    def _translate_http_error(self, error):
        message = self._error_message(error)
        code = error.code
        if code == 401:
            return AuthError("GitHub rejected the token (401). Check that it is correct and not expired.")
        if code in (403, 429):
            retry_after = error.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                return RateLimitError(int(retry_after) + 1)
            if error.headers.get("X-RateLimit-Remaining") == "0":
                return RateLimitError(self.seconds_until_reset() + 1)
            if "rate limit" in message.lower():
                return RateLimitError(60, "GitHub asked us to slow down (secondary rate limit).")
            return AuthError(f"GitHub refused the request (403): {message or 'access forbidden'}")
        if code == 404:
            return NotFoundError("GitHub could not find that repository or user (404).")
        return ApiError(f"GitHub returned HTTP {code}: {message}", status=code)

    def _request(self, path, params=None):
        url = config.API_BASE_URL + path
        if params:
            url += "?" + urlencode(params)
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": config.USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        last_problem = ""
        for attempt in range(1, config.MAX_REQUEST_RETRIES + 1):
            try:
                request = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(request, timeout=config.REQUEST_TIMEOUT_SECONDS) as response:
                    self._remember_rate_limit(response.headers)
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as error:  # must come before URLError
                self._remember_rate_limit(error.headers)
                if error.code < 500:
                    raise self._translate_http_error(error)
                last_problem = f"GitHub server error {error.code}"
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
                last_problem = str(getattr(error, "reason", error))
            except ValueError:
                raise ApiError("GitHub sent a response that is not valid JSON.")
            time.sleep(2 ** attempt)
        raise NetworkError(f"Network problem after {config.MAX_REQUEST_RETRIES} attempts: {last_problem}")

    def search_repositories(self, query, page):
        data = self._request("/search/repositories", {
            "q": query, "sort": "stars", "order": "desc",
            "per_page": config.RESULTS_PER_PAGE, "page": page,
        })
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise ApiError("Unexpected response from the GitHub search API.")
        return data

    def get_repository(self, full_name):
        owner, repo = full_name.split("/", 1)
        data = self._request(f"/repos/{quote(owner)}/{quote(repo)}")
        if not isinstance(data, dict):
            raise ApiError("Unexpected response from the GitHub repository API.")
        return data
