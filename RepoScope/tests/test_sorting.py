import random
import threading
import unittest
from functools import cmp_to_key

from benchmark import prepare_input, run_benchmark, verify_result
from models import comparable_value
from sorting_algorithms import (ALGORITHMS, BOGO_MAX_RECORDS, SortCancelled, SortNotSupported, SortSpec, sort_records,
                                unsupported_reason)


def make_records(count, seed=1):
    generator = random.Random(seed)
    records = []
    for number in range(count):
        records.append({
            "id": number,
            "name": generator.choice(["alpha", "Beta", "gamma", "delta", "beta", None]),
            "language": generator.choice(["Python", "python", "Go", "Rust", None]),
            "stars": generator.choice([None, 0, 1, 5, 5, 5, 20, 1000]),
            "forks": generator.randint(0, 10),
            "created_at": generator.choice([None, "2015-03-01T10:00:00Z", "2020-12-31T23:59:59Z", "2020-12-31T01:00:00Z"]),
        })
    return records


def reference_order(records, levels):
    """Python's sort is used here only to check the answers, never inside the project."""
    spec = SortSpec(levels)

    def compare(a, b):
        return spec.compare(spec.make_entry(a), spec.make_entry(b))

    return sorted(records, key=cmp_to_key(compare))


FAST_ALGORITHMS = [name for name in ALGORITHMS if name != "Bogo Sort"]  # bogo sort only accepts tiny inputs


def algorithms_for(levels, records=None):
    return [name for name in ALGORITHMS if unsupported_reason(name, levels, records) is None]


