import unittest
from unittest.mock import MagicMock

from mip.catalog import Catalog


MOCK_DATA_MODELS = [
    {
        "code": "dementia",
        "version": "0.1",
        "label": "Dementia",
        "longitudinal": False,
        "variables": [{"code": "dataset", "label": "Dataset", "type": "nominal"}],
        "groups": [
            {
                "code": "clinical",
                "label": "Clinical",
                "variables": [
                    {"code": "age", "label": "Age", "type": "real"},
                    {"code": "sex", "label": "Sex", "type": "nominal", "enumerations": {"M": "Male", "F": "Female"}},
                ],
                "groups": [
                    {"code": "cognitive", "label": "Cognitive", "variables": [{"code": "mmse", "label": "MMSE", "type": "integer"}]}
                ],
            }
        ],
        "datasets": [{"code": "adni", "label": "ADNI"}],
        "datasetsVariables": {"adni": ["age", "sex", "mmse"]},
    }
]


class TestCatalog(unittest.TestCase):
    def test_data_model_builds_collections(self):
        transport = MagicMock()
        transport.get.return_value = MOCK_DATA_MODELS

        dm = Catalog(transport).data_model("Dementia")

        self.assertEqual(dm.name, "Dementia (0.1)")
        self.assertEqual(dm.variables["Age"].label, "Age")
        self.assertEqual(dm.variables["MMSE"].label, "MMSE")
        self.assertTrue(dm.variables["Age"].is_numerical())
        self.assertTrue(dm.variables["Sex"].is_categorical())
        self.assertEqual(dm.variables["Sex"].categories(), ["Male", "Female"])
        self.assertEqual(dm.datasets["ADNI"].variables()[0].label, "Age")
        self.assertTrue(dm.datasets["ADNI"].has_variable(dm.variables["MMSE"]))

    def test_search_methods_return_native_lists(self):
        transport = MagicMock()
        transport.get.return_value = MOCK_DATA_MODELS
        catalog = Catalog(transport)

        self.assertIsInstance(catalog.list(), list)
        self.assertEqual(catalog.list()[0].label, "Dementia")
        self.assertIsInstance(catalog.summaries(), list)
        self.assertEqual(catalog.summaries()[0]["label"], "Dementia")
        self.assertIn("Data models", str(catalog.tree()))
        self.assertIsInstance(catalog.search_variables("MMSE"), list)
        self.assertEqual(catalog.search_variables("MMSE")[0].label, "MMSE")
        self.assertIsInstance(catalog.search_datasets("ADNI"), list)
        self.assertEqual(catalog.search_datasets("ADNI")[0].label, "ADNI")
        dm = catalog.data_model("Dementia")
        self.assertIsInstance(dm.variables.search("MMSE"), list)
        self.assertEqual(dm.variables.search("MMSE")[0].label, "MMSE")

    def test_data_model_list_and_tree_helpers(self):
        transport = MagicMock()
        transport.get.return_value = MOCK_DATA_MODELS
        dm = Catalog(transport).data_model("Dementia")

        self.assertEqual(dm.list_datasets()[0]["label"], "ADNI")
        self.assertEqual(dm.datasets.list()[0].label, "ADNI")
        self.assertEqual(dm.list_variables()[0]["label"], "Dataset")
        self.assertIn("groups", str(dm.tree()))
        self.assertIn("MMSE", str(dm.tree(include_variables=True)))
        self.assertIn("MMSE", str(dm.variables.tree()))
        self.assertIn("Clinical", str(dm.tree(group="Clinical", include_variables=True)))
        self.assertIn("MMSE", str(dm.tree(group="Cognitive", include_variables=True)))
        self.assertIn("MMSE", str(dm.variables.tree(group="Cognitive")))
        self.assertEqual(
            [item["label"] for item in dm.list_groups()],
            ["Clinical", "Cognitive"],
        )

    def test_unknown_group_raises_lookup_error(self):
        transport = MagicMock()
        transport.get.return_value = MOCK_DATA_MODELS
        dm = Catalog(transport).data_model("Dementia")
        with self.assertRaises(LookupError):
            dm.tree(group="missing")

    def test_ambiguous_data_model_requires_version(self):
        transport = MagicMock()
        transport.get.return_value = [*MOCK_DATA_MODELS, {**MOCK_DATA_MODELS[0], "version": "0.2"}]
        with self.assertRaises(LookupError):
            Catalog(transport).data_model("Dementia")


if __name__ == "__main__":
    unittest.main()
