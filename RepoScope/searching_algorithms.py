import time

from filtering import FilterError, evaluate_operator, parse_query_value
from models import COLUMN_KIND, comparable_value

BINARY_OPERATORS = ("equals", "starts_with", "greater_than", "less_than", "date_before", "date_after")


class SearchError(ValueError):
    pass


class NotSortedError(SearchError):
    pass


class SearchResult:
    def __init__(self, method, matches, comparisons, time_ms, setup_ms=0.0, note=""):
        self.method = method
        self.matches = matches
        self.comparisons = comparisons
        self.time_ms = time_ms
        self.setup_ms = setup_ms
        self.note = note


def _prepare(column, operator, text):
    if column not in COLUMN_KIND:
        raise SearchError(f"Unknown column: {column}")
    try:
        return COLUMN_KIND[column], parse_query_value(COLUMN_KIND[column], operator, text)
    except FilterError as error:
        raise SearchError(str(error))


def linear_search(records, column, operator, text):
    """Checks every record from the first to the last. Works on unsorted data and for every operator."""
    kind, query = _prepare(column, operator, text)
    started = time.perf_counter()
    matches = []
    comparisons = 0
    for record in records:
        comparisons += 1
        if evaluate_operator(comparable_value(record, column), operator, query):
            matches.append(record)
    return SearchResult("Linear search", matches, comparisons, (time.perf_counter() - started) * 1000)


def is_sorted_ascending(records, column):
    """True if records are in ascending order of this column, with missing values last.

    This is exactly the order produced by sorting this column ascending in RepoScope.
    """
    previous = None
    seen_missing = False
    for record in records:
        value = comparable_value(record, column)
        if value is None:
            seen_missing = True
        elif seen_missing or (previous is not None and value < previous):
            return False
        else:
            previous = value
    return True


def _lower_bound(records, column, query, counter):
    """First index whose value is >= query. Missing values count as larger than everything."""
    low, high = 0, len(records)
    while low < high:
        middle = (low + high) // 2
        counter[0] += 1
        value = comparable_value(records[middle], column)
        if value is not None and value < query:
            low = middle + 1
        else:
            high = middle
    return low


def _upper_bound(records, column, query, counter):
    """First index whose value is > query."""
    low, high = 0, len(records)
    while low < high:
        middle = (low + high) // 2
        counter[0] += 1
        value = comparable_value(records[middle], column)
        if value is not None and value <= query:
            low = middle + 1
        else:
            high = middle
    return low


def _first_missing(records, column, counter):
    low, high = 0, len(records)
    while low < high:
        middle = (low + high) // 2
        counter[0] += 1
        if comparable_value(records[middle], column) is None:
            high = middle
        else:
            low = middle + 1
    return low


def binary_search(records, column, operator, text):
    """Finds all matches in O(log n) steps, but only if records are sorted ascending by this column."""
    kind, query = _prepare(column, operator, text)
    if operator not in BINARY_OPERATORS:
        raise SearchError("Binary search can only find ranges of sorted values. "
                          "'contains', 'ends with' and 'missing' tests need a linear scan.")
    if not is_sorted_ascending(records, column):
        raise NotSortedError(f"Binary search needs the records sorted ascending by '{column}'. They are not.")

    counter = [0]
    started = time.perf_counter()
    if operator == "equals":
        start, end = _lower_bound(records, column, query, counter), _upper_bound(records, column, query, counter)
    elif operator == "starts_with":
        # Every text starting with the prefix lies between the prefix and prefix + the largest character.
        start = _lower_bound(records, column, query, counter)
        end = _lower_bound(records, column, query + "\U0010ffff", counter)
    elif operator in ("greater_than", "date_after"):
        start, end = _upper_bound(records, column, query, counter), _first_missing(records, column, counter)
    else:
        start, end = 0, _lower_bound(records, column, query, counter)
    matches = records[start:end] if start < end else []
    return SearchResult("Binary search", matches, counter[0], (time.perf_counter() - started) * 1000)


def hash_search(records, column, operator, text):
    """Exact-match lookup in a dictionary (hash table). Building the index is a one-time O(n) cost."""
    kind, query = _prepare(column, operator, text)
    if operator != "equals":
        raise SearchError("A hash index can only answer exact-match ('equals') questions.")
    started = time.perf_counter()
    index = {}
    for record in records:
        value = comparable_value(record, column)
        if value is not None:
            index.setdefault(value, []).append(record)
    built = time.perf_counter()
    matches = list(index.get(query, []))
    finished = time.perf_counter()
    return SearchResult("Hash index lookup", matches, 1, (finished - built) * 1000,
                        setup_ms=(built - started) * 1000, note="1 lookup after building the index")