class SortingAlgorithmTests(unittest.TestCase):
    def test_all_algorithms_sort_every_kind_of_column_both_directions(self):
        records = make_records(200)
        for column in ["name", "language", "stars", "forks", "created_at"]:
            for descending in (False, True):
                levels = [(column, descending)]
                expected = [comparable_value(r, column) for r in reference_order(records, levels)]
                for algorithm in algorithms_for(levels, records):
                    with self.subTest(column=column, descending=descending, algorithm=algorithm):
                        result = sort_records(records, levels, algorithm)
                        self.assertEqual([comparable_value(r, column) for r in result.records], expected)

    def test_no_records_lost_or_duplicated_and_attributes_preserved(self):
        records = make_records(150)
        for algorithm in FAST_ALGORITHMS:
            result = sort_records(records, [("stars", True)], algorithm)
            self.assertEqual(sorted(r["id"] for r in result.records), [r["id"] for r in records])
            self.assertEqual({id(r) for r in result.records}, {id(r) for r in records})

    def test_input_list_is_not_modified(self):
        records = make_records(50)
        before = list(records)
        for algorithm in FAST_ALGORITHMS:
            sort_records(records, [("stars", False)], algorithm)
            self.assertEqual(records, before)

    def test_empty_and_single_element(self):
        for algorithm in ALGORITHMS:
            self.assertEqual(sort_records([], [("stars", False)], algorithm).records, [])
            one = [{"id": 1, "stars": 3}]
            self.assertEqual(sort_records(one, [("stars", False)], algorithm).records, one)

    def test_all_equal_keys(self):
        records = [{"id": i, "stars": 7} for i in range(40)]
        for algorithm in FAST_ALGORITHMS:
            self.assertEqual(len(sort_records(records, [("stars", True)], algorithm).records), 40)

    def test_missing_values_always_last(self):
        records = make_records(100)
        for descending in (False, True):
            for algorithm in FAST_ALGORITHMS:
                values = [r["stars"] for r in sort_records(records, [("stars", descending)], algorithm).records]
                first_missing = values.index(None)
                self.assertTrue(all(v is None for v in values[first_missing:]))

    def test_stable_algorithms_keep_original_order_of_equal_keys(self):
        records = make_records(300)
        for descending in (False, True):
            expected_ids = [r["id"] for r in reference_order(records, [("stars", descending)])]
            for name, info in ALGORITHMS.items():
                if info.stable:
                    result = sort_records(records, [("stars", descending)], name)
                    self.assertEqual([r["id"] for r in result.records], expected_ids, name)

    def test_unstable_label_is_honest(self):
        # Two repositories with equal stars: selection sort moves the later one in front.
        records = [{"id": "a", "stars": 5}, {"id": "b", "stars": 5}, {"id": "c", "stars": 1}]
        result = sort_records(records, [("stars", False)], "Selection Sort")
        self.assertEqual([r["id"] for r in result.records], ["c", "b", "a"])
        self.assertFalse(ALGORITHMS["Selection Sort"].stable)

    def test_multi_level_sorting_matches_reference_for_every_algorithm(self):
        records = make_records(250)
        levels = [("language", False), ("stars", True), ("name", False)]
        spec = SortSpec(levels)
        expected = reference_order(records, levels)
        expected_keys = [spec.make_key(r) for r in expected]
        for algorithm in algorithms_for(levels, records):
            result = sort_records(records, levels, algorithm)
            self.assertEqual([spec.make_key(r) for r in result.records], expected_keys, algorithm)
            if ALGORITHMS[algorithm].stable:
                self.assertEqual([r["id"] for r in result.records], [r["id"] for r in expected], algorithm)

    def test_multi_level_counting_sort_on_numbers_and_dates(self):
        records = make_records(250)
        levels = [("created_at", True), ("stars", False)]
        expected = [r["id"] for r in reference_order(records, levels)]
        result = sort_records(records, levels, "Counting Sort")
        self.assertEqual([r["id"] for r in result.records], expected)

    def test_dates_compare_by_day(self):
        records = [{"id": 1, "created_at": "2020-12-31T23:59:59Z"}, {"id": 2, "created_at": "2020-12-31T01:00:00Z"},
                   {"id": 3, "created_at": "2019-01-01T00:00:00Z"}]
        result = sort_records(records, [("created_at", False)], "Merge Sort")
        self.assertEqual([r["id"] for r in result.records], [3, 1, 2])

    def test_counting_sort_rejects_text_columns(self):
        self.assertIsNotNone(unsupported_reason("Counting Sort", [("language", False)]))
        with self.assertRaises(SortNotSupported):
            sort_records(make_records(5), [("language", False)], "Counting Sort")

    def test_counting_sort_rejects_huge_key_range(self):
        records = [{"id": 1, "stars": 0}, {"id": 2, "stars": 5_000_000}]
        self.assertIsNotNone(unsupported_reason("Counting Sort", [("stars", False)], records))

    def test_metrics_are_non_negative_and_follow_the_definitions(self):
        records = make_records(200)
        by_name = {name: sort_records(records, [("stars", False)], name) for name in FAST_ALGORITHMS}
        for result in by_name.values():
            self.assertGreaterEqual(result.time_ms, 0)
            self.assertGreaterEqual(result.comparisons, 0)
            self.assertGreaterEqual(result.swaps, 0)
            self.assertGreaterEqual(result.movements, 0)
            self.assertEqual(result.record_count, 200)
        self.assertEqual(by_name["Merge Sort"].swaps, 0)
        self.assertGreater(by_name["Merge Sort"].movements, 0)
        self.assertEqual(by_name["Insertion Sort"].swaps, 0)
        self.assertEqual(by_name["Bubble Sort"].movements, 0)
        self.assertEqual(by_name["Counting Sort"].comparisons, 0)
        self.assertEqual(by_name["Counting Sort"].swaps, 0)
        self.assertEqual((by_name["Radix Sort"].comparisons, by_name["Radix Sort"].swaps), (0, 0))
        self.assertGreater(by_name["Radix Sort"].movements, 0)
        self.assertEqual(by_name["Bucket Sort"].swaps, 0)
        self.assertGreater(by_name["Bucket Sort"].movements, 0)

    def test_counts_are_exact_for_a_tiny_example(self):
        records = [{"stars": 3}, {"stars": 2}, {"stars": 1}]
        result = sort_records(records, [("stars", False)], "Bubble Sort")
        self.assertEqual((result.comparisons, result.swaps), (3, 3))
        result = sort_records(records, [("stars", False)], "Selection Sort")
        self.assertEqual((result.comparisons, result.swaps), (3, 1))

    def test_cancel_stops_a_sort(self):
        stop = threading.Event()
        stop.set()
        with self.assertRaises(SortCancelled):
            sort_records(make_records(100), [("stars", False)], "Bubble Sort", stop_event=stop)

    def test_invalid_choices_are_rejected(self):
        with self.assertRaises(ValueError):
            sort_records([], [], "Merge Sort")
        with self.assertRaises(ValueError):
            sort_records([], [("not_a_column", False)], "Merge Sort")
        with self.assertRaises(ValueError):
            sort_records([], [("stars", False)], "Miracle Sort")


