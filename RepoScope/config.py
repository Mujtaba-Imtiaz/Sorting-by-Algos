from pathlib import Path

APP_NAME = "RepoScope"

PROJECT_DIR = Path(__file__).resolve().parent
DATABASE_PATH = PROJECT_DIR / "data" / "reposcope.db"

API_BASE_URL = "https://api.github.com"
USER_AGENT = "RepoScope-CS200-Project"
TOKEN_ENVIRONMENT_VARIABLE = "GITHUB_TOKEN"

REQUEST_TIMEOUT_SECONDS = 20
MAX_REQUEST_RETRIES = 3
RESULTS_PER_PAGE = 100
# GitHub search never returns more than the first 1000 results of one query.
MAX_SEARCH_RESULTS = 1000
MAX_SEARCH_PAGES = MAX_SEARCH_RESULTS // RESULTS_PER_PAGE
DEFAULT_TARGET_RECORDS = 15000

# The automatic plan combines every language with every star range.
# Each combination is one search query that can return up to 1000 repositories.
BULK_LANGUAGES = [
    "Python", "JavaScript", "TypeScript", "Java", "Go", "Rust", "C++", "C",
    "C#", "PHP", "Ruby", "Swift", "Kotlin", "Shell", "HTML", "Dart",
    "Jupyter Notebook", "Scala", "Lua", "Vue",
]
BULK_STAR_RANGES = [
    ">=20000", "10000..19999", "5000..9999", "3000..4999",
    "2000..2999", "1000..1999", "500..999",
]

SORT_WARNING_SIZE = 3000
BENCHMARK_SEED = 42
