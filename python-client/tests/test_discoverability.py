"""Tests for notebook discoverability helpers."""

import unittest
from unittest.mock import MagicMock

import mip
from mip.analysis import AnalysisSet
from mip.catalog import Catalog
from mip.catalog_registry import PIPELINE_BACKEND_ALGORITHMS
from mip.client import Client
from mip.display import HelpText
from mip.pipeline import Pipeline
from mip.results import ModelResult
from mip.results import Result

from test_catalog import MOCK_DATA_MODELS


class TestDiscoverability(unittest.TestCase):
    def setUp(self):
        self.transport = MagicMock()
        self.transport.get.return_value = MOCK_DATA_MODELS
        self.catalog = Catalog(self.transport)
        self.dm = self.catalog.data_model("Dementia")
        self.age = self.dm.variables["Age"]
        self.sex = self.dm.variables["Sex"]
        self.mmse = self.dm.variables["MMSE"]
        self.adni = self.dm.datasets["ADNI"]

    def test_help_returns_help_text(self):
        for obj in (
            Client("http://example/services"),
            self.catalog,
            self.dm,
            self.adni,
            self.age,
            self.dm.variables,
            self.dm.datasets,
        ):
            help_obj = obj.help()
            self.assertIsInstance(help_obj, HelpText)
            self.assertIn("help", str(help_obj).lower())
            self.assertIn("help", help_obj._repr_html_().lower())

    def test_repr_html_escapes_content(self):
        html = self.age._repr_html_()
        self.assertIn("Age", html)
        self.assertNotIn("<script", html.lower())

    def test_variable_collection_to_frame(self):
        frame = self.dm.variables.to_frame()
        self.assertIn("label", frame.columns)
        self.assertIn("group_path", frame.columns)
        self.assertIn("Age", frame["label"].tolist())
        age_row = frame.loc[frame["label"] == "Age"].iloc[0]
        self.assertEqual(age_row["group_path"], "Clinical")
        mmse_row = frame.loc[frame["label"] == "MMSE"].iloc[0]
        self.assertEqual(mmse_row["group_path"], "Clinical > Cognitive")
        sex_row = frame.loc[frame["label"] == "Sex"].iloc[0]
        self.assertEqual(sex_row["n_categories"], 2)

    def test_dataset_collection_to_frame(self):
        frame = self.dm.datasets.to_frame()
        self.assertIn("label", frame.columns)
        self.assertEqual(frame.iloc[0]["label"], "ADNI")

    def test_mip_to_frame_on_search_results(self):
        frame = mip.to_frame(self.dm.variables.search("Age"))
        self.assertEqual(frame.iloc[0]["label"], "Age")

    def test_metadata_tree_html_is_collapsible(self):
        tree = self.dm.tree(include_variables=True)
        html = tree._repr_html_()
        self.assertIn("<details", html)
        self.assertIn("Clinical", html)
        self.assertIn("MMSE", html)
        self.assertIn("Age", str(tree))
        self.assertNotIn("<details", str(tree))

    def test_variable_card_includes_categories_and_group(self):
        html = self.sex._repr_html_()
        self.assertIn("Clinical", html)
        self.assertIn("Male", html)
        self.assertIn("categorical", html)

    def test_dataset_card_includes_variable_preview(self):
        html = self.adni._repr_html_()
        self.assertIn("Age", html)
        self.assertIn("n_variables", html)

    def test_pipeline_available_algorithms(self):
        analysis_set = AnalysisSet(
            data_model=self.dm,
            datasets=[self.adni],
            variables=[self.age, self.mmse],
        )
        pipeline = Pipeline(analysis_set=analysis_set)
        methods = pipeline.available_algorithms()
        self.assertEqual(len(methods), len(PIPELINE_BACKEND_ALGORITHMS))
        self.assertIn("histogram", methods)
        self.assertIn("logistic_regression", methods)
        self.assertIn("pca", methods)

    def test_pipeline_recommend_algorithms(self):
        analysis_set = AnalysisSet(
            data_model=self.dm,
            datasets=[self.adni],
            variables=[self.age, self.mmse, self.sex],
        )
        pipeline = Pipeline(analysis_set=analysis_set)
        text = pipeline.recommend_algorithms()
        self.assertIn("Age", text)
        self.assertIn("numerical", text)
        self.assertIn("categorical", text)
        self.assertIn("histogram", text)
        html = text._repr_html_()
        self.assertIn("<table", html)
        self.assertIn("histogram", html)

    def test_data_model_select(self):
        analysis_set = self.dm.select(datasets=["ADNI"], variables=["Age", "MMSE"])
        self.assertEqual(analysis_set.summary()["datasets"], ["ADNI"])
        self.assertEqual(analysis_set.summary()["variables"], ["Age", "MMSE"])
        mixed = self.dm.select(datasets=[self.adni], variables=[self.age, "MMSE"])
        self.assertEqual(mixed.summary()["variables"], ["Age", "MMSE"])

    def test_catalog_repr_html(self):
        html = self.catalog._repr_html_()
        self.assertIn("Catalog", html)
        self.assertIn("Dementia", html)
        self.assertIn("<table", html)
        self.assertIn("n_variables", html)

    def test_result_help_and_repr_html(self):
        result = Result(raw={"bins": [1, 2], "counts": [3, 4]}, result_type="histogram")
        self.assertIn("Result help", str(result.help()))
        self.assertIn("histogram", result._repr_html_())

    def test_model_result_help(self):
        result = ModelResult(raw={}, result_type="logistic_regression")
        self.assertIn("ModelResult help", str(result.help()))

    def test_analysis_set_repr_html(self):
        analysis_set = AnalysisSet(
            data_model=self.dm,
            datasets=[self.adni],
            variables=[self.age],
        )
        html = analysis_set._repr_html_()
        self.assertIn("AnalysisSet", html)
        self.assertIn("Age", html)


if __name__ == "__main__":
    unittest.main()