class BucketSortTests(unittest.TestCase):
    def test_matches_reference_on_numbers_dates_and_two_levels_both_directions(self):
        records = make_records(300)
        for levels in ([("stars", False)], [("stars", True)], [("forks", True)], [("created_at", False)],
                       [("created_at", True), ("stars", False)], [("stars", True), ("forks", False)]):
            expected = [r["id"] for r in reference_order(records, levels)]
            result = sort_records(records, levels, "Bucket Sort")
            self.assertEqual([r["id"] for r in result.records], expected, levels)

    def test_uneven_data_and_all_equal_keys(self):
        # Nearly everything is tiny and one value is huge, so almost all records share one bucket.
        records = [{"id": i, "stars": value} for i, value in enumerate([1, 2, 1, 3, 2, 1_000_000, 0, 2])]
        result = sort_records(records, [("stars", False)], "Bucket Sort")
        self.assertEqual([r["id"] for r in result.records], [6, 0, 2, 1, 4, 7, 3, 5])
        same = [{"id": i, "stars": 4} for i in range(10)]
        self.assertEqual([r["id"] for r in sort_records(same, [("stars", True)], "Bucket Sort").records], list(range(10)))

    def test_small_hand_example_counts(self):
        records = [{"stars": 170}, {"stars": 45}, {"stars": 75}, {"stars": 90}]
        result = sort_records(records, [("stars", False)], "Bucket Sort")
        self.assertEqual([r["stars"] for r in result.records], [45, 75, 90, 170])
        self.assertEqual((result.comparisons, result.swaps, result.movements), (1, 0, 4))

    def test_refuses_text_and_is_stable(self):
        self.assertIsNotNone(unsupported_reason("Bucket Sort", [("language", False)]))
        with self.assertRaises(SortNotSupported):
            sort_records(make_records(5), [("language", False)], "Bucket Sort")
        self.assertTrue(ALGORITHMS["Bucket Sort"].stable)

    def test_empty_single_and_cancel(self):
        self.assertEqual(sort_records([], [("stars", False)], "Bucket Sort").records, [])
        stop = threading.Event()
        stop.set()
        with self.assertRaises(SortCancelled):
            sort_records(make_records(50), [("stars", False)], "Bucket Sort", stop_event=stop)


