import unittest

from mip.filters import F
from mip.preprocessing import CategoricalColumnCreator


class Var:
    def __init__(self, code, *, label=None, enumerations=None):
        self._code = code
        self.label = label or code
        self._data = {"enumerations": enumerations or {}}

    def enumeration_code_for(self, value):
        from mip.labels import enumeration_code_for_label

        return enumeration_code_for_label(self._data.get("enumerations"), value)


class TestCategoricalColumnCreator(unittest.TestCase):
    def test_categorical_column_creator_creates_derived_variable_with_enumerations(self):
        mmse = Var("mmse", label="MMSE")
        cdr = Var("cdr", label="CDR")
        creator = CategoricalColumnCreator(
            label="Cognitive profile",
            rules={
                "Preserved": F(mmse) >= 27,
                "Mild impairment": F(mmse).between(20, 26) & F(cdr).isin([0.5, 1.0]),
                "Severe impairment": F(mmse) < 20,
            },
            default_enumeration="Unclassified",
        )

        self.assertEqual(creator.variable.label, "Cognitive profile")
        self.assertEqual(
            creator.enumerations,
            ["Preserved", "Mild impairment", "Severe impairment", "Unclassified"],
        )
        self.assertTrue(creator.variable.is_categorical())
        self.assertFalse(creator.variable.is_numerical())
        self.assertEqual(creator.variable.categories(), creator.enumerations)

    def test_categorical_column_creator_payload_uses_filter_rules_strategy(self):
        mmse = Var("mmse", label="MMSE")
        creator = CategoricalColumnCreator(
            label="Cognitive profile",
            rules={"Preserved": F(mmse) >= 27},
            default_enumeration="Unclassified",
        )

        spec = creator.spec()
        self.assertEqual(spec["name"], "categorical_column_creator")
        self.assertEqual(spec["parameters"]["code"], "cognitive_profile")
        self.assertEqual(spec["parameters"]["strategy"], "filter_rules")
        self.assertEqual(spec["parameters"]["default_enumeration"], "Unclassified")
        self.assertEqual(spec["parameters"]["rules"]["Preserved"]["operator"], "greater_or_equal")


if __name__ == "__main__":
    unittest.main()
