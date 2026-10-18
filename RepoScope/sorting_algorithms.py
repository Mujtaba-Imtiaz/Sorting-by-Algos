"""Eleven sorting algorithms that sort real repository records and count their own work.

Definitions used everywhere in RepoScope:
  comparison  one call that compares two records by the sort key(s).
  swap        two items in the same list exchange places (counted once, not as writes).
  movement    one item written into a list position outside a swap
              (an insertion-sort shift, a merge-sort output write, a counting-sort placement).
Equal keys keep their original order in stable algorithms, in ascending and descending mode.
"""
import random
import time
from typing import Callable, NamedTuple

from models import COLUMN_KIND, comparable_value

MAX_COUNTING_RANGE = 1_000_000
BOGO_MAX_RECORDS = 8  # bogo sort needs about n! shuffles, so anything bigger would never finish


class SortCancelled(Exception):
    pass


class SortNotSupported(ValueError):
    pass


class SortMetrics:
    def __init__(self, stop_event=None):
        self.comparisons = 0
        self.swaps = 0
        self.movements = 0
        self.stop_event = stop_event

    def check_stop(self):
        if self.stop_event is not None and self.stop_event.is_set():
            raise SortCancelled()


class SortSpec:
    """Describes how to order records: a list of (column_key, descending) levels."""

    def __init__(self, levels):
        if not levels:
            raise ValueError("Choose at least one column to sort by.")
        for column_key, _ in levels:
            if column_key not in COLUMN_KIND:
                raise ValueError(f"Unknown column: {column_key}")
        self.levels = [(column_key, bool(descending)) for column_key, descending in levels]

    def make_key(self, record):
        keys = []
        for column_key, _ in self.levels:
            value = comparable_value(record, column_key)
            keys.append((value is None, 0 if value is None else value))
        return tuple(keys)

    def make_entry(self, record):
        return (self.make_key(record), record)

    def compare(self, first, second):
        """Returns -1 if first belongs before second, 1 if after, 0 if the keys tie.

        Missing values always go last. Later levels are only looked at when all earlier levels tie.
        """
        for level, (_, descending) in enumerate(self.levels):
            first_missing, first_value = first[0][level]
            second_missing, second_value = second[0][level]
            if first_missing or second_missing:
                if first_missing and second_missing:
                    continue
                return 1 if first_missing else -1
            if first_value != second_value:
                order = -1 if first_value < second_value else 1
                return -order if descending else order
        return 0


def bubble_sort(items, spec, metrics):
    compare = spec.compare
    for end in range(len(items) - 1, 0, -1):
        metrics.check_stop()
        swapped = False
        for j in range(end):
            metrics.comparisons += 1
            # Strictly "<" so equal items are never swapped that is what keeps it stable.
            if compare(items[j + 1], items[j]) < 0:
                items[j], items[j + 1] = items[j + 1], items[j]
                metrics.swaps += 1
                swapped = True
        if not swapped:
            break
    return items


def selection_sort(items, spec, metrics):
    compare = spec.compare
    for start in range(len(items) - 1):
        metrics.check_stop()
        first_in_order = start
        for j in range(start + 1, len(items)):
            metrics.comparisons += 1
            if compare(items[j], items[first_in_order]) < 0:
                first_in_order = j
        if first_in_order != start:
            # This long distance swap can jump over equal items, so selection sort is not stable.
            items[start], items[first_in_order] = items[first_in_order], items[start]
            metrics.swaps += 1
    return items


def insertion_sort(items, spec, metrics):
    compare = spec.compare
    for i in range(1, len(items)):
        metrics.check_stop()
        current = items[i]
        j = i - 1
        while j >= 0:
            metrics.comparisons += 1
            if compare(current, items[j]) < 0:
                items[j + 1] = items[j]
                metrics.movements += 1
                j -= 1
            else:
                break
        if j + 1 != i:
            items[j + 1] = current
            metrics.movements += 1
    return items


def merge_sort(items, spec, metrics):
    if len(items) <= 1:
        return items
    metrics.check_stop()
    compare = spec.compare
    middle = len(items) // 2
    left = merge_sort(items[:middle], spec, metrics)
    right = merge_sort(items[middle:], spec, metrics)

    merged = []
    i = j = 0
    while i < len(left) and j < len(right):
        metrics.comparisons += 1
        # Take from the right only if it is strictly smaller on a tie the left (earlier) item wins.
        if compare(right[j], left[i]) < 0:
            merged.append(right[j])
            j += 1
        else:
            merged.append(left[i])
            i += 1
        metrics.movements += 1
    leftover = left[i:] if i < len(left) else right[j:]
    merged.extend(leftover)
    metrics.movements += len(leftover)
    return merged