class RadixAndBogoTests(unittest.TestCase):
    def test_radix_sort_matches_reference_on_numbers_dates_and_two_levels(self):
        records = make_records(300)
        for levels in ([("stars", False)], [("stars", True)], [("forks", True)], [("created_at", False)],
                       [("created_at", True), ("stars", False)], [("stars", True), ("forks", False)]):
            expected = [r["id"] for r in reference_order(records, levels)]
            result = sort_records(records, levels, "Radix Sort")
            self.assertEqual([r["id"] for r in result.records], expected, levels)

    def test_radix_sort_handles_big_numbers_and_all_equal_keys(self):
        records = [{"id": i, "stars": value} for i, value in enumerate([123456789, 5, 99999, 5, 0, 123456789])]
        result = sort_records(records, [("stars", False)], "Radix Sort")
        self.assertEqual([r["id"] for r in result.records], [4, 1, 3, 2, 0, 5])
        same = [{"id": i, "stars": 9} for i in range(10)]
        self.assertEqual([r["id"] for r in sort_records(same, [("stars", True)], "Radix Sort").records], list(range(10)))

    def test_radix_sort_refuses_text(self):
        self.assertIsNotNone(unsupported_reason("Radix Sort", [("name", False)]))
        with self.assertRaises(SortNotSupported):
            sort_records(make_records(5), [("name", False)], "Radix Sort")

    def test_bogo_sort_sorts_a_tiny_input_including_duplicates_and_missing_values(self):
        records = make_records(7, seed=4)
        for levels in ([("stars", False)], [("stars", True)], [("language", False), ("stars", True)]):
            expected = [SortSpec(levels).make_key(r) for r in reference_order(records, levels)]
            result = sort_records(records, levels, "Bogo Sort")
            self.assertEqual([SortSpec(levels).make_key(r) for r in result.records], expected)
            self.assertEqual({id(r) for r in result.records}, {id(r) for r in records})
            self.assertEqual((result.movements >= 0, result.swaps >= 0, result.comparisons > 0), (True, True, True))

    def test_bogo_sort_on_sorted_input_needs_no_shuffle(self):
        records = [{"stars": 1}, {"stars": 2}, {"stars": 3}]
        result = sort_records(records, [("stars", False)], "Bogo Sort")
        self.assertEqual((result.comparisons, result.swaps), (2, 0))

    def test_bogo_sort_refuses_more_than_the_limit(self):
        records = make_records(BOGO_MAX_RECORDS + 1)
        self.assertIsNotNone(unsupported_reason("Bogo Sort", [("stars", False)], records))
        with self.assertRaises(SortNotSupported):
            sort_records(records, [("stars", False)], "Bogo Sort")
        sort_records(records[:BOGO_MAX_RECORDS], [("stars", False)], "Bogo Sort")

    def test_bogo_sort_can_be_cancelled(self):
        stop = threading.Event()
        stop.set()
        with self.assertRaises(SortCancelled):
            sort_records([{"stars": 3}, {"stars": 2}, {"stars": 1}], [("stars", False)], "Bogo Sort", stop_event=stop)

    def test_benchmark_of_all_eleven_algorithms_on_a_tiny_input(self):
        report = run_benchmark(make_records(7, seed=2), [("stars", True)], list(ALGORITHMS))
        self.assertTrue(report.valid, report.problems)
        self.assertEqual(len(report.results), 11)
        self.assertEqual(report.skipped, {})


class BenchmarkTests(unittest.TestCase):
    def test_every_algorithm_gets_the_same_original_input_and_results_are_verified(self):
        records = make_records(300)
        report = run_benchmark(records, [("stars", True)], list(ALGORITHMS))
        self.assertTrue(report.valid, report.problems)
        self.assertEqual(len(report.results), 10)  # every algorithm except bogo sort, which is refused for 300 records
        self.assertIn("Bogo Sort", report.skipped)
        self.assertTrue(all(r.verified for r in report.results))
        self.assertIn(report.fastest, ALGORITHMS)
        self.assertTrue(all(r.record_count == 300 for r in report.results))

    def test_text_column_skips_counting_sort_with_a_reason(self):
        report = run_benchmark(make_records(50), [("language", False)], list(ALGORITHMS))
        self.assertIn("Counting Sort", report.skipped)
        self.assertIn("Radix Sort", report.skipped)
        self.assertIn("Bucket Sort", report.skipped)
        self.assertEqual(len(report.results), 7)

    def test_verification_detects_wrong_results(self):
        records = make_records(30)
        spec = SortSpec([("stars", False)])
        result = sort_records(records, [("stars", False)], "Merge Sort")
        result.records = list(reversed(result.records))
        self.assertFalse(verify_result(records, result, spec)[0])
        result.records = result.records[:-1]
        self.assertFalse(verify_result(records, result, spec)[0])

    def test_sample_and_shuffle_are_repeatable(self):
        records = make_records(100)
        self.assertEqual(prepare_input(records, 20), prepare_input(records, 20))
        self.assertEqual(len(prepare_input(records, 20)), 20)
        self.assertEqual(len(prepare_input(records, None, shuffle=True)), 100)
        self.assertEqual(prepare_input(records), records)


if __name__ == "__main__":
    unittest.main()
