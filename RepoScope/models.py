from datetime import date, datetime, timezone
from typing import NamedTuple


class Column(NamedTuple):
    key: str
    label: str
    kind: str  # "int", "text", "date" or "bool"


COLUMNS = [
    Column("id", "ID", "int"),
    Column("name", "Name", "text"),
    Column("full_name", "Full name", "text"),
    Column("owner", "Owner", "text"),
    Column("description", "Description", "text"),
    Column("language", "Language", "text"),
    Column("stars", "Stars", "int"),
    Column("forks", "Forks", "int"),
    Column("open_issues", "Open issues", "int"),
    Column("created_at", "Created", "date"),
    Column("updated_at", "Last updated", "date"),
    Column("license_name", "License", "text"),
    Column("default_branch", "Default branch", "text"),
    Column("html_url", "URL", "text"),
    Column("archived", "Archived", "bool"),
    Column("visibility", "Visibility", "text"),
    Column("collected_at", "Collected at", "date"),
]

COLUMN_KEYS = [column.key for column in COLUMNS]
COLUMN_BY_KEY = {column.key: column for column in COLUMNS}
COLUMN_KIND = {column.key: column.kind for column in COLUMNS}


def clean_text(value):
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def to_int(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_repository(item):
    """Turn one GitHub API repository object into a flat record, or None if unusable."""
    if not isinstance(item, dict):
        return None
    repo_id = to_int(item.get("id"))
    full_name = clean_text(item.get("full_name"))
    if repo_id is None or full_name is None:
        return None

    owner = item.get("owner") if isinstance(item.get("owner"), dict) else {}
    license_info = item.get("license") if isinstance(item.get("license"), dict) else {}
    archived = item.get("archived")
    visibility = clean_text(item.get("visibility"))
    if visibility is None and item.get("private") is not None:
        visibility = "private" if item.get("private") else "public"

    return {
        "id": repo_id,
        "name": clean_text(item.get("name")) or full_name.split("/")[-1],
        "full_name": full_name,
        "owner": clean_text(owner.get("login")) or full_name.split("/")[0],
        "description": clean_text(item.get("description")),
        "language": clean_text(item.get("language")),
        "stars": to_int(item.get("stargazers_count")),
        "forks": to_int(item.get("forks_count")),
        "open_issues": to_int(item.get("open_issues_count")),
        "created_at": clean_text(item.get("created_at")),
        "updated_at": clean_text(item.get("updated_at")),
        "license_name": clean_text(license_info.get("name")),
        "default_branch": clean_text(item.get("default_branch")),
        "html_url": clean_text(item.get("html_url")),
        "archived": None if archived is None else int(bool(archived)),
        "visibility": visibility,
        "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def date_to_ordinal(text):
    """Convert '2021-05-30' or '2021-05-30T10:00:00Z' to a whole number of days."""
    try:
        return date.fromisoformat(str(text).strip()[:10]).toordinal()
    except ValueError:
        return None


def comparable_value(record, column_key):
    """The one place that decides how a field is compared.

    Text becomes lowercase, numbers stay numbers, dates become day numbers and
    a missing value becomes None. Sorting, searching and filtering all use this,
    so they always agree with each other.
    """
    value = record.get(column_key)
    if value is None:
        return None
    kind = COLUMN_KIND[column_key]
    if kind == "text":
        return str(value).strip().casefold() or None
    if kind == "int":
        return to_int(value)
    if kind == "bool":
        return 1 if value in (1, True, "1", "true", "True") else 0
    return date_to_ordinal(value)