def quick_sort(items, spec, metrics):
    _quick_sort_range(items, 0, len(items) - 1, spec.compare, metrics)
    return items


def _quick_sort_range(items, low, high, compare, metrics):
    while low < high:
        metrics.check_stop()
        pivot = items[(low + high) // 2]
        # Three-way partition: [low, less_end) < pivot, [less_end, greater_start] == pivot, rest > pivot.
        # Grouping equal keys together keeps quick sort fast when many repositories share a value.
        less_end, scan, greater_start = low, low, high
        while scan <= greater_start:
            metrics.comparisons += 1
            order = compare(items[scan], pivot)
            if order < 0:
                if less_end != scan:
                    items[less_end], items[scan] = items[scan], items[less_end]
                    metrics.swaps += 1
                less_end += 1
                scan += 1
            elif order > 0:
                if scan != greater_start:
                    items[scan], items[greater_start] = items[greater_start], items[scan]
                    metrics.swaps += 1
                greater_start -= 1
            else:
                scan += 1
        # Recurse into the smaller side and loop on the larger one, so the stack stays O(log n) deep.
        if less_end - low < high - greater_start:
            _quick_sort_range(items, low, less_end - 1, compare, metrics)
            low = greater_start + 1
        else:
            _quick_sort_range(items, greater_start + 1, high, compare, metrics)
            high = less_end - 1


def counting_sort(items, spec, metrics):
    # For several levels, sort by the last level first and the first level last.
    # Each pass is stable, so earlier levels end up as the main order.
    for level in range(len(spec.levels) - 1, -1, -1):
        metrics.check_stop()
        items = _counting_pass(items, level, spec.levels[level][1], metrics)
    return items


def _counting_pass(items, level, descending, metrics):
    present = [entry[0][level][1] for entry in items if not entry[0][level][0]]
    if not present:
        return items
    low, high = min(present), max(present)
    size = high - low + 1
    if size > MAX_COUNTING_RANGE:
        raise SortNotSupported(f"Counting sort needs a key range of at most {MAX_COUNTING_RANGE:,}; this one is {size:,}.")

    def bucket_of(entry):
        missing, value = entry[0][level]
        if missing:
            return size  # the last bucket holds missing values
        return high - value if descending else value - low

    counts = [0] * (size + 1)
    for entry in items:
        counts[bucket_of(entry)] += 1
    start = 0
    for bucket in range(size + 1):  # turn counts into starting positions
        counts[bucket], start = start, start + counts[bucket]
    output = [None] * len(items)
    for entry in items:  # going left to right keeps equal keys in their original order
        bucket = bucket_of(entry)
        output[counts[bucket]] = entry
        counts[bucket] += 1
        metrics.movements += 1
    return output


def heap_sort(items, spec, metrics):
    compare = spec.compare
    size = len(items)
    for root in range(size // 2 - 1, -1, -1):
        metrics.check_stop()
        _sift_down(items, root, size, compare, metrics)
    for end in range(size - 1, 0, -1):
        metrics.check_stop()
        items[0], items[end] = items[end], items[0]
        metrics.swaps += 1
        _sift_down(items, 0, end, compare, metrics)
    return items


def _sift_down(items, root, size, compare, metrics):
    while True:
        last_in_order = root
        left = 2 * root + 1
        right = left + 1
        if left < size:
            metrics.comparisons += 1
            if compare(items[left], items[last_in_order]) > 0:
                last_in_order = left
        if right < size:
            metrics.comparisons += 1
            if compare(items[right], items[last_in_order]) > 0:
                last_in_order = right
        if last_in_order == root:
            return
        items[root], items[last_in_order] = items[last_in_order], items[root]
        metrics.swaps += 1
        root = last_in_order


def shell_sort(items, spec, metrics):
    compare = spec.compare
    size = len(items)
    gap = 1
    while gap < size // 3:
        gap = 3 * gap + 1  # gaps 1, 4, 13, 40, ...
    while gap >= 1:
        metrics.check_stop()
        for i in range(gap, size):
            current = items[i]
            j = i
            while j >= gap:
                metrics.comparisons += 1
                if compare(current, items[j - gap]) < 0:
                    items[j] = items[j - gap]
                    metrics.movements += 1
                    j -= gap
                else:
                    break
            if j != i:
                items[j] = current
                metrics.movements += 1
        gap //= 3
    return items


def _split_and_number(items, level, descending):
    """Shared by radix and bucket sort

    Returns (pairs, missing).... Each pair is (number, entry) where number is a whole number that is 0 or bigger:
    the smallest key becomes 0 (or the biggest key becomes 0 for descending order) entries with a missing
    value are returned separately because they always go last.
    """
    present = [entry for entry in items if not entry[0][level][0]]
    missing = [entry for entry in items if entry[0][level][0]]
    values = [entry[0][level][1] for entry in present]
    if not values:
        return [], missing
    low, high = min(values), max(values)
    pairs = [((high - value) if descending else (value - low), entry) for value, entry in zip(values, present)]
    return pairs, missing


def radix_sort(items, spec, metrics):
    # Like counting sort, several levels are handled one after another, last level first.
    for level in range(len(spec.levels) - 1, -1, -1):
        metrics.check_stop()
        items = _radix_pass(items, level, spec.levels[level][1], metrics)
    return items


def _radix_pass(items, level, descending, metrics):
    pairs, missing = _split_and_number(items, level, descending)
    if not pairs:
        return items
    largest = max(number for number, _ in pairs)
    place = 1  # 1 = ones digit, 10 = tens digit, 100 = hundreds digit, ...
    while largest // place > 0:
        metrics.check_stop()
        buckets = [[] for _ in range(10)]  # one bucket for each digit 0 to 9
        for number, entry in pairs:  # visited in order, so equal digits keep their order (stable)
            buckets[(number // place) % 10].append((number, entry))
            metrics.movements += 1
        pairs = [pair for bucket in buckets for pair in bucket]
        place *= 10
    return [entry for _, entry in pairs] + missing


def bucket_sort(items, spec, metrics):
    for level in range(len(spec.levels) - 1, -1, -1):
        metrics.check_stop()
        items = _bucket_pass(items, level, spec.levels[level][1], metrics)
    return items


def _bucket_pass(items, level, descending, metrics):
    pairs, missing = _split_and_number(items, level, descending)
    if not pairs:
        return items
    largest = max(number for number, _ in pairs)
    bucket_count = len(pairs)  # as many buckets as records
    buckets = [[] for _ in range(bucket_count)]
    for number, entry in pairs:
        # Small numbers land in the first buckets and big numbers in the last ones, always in order.
        buckets[number * bucket_count // (largest + 1)].append((number, entry))
        metrics.movements += 1
    sorted_pairs = []
    for bucket in buckets:
        _sort_one_bucket(bucket, metrics)
        sorted_pairs.extend(bucket)
    return [entry for _, entry in sorted_pairs] + missing


def _sort_one_bucket(bucket, metrics):
    """Insertion sort on one small bucket. A comparison here compares two keys of the current level."""
    for i in range(1, len(bucket)):
        metrics.check_stop()
        current = bucket[i]
        j = i - 1
        while j >= 0:
            metrics.comparisons += 1
            if current[0] < bucket[j][0]:  # strictly smaller, so equal keys keep their order (stable)
                bucket[j + 1] = bucket[j]
                metrics.movements += 1
                j -= 1
            else:
                break
        if j + 1 != i:
            bucket[j + 1] = current
            metrics.movements += 1


def bogo_sort(items, spec, metrics):
    compare = spec.compare
    generator = random.Random(42)  # fixed seed so a run can be repeated
    while not _is_in_order(items, compare, metrics):
        metrics.check_stop()
        for i in range(len(items) - 1, 0, -1):  # shuffle: swap each item with a random earlier one
            j = generator.randint(0, i)
            if j != i:
                items[i], items[j] = items[j], items[i]
                metrics.swaps += 1
    return items


def _is_in_order(items, compare, metrics):
    for i in range(len(items) - 1):
        metrics.comparisons += 1
        if compare(items[i + 1], items[i]) < 0:
            return False
    return True


class AlgorithmInfo(NamedTuple):
    function: Callable
    best: str
    average: str
    worst: str
    space: str
    stable: bool
    quadratic: bool
    taught_in_class: bool
    description: str


ALGORITHMS = {
    "Bubble Sort": AlgorithmInfo(
        bubble_sort, "O(n)", "O(n²)", "O(n²)", "O(1)", True, True, True,
        "Repeatedly swaps neighbouring records that are out of order. Stops early if a pass makes no swap."),
    "Selection Sort": AlgorithmInfo(
        selection_sort, "O(n²)", "O(n²)", "O(n²)", "O(1)", False, True, True,
        "Finds the first record in order and swaps it to the front, then repeats for the rest."),
    "Insertion Sort": AlgorithmInfo(
        insertion_sort, "O(n)", "O(n²)", "O(n²)", "O(1)", True, True, True,
        "Grows a sorted part on the left by shifting bigger records right and inserting the next record."),
    "Merge Sort": AlgorithmInfo(
        merge_sort, "O(n log n)", "O(n log n)", "O(n log n)", "O(n)", True, False, True,
        "Splits the list in half, sorts each half, then merges the two sorted halves."),
    "Quick Sort": AlgorithmInfo(
        quick_sort, "O(n log n)", "O(n log n)", "O(n²)", "O(log n)", False, False, True,
        "Picks a pivot and groups records into smaller, equal and larger, then sorts the outer groups."),
    "Counting Sort": AlgorithmInfo(
        counting_sort, "O(n + k)", "O(n + k)", "O(n + k)", "O(n + k)", True, False, True,
        "Counts how many records have each whole-number key and places them directly. No comparisons. "
        "Only for numbers and dates (k is the size of the key range)."),
    "Heap Sort": AlgorithmInfo(
        heap_sort, "O(n log n)", "O(n log n)", "O(n log n)", "O(1)", False, False, False,
        "Builds a max-heap, then repeatedly swaps the largest record to the end. Extra algorithm."),
    "Shell Sort": AlgorithmInfo(
        shell_sort, "O(n log n)", "O(n^1.5)", "O(n^1.5)", "O(1)", False, False, False,
        "Insertion sort on records far apart first, then closer and closer. Extra algorithm."),
    "Radix Sort": AlgorithmInfo(
        radix_sort, "O(d·n)", "O(d·n)", "O(d·n)", "O(n + 10)", True, False, False,
        "Sorts whole numbers digit by digit, ones first, then tens, then hundreds, using ten buckets (0 to 9). "
        "No comparisons. Only for numbers and dates. d is the number of digits of the biggest key. Extra algorithm."),
    "Bucket Sort": AlgorithmInfo(
        bucket_sort, "O(n + k)", "O(n + k)", "O(n²)", "O(n + k)", True, False, False,
        "Spreads whole numbers into buckets by size (small numbers in the first buckets, big numbers in the last), "
        "sorts each small bucket with insertion sort, then joins the buckets. Fast when the numbers are spread "
        "evenly; slow if most land in one bucket. k is the number of buckets. Only for numbers and dates. "
        "Extra algorithm."),
    "Bogo Sort": AlgorithmInfo(
        bogo_sort, "O(n)", "O(n·n!)", "no upper limit", "O(1)", False, False, False,
        f"A joke algorithm: shuffle randomly until the list happens to be sorted. It needs about n! shuffles, "
        f"so it is only allowed for {BOGO_MAX_RECORDS} records or fewer (use a sample). For demonstration only."),
}


class SortResult:
    def __init__(self, algorithm, record_count, time_ms, metrics, records):
        info = ALGORITHMS[algorithm]
        self.algorithm = algorithm
        self.record_count = record_count
        self.time_ms = time_ms
        self.comparisons = metrics.comparisons
        self.swaps = metrics.swaps
        self.movements = metrics.movements
        self.time_complexity = f"{info.best} / {info.average} / {info.worst}"
        self.space_complexity = info.space
        self.stable = info.stable
        self.records = records
        self.verified = None
        self.note = ""


def unsupported_reason(algorithm, levels, records=None):
    """Explains why an algorithm cannot sort these columns, or returns None if it can."""
    if algorithm == "Bogo Sort":
        if records is not None and len(records) > BOGO_MAX_RECORDS:
            return (f"Bogo sort shuffles randomly until sorted, which needs about n! tries. It is only allowed for "
                    f"{BOGO_MAX_RECORDS} records or fewer (this input has {len(records):,}).")
        return None
    if algorithm not in ("Counting Sort", "Radix Sort", "Bucket Sort"):
        return None
    for column_key, _ in levels:
        if COLUMN_KIND[column_key] == "text":
            return f"{algorithm} needs whole-number keys (numbers or dates). Text cannot be split into digits or counted."
    if algorithm == "Counting Sort" and records:
        for column_key, _ in levels:
            values = [v for v in (comparable_value(r, column_key) for r in records) if v is not None]
            if values and max(values) - min(values) + 1 > MAX_COUNTING_RANGE:
                return f"The key range of '{column_key}' is larger than {MAX_COUNTING_RANGE:,}."
    return None


def sort_records(records, levels, algorithm, stop_event=None):
    """Sort a copy of records. Only the algorithm itself is timed."""
    if algorithm not in ALGORITHMS:
        raise ValueError(f"Unknown algorithm: {algorithm}")
    spec = SortSpec(levels)
    reason = unsupported_reason(algorithm, spec.levels, records)
    if reason:
        raise SortNotSupported(reason)
    entries = [spec.make_entry(record) for record in records]  # building keys is not timed
    metrics = SortMetrics(stop_event)
    started = time.perf_counter()
    sorted_entries = ALGORITHMS[algorithm].function(entries, spec, metrics)
    elapsed_ms = (time.perf_counter() - started) * 1000
    return SortResult(algorithm, len(records), elapsed_ms, metrics, [entry[1] for entry in sorted_entries])
