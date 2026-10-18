import random
import unittest

from searching_algorithms import (NotSortedError, SearchError, binary_search, hash_search,
                                  is_sorted_ascending, linear_search)
from sorting_algorithms import sort_records


def make_records():
    generator = random.Random(3)
    names = ["alpha", "Alpha", "beta", "betamax", "gamma", " delta ", None]
    dates = [None, "2019-05-01T00:00:00Z", "2021-05-01T10:00:00Z", "2022-01-01T00:00:00Z"]
    return [{"id": i, "name": generator.choice(names), "stars": generator.choice([None, 1, 5, 5, 50, 500]),
             "created_at": generator.choice(dates)} for i in range(400)]


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.records = make_records()

    def sorted_by(self, column):
        return sort_records(self.records, [(column, False)], "Merge Sort").records

    def test_binary_search_agrees_with_linear_search_for_every_operator(self):
        cases = [("name", "equals", "ALPHA"), ("name", "equals", "delta"), ("name", "starts_with", "beta"),
                 ("name", "starts_with", "zzz"), ("stars", "greater_than", "5"), ("stars", "equals", "5"),
                 ("stars", "less_than", "5"), ("stars", "greater_than", "9999"),
                 ("created_at", "date_before", "2021-05-01"), ("created_at", "date_after", "2021-05-01"),
                 ("created_at", "equals", "2021-05-01")]
        for column, operator, text in cases:
            data = self.sorted_by(column)
            expected = linear_search(data, column, operator, text).matches
            actual = binary_search(data, column, operator, text).matches
            self.assertEqual(actual, expected, (column, operator, text))

    def test_binary_search_refuses_unsorted_data(self):
        with self.assertRaises(NotSortedError):
            binary_search(self.records, "stars", "equals", "5")

    def test_binary_search_refuses_data_sorted_by_a_different_column(self):
        with self.assertRaises(NotSortedError):
            binary_search(self.sorted_by("name"), "stars", "equals", "5")

    def test_binary_search_refuses_descending_data(self):
        descending = sort_records(self.records, [("stars", True)], "Merge Sort").records
        self.assertFalse(is_sorted_ascending(descending, "stars"))
        with self.assertRaises(NotSortedError):
            binary_search(descending, "stars", "equals", "5")

    def test_binary_search_rejects_substring_operators(self):
        with self.assertRaises(SearchError):
            binary_search(self.sorted_by("name"), "name", "contains", "eta")

    def test_binary_search_uses_few_comparisons(self):
        data = self.sorted_by("stars")
        self.assertLess(binary_search(data, "stars", "equals", "5").comparisons, 40)
        self.assertEqual(linear_search(data, "stars", "equals", "5").comparisons, 400)

    def test_hash_search_matches_linear_search(self):
        for column, text in [("name", "Alpha"), ("stars", "50"), ("created_at", "2022-01-01"), ("name", "nothing")]:
            self.assertEqual(hash_search(self.records, column, "equals", text).matches,
                             linear_search(self.records, column, "equals", text).matches)
        with self.assertRaises(SearchError):
            hash_search(self.records, "name", "contains", "a")

    def test_case_spaces_and_missing_values(self):
        names = [r["name"] for r in linear_search(self.records, "name", "contains", "  ALPH ").matches]
        self.assertTrue(names)
        self.assertTrue(all("alph" in name.lower() for name in names))
        self.assertTrue(all(r["name"] is None for r in linear_search(self.records, "name", "is_missing", "").matches))
        delta = linear_search(self.records, "name", "equals", "delta").matches
        self.assertTrue(delta and all(r["name"] == " delta " for r in delta))

    def test_invalid_input_gives_a_clear_error(self):
        for column, operator, text in [("stars", "greater_than", "many"), ("created_at", "date_before", "yesterday"),
                                       ("nope", "equals", "x")]:
            with self.assertRaises(SearchError):
                linear_search(self.records, column, operator, text)

    def test_empty_dataset(self):
        self.assertEqual(linear_search([], "stars", "equals", "1").matches, [])
        self.assertEqual(binary_search([], "stars", "equals", "1").matches, [])
        self.assertEqual(hash_search([], "stars", "equals", "1").matches, [])


if __name__ == "__main__":
    unittest.main()
