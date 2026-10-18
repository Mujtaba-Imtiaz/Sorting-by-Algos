import unittest

from filtering import Condition, FilterError, describe_conditions, filter_records

RECORDS = [
    {"id": 1, "name": "ml-lib", "language": "Python", "stars": 5000, "archived": 0,
     "description": "Machine learning toolkit", "license_name": "MIT License", "updated_at": "2024-03-01T00:00:00Z"},
    {"id": 2, "name": "web-ui", "language": "JavaScript", "stars": 900, "archived": 1,
     "description": None, "license_name": None, "updated_at": "2020-01-01T00:00:00Z"},
    {"id": 3, "name": "type-lib", "language": "TypeScript", "stars": 1500, "archived": 0,
     "description": "A typed library for machine learning", "license_name": None, "updated_at": "2024-06-01T00:00:00Z"},
    {"id": 4, "name": "old-tool", "language": None, "stars": None, "archived": 0,
     "description": "", "license_name": "Apache License 2.0", "updated_at": None},
]


def ids(conditions):
    return [r["id"] for r in filter_records(RECORDS, conditions)]


class FilterTests(unittest.TestCase):
    def test_language_and_stars(self):
        self.assertEqual(ids([Condition("language", "equals", "python"),
                              Condition("stars", "greater_than", "1,000")]), [1])

    def test_or(self):
        self.assertEqual(ids([Condition("language", "equals", "JavaScript"),
                              Condition("language", "equals", "TypeScript", join="OR")]), [2, 3])

    def test_not_archived(self):
        self.assertEqual(ids([Condition("archived", "equals", "true", negate=True)]), [1, 3, 4])

    def test_description_contains_and_license_not_missing(self):
        self.assertEqual(ids([Condition("description", "contains", "machine learning"),
                              Condition("license_name", "is_not_missing")]), [1])

    def test_stars_and_updated_after_date(self):
        self.assertEqual(ids([Condition("stars", "greater_than", "500"),
                              Condition("updated_at", "date_after", "2024-04-01")]), [3])

    def test_and_binds_tighter_than_or(self):
        conditions = [Condition("language", "equals", "Python"),
                      Condition("stars", "greater_than", "100000"),
                      Condition("language", "equals", "TypeScript", join="OR")]
        self.assertEqual(ids(conditions), [3])

    def test_string_operators(self):
        self.assertEqual(ids([Condition("name", "starts_with", "ML")]), [1])
        self.assertEqual(ids([Condition("name", "ends_with", "-lib")]), [1, 3])
        self.assertEqual(ids([Condition("name", "contains", "tool")]), [4])
        self.assertEqual(ids([Condition("name", "equals", "WEB-UI")]), [2])

    def test_missing_values_never_match_comparisons_but_not_inverts_them(self):
        self.assertNotIn(4, ids([Condition("stars", "less_than", "999999")]))
        self.assertIn(4, ids([Condition("stars", "less_than", "999999", negate=True)]))
        self.assertEqual(ids([Condition("language", "is_missing")]), [4])
        self.assertEqual(ids([Condition("description", "is_missing")]), [2, 4])

    def test_no_conditions_returns_a_copy_of_everything(self):
        result = filter_records(RECORDS, [])
        self.assertEqual(result, RECORDS)
        self.assertIsNot(result, RECORDS)

    def test_filtering_does_not_change_the_source_list(self):
        before = list(RECORDS)
        ids([Condition("stars", "greater_than", "1")])
        self.assertEqual(RECORDS, before)

    def test_invalid_conditions_raise_filter_error(self):
        for bad in [Condition("stars", "greater_than", "abc"), Condition("updated_at", "date_after", "soon"),
                    Condition("archived", "equals", "maybe"), Condition("name", "greater_than", "a"),
                    Condition("name", "contains", "  "), Condition("ghost", "equals", "x")]:
            with self.assertRaises(FilterError):
                filter_records(RECORDS, [bad])

    def test_description_text(self):
        text = describe_conditions([Condition("stars", "greater_than", "5"),
                                    Condition("archived", "equals", "true", negate=True, join="OR")])
        self.assertIn("OR NOT", text)


if __name__ == "__main__":
    unittest.main()
