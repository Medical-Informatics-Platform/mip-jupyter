import unittest
from types import SimpleNamespace

from mip import AnalysisSet


class Var:
    def __init__(self, code, *, label=None):
        self._code = code
        self.label = label or code


class TestAnalysisSet(unittest.TestCase):
    def test_inputdata_uses_new_shape(self):
        dm = SimpleNamespace(_code="dementia", label="Dementia", version="0.1")
        dm.internal_name = lambda: "dementia:0.1"
        adni = SimpleNamespace(_code="adni", label="ADNI")
        age = Var("age", label="Age")
        sex = Var("sex", label="Sex")
        analysis_set = AnalysisSet(data_model=dm, datasets=[adni], variables=[age, sex])

        payload = analysis_set.inputdata(filters={"condition": "AND", "rules": []})

        self.assertEqual(payload["data_model"], "dementia:0.1")
        self.assertEqual(payload["datasets"], ["adni"])
        self.assertEqual(payload["variables"], ["age", "sex"])
        self.assertIsNone(payload["validation_datasets"])
        self.assertNotIn("x", payload)
        self.assertNotIn("y", payload)

    def test_summary_and_explain_use_labels(self):
        dm = SimpleNamespace(_code="dementia", label="Dementia", version="0.1")
        dm.internal_name = lambda: "dementia:0.1"
        adni = SimpleNamespace(_code="adni", label="ADNI")
        age = Var("age", label="Age")
        analysis_set = AnalysisSet(data_model=dm, datasets=[adni], variables=[age])

        self.assertEqual(analysis_set.summary()["data_model"], "Dementia")
        self.assertEqual(analysis_set.summary()["datasets"], ["ADNI"])
        self.assertEqual(analysis_set.summary()["variables"], ["Age"])
        self.assertEqual(analysis_set.explain()["data_model"], "Dementia")
        self.assertEqual(analysis_set.explain()["datasets"], ["ADNI"])


if __name__ == "__main__":
    unittest.main()
