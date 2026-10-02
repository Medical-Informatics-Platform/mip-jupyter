import unittest
from types import SimpleNamespace

from mip.filters import F


class TestFilters(unittest.TestCase):
    def test_operator_serializes_variable_code(self):
        age = SimpleNamespace(_code="age", label="Age")
        payload = (F(age) >= 50).explain()
        self.assertEqual(payload["field"], "age")
        self.assertEqual(payload["operator"], "greater_or_equal")
        self.assertEqual(payload["value"], 50)

    def test_methods_and_composition(self):
        expr = (F("mmse").is_not_null() & F("sex").isin(["M", "F"])) | ~F("diagnosis").isin(["AD"])
        payload = expr.explain()
        self.assertEqual(payload["condition"], "OR")
        self.assertEqual(payload["rules"][0]["condition"], "AND")
        self.assertEqual(payload["rules"][1]["operator"], "not_in")
        self.assertEqual(payload["rules"][1]["value"], ["AD"])

    def test_between_and_to_payload(self):
        age = SimpleNamespace(_code="age", label="Age")
        expr = F(age).between(20, 26)
        payload = expr.to_payload()
        self.assertEqual(payload["operator"], "between")
        self.assertEqual(payload["value"], [20, 26])

    def test_isin_accepts_enumeration_labels(self):
        sex = SimpleNamespace(
            _code="sex",
            label="Sex",
            _data={"enumerations": {"M": "Male", "F": "Female"}},
        )

        def enumeration_code_for(value):
            from mip.labels import enumeration_code_for_label

            return enumeration_code_for_label(sex._data["enumerations"], value)

        sex.enumeration_code_for = enumeration_code_for
        payload = F(sex).isin(["Male", "Female"]).to_payload()
        self.assertEqual(payload["value"], ["M", "F"])


if __name__ == "__main__":
    unittest.main()
