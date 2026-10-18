import random
from collections import Counter

from config import BENCHMARK_SEED
from sorting_algorithms import SortSpec, sort_records, unsupported_reason


class BenchmarkReport:
    def __init__(self):
        self.results = []
        self.skipped = {}  # algorithm name -> reason
        self.problems = []
        self.fastest = None

    @property
    def valid(self):
        return not self.problems


def prepare_input(records, sample_size=None, shuffle=False, seed=BENCHMARK_SEED):
    """Returns the list every algorithm will receive. The same seed always gives the same order."""
    generator = random.Random(seed)
    if sample_size is not None and sample_size < len(records):
        return generator.sample(records, sample_size)
    chosen = list(records)
    if shuffle:
        generator.shuffle(chosen)
    return chosen


def verify_result(original, result, spec):
    """Checks a sorted result without using any sorting. Returns (ok, message)."""
    output = result.records
    if len(output) != len(original):
        return False, f"record count changed ({len(original)} became {len(output)})"
    if Counter(map(id, output)) != Counter(map(id, original)):
        return False, "records were lost or duplicated"
    position = {id(record): index for index, record in enumerate(original)}
    previous_entry = None
    for record in output:
        entry = spec.make_entry(record)
        if previous_entry is not None:
            order = spec.compare(previous_entry, entry)
            if order > 0:
                return False, "output is not in sorted order"
            if order == 0 and result.stable and position[id(previous_entry[1])] > position[id(record)]:
                return False, "equal keys changed their original order (stable sort broken)"
        previous_entry = entry
    return True, ""


def run_benchmark(records, levels, algorithm_names, stop_event=None, on_step=None, keep_records=False):
    """Runs each algorithm on its own copy of the same input, then verifies every result."""
    spec = SortSpec(levels)
    report = BenchmarkReport()
    reference_keys = None
    for number, name in enumerate(algorithm_names, start=1):
        reason = unsupported_reason(name, spec.levels, records)
        if reason:
            report.skipped[name] = reason
            continue
        if on_step:
            on_step(f"Running {name} ({number} of {len(algorithm_names)})")
        result = sort_records(records, spec.levels, name, stop_event)
        ok, message = verify_result(records, result, spec)
        if ok:
            keys = [spec.make_key(record) for record in result.records]
            if reference_keys is None:
                reference_keys = keys
            elif keys != reference_keys:
                ok, message = False, "sorted keys differ from the other algorithms"
        result.verified = ok
        result.note = message
        if not ok:
            report.problems.append(f"{name}: {message}")
        if not keep_records:
            result.records = None
        report.results.append(result)
    if report.valid and report.results:
        report.fastest = min(report.results, key=lambda result: result.time_ms).algorithm
    return report
