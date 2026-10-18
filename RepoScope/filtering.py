from dataclasses import dataclass

from models import COLUMN_KIND, comparable_value, date_to_ordinal


class FilterError(ValueError):
    pass


@dataclass
class Condition:
    column: str
    operator: str
    value: str = ""
    negate: bool = False  # NOT
    join: str = "AND"  # how this condition connects to the one before it


OPERATOR_LABELS = {
    "equals": "equals",
    "contains": "contains",
    "starts_with": "starts with",
    "ends_with": "ends with",
    "greater_than": "greater than",
    "less_than": "less than",
    "date_before": "before date",
    "date_after": "after date",
    "is_missing": "is missing",
    "is_not_missing": "is not missing",
}

_OPERATORS_BY_KIND = {
    "text": ["equals", "contains", "starts_with", "ends_with", "is_missing", "is_not_missing"],
    "int": ["equals", "greater_than", "less_than", "is_missing", "is_not_missing"],
    "date": ["equals", "date_before", "date_after", "is_missing", "is_not_missing"],
    "bool": ["equals", "is_missing", "is_not_missing"],
}
NO_VALUE_OPERATORS = ("is_missing", "is_not_missing")


def operators_for_kind(kind):
    return _OPERATORS_BY_KIND[kind]


def operator_label(operator, kind):
    if operator == "equals" and kind == "text":
        return "exact match"
    return OPERATOR_LABELS[operator]


def parse_query_value(kind, operator, text):
    """Converts what the user typed into the same form comparable_value() produces."""
    if operator in NO_VALUE_OPERATORS:
        return None
    text = (text or "").strip()
    if not text:
        raise FilterError("Please enter a value to search for.")
    if kind == "text":
        return text.casefold()
    if kind == "int":
        try:
            return int(text.replace(",", "").replace("_", ""))
        except ValueError:
            raise FilterError(f"'{text}' is not a whole number.")
    if kind == "date":
        ordinal = date_to_ordinal(text)
        if ordinal is None:
            raise FilterError(f"'{text}' is not a date. Use YYYY-MM-DD, for example 2023-06-30.")
        return ordinal
    if text.casefold() in ("true", "yes", "1"):
        return 1
    if text.casefold() in ("false", "no", "0"):
        return 0
    raise FilterError("Use true or false for this column.")


def evaluate_operator(value, operator, query):
    """value comes from comparable_value(); a missing value is None and never matches a comparison."""
    if operator == "is_missing":
        return value is None
    if operator == "is_not_missing":
        return value is not None
    if value is None:
        return False
    if operator == "equals":
        return value == query
    if operator == "contains":
        return query in value
    if operator == "starts_with":
        return value.startswith(query)
    if operator == "ends_with":
        return value.endswith(query)
    if operator in ("greater_than", "date_after"):
        return value > query
    if operator in ("less_than", "date_before"):
        return value < query
    raise FilterError(f"Unknown operator: {operator}")


def build_predicate(condition):
    if condition.column not in COLUMN_KIND:
        raise FilterError(f"Unknown column: {condition.column}")
    kind = COLUMN_KIND[condition.column]
    if condition.operator not in operators_for_kind(kind):
        raise FilterError(f"'{condition.operator}' cannot be used on a {kind} column.")
    query = parse_query_value(kind, condition.operator, condition.value)

    def predicate(record):
        result = evaluate_operator(comparable_value(record, condition.column), condition.operator, query)
        return not result if condition.negate else result

    return predicate


def filter_records(records, conditions):
    """Keeps records matching the conditions. AND is evaluated before OR, like x before + in maths.

    "A AND B OR C" means "(A AND B) OR C".
    """
    if not conditions:
        return list(records)
    groups = []
    for index, condition in enumerate(conditions):
        predicate = build_predicate(condition)
        if index == 0 or condition.join == "OR":
            groups.append([predicate])
        else:
            groups[-1].append(predicate)
    return [record for record in records if any(all(p(record) for p in group) for group in groups)]


def describe_conditions(conditions):
    if not conditions:
        return "no filters"
    parts = []
    for index, condition in enumerate(conditions):
        kind = COLUMN_KIND.get(condition.column, "text")
        text = f"{condition.column} {operator_label(condition.operator, kind)} {condition.value}".strip()
        if condition.negate:
            text = f"NOT ({text})"
        parts.append(text if index == 0 else f"{condition.join} {text}")
    return " ".join(parts)
