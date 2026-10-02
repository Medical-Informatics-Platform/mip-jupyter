"""Ensure user-facing surfaces never expose internal codes."""

import json
import unittest
from unittest.mock import MagicMock

from mip import AnalysisSet
from mip import Pipeline
from mip.catalog import Catalog
from mip.filters import F
from mip.preprocessing import MissingValuesHandler

from test_catalog import MOCK_DATA_MODELS


class TestLabelsOnly(unittest.TestCase):
    def setUp(self):
        self.transport = MagicMock()
        self.transport.get.return_value = MOCK_DATA_MODELS
        self.dm = Catalog(self.transport).data_model("Dementia")
        self.age = self.dm.variables["Age"]
        self.sex = self.dm.variables["Sex"]
        self.mmse = self.dm.variables["MMSE"]
        self.adni = self.dm.datasets["ADNI"]

    def test_summaries_do_not_include_code_fields(self):
        self.assertNotIn("code", self.age.summary())
        self.assertNotIn("code", self.adni.summary())
        self.assertNotIn("code", self.dm.summary())

    def test_categories_return_human_labels(self):
        self.assertEqual(self.sex.categories(), ["Male", "Female"])

    def test_variables_have_no_public_code_attribute(self):
        self.assertFalse(hasattr(self.age, "code"))

    def test_label_lookup_rejects_unrelated_identifier(self):
        with self.assertRaises(KeyError):
            self.dm.variables["adni"]

    def test_explain_preview_uses_labels(self):
        analysis_set = AnalysisSet(
            data_model=self.dm,
            datasets=[self.adni],
            variables=[self.age, self.mmse],
        )
        pipeline = Pipeline(
            analysis_set=analysis_set,
            filters=F(self.age) >= 50,
            handle_missing=MissingValuesHandler(strategies={self.mmse: "mean"}),
        )
        preview = json.dumps(pipeline.explain())
        self.assertIn("Age", preview)
        self.assertIn("MMSE", preview)
        self.assertNotIn('"age"', preview)
        self.assertNotIn('"mmse"', preview)

    def test_analysis_set_explain_uses_data_model_label(self):
        analysis_set = AnalysisSet(
            data_model=self.dm,
            datasets=[self.adni],
            variables=[self.age, self.mmse],
        )
        explained = analysis_set.explain()
        self.assertEqual(explained["data_model"], "Dementia")
        preview = json.dumps(explained)
        self.assertNotIn("dementia:0.1", preview)
        self.assertNotIn('"dementia"', preview)

    def test_filter_explain_isin_shows_enumeration_labels(self):
        from mip.labels import build_code_to_label_lookup
        from mip.labels import build_field_enumeration_lookups

        lookup = build_code_to_label_lookup([self.sex])
        enum_lookups = build_field_enumeration_lookups(self.dm.variables)
        explained = F(self.sex).isin(["Male", "Female"]).explain(
            lookup=lookup,
            enum_lookups=enum_lookups,
        )
        self.assertEqual(explained["field"], "Sex")
        self.assertEqual(explained["value"], ["Male", "Female"])

    def test_pipeline_explain_isin_shows_enumeration_labels(self):
        analysis_set = AnalysisSet(
            data_model=self.dm,
            datasets=[self.adni],
            variables=[self.age, self.sex],
        )
        pipeline = Pipeline(
            analysis_set=analysis_set,
            filters=F(self.sex).isin(["Male", "Female"]),
        )
        preview = json.dumps(pipeline.explain())
        self.assertIn("Male", preview)
        self.assertIn("Female", preview)
        self.assertNotIn('"M"', preview)
        self.assertNotIn('"F"', preview)

    def test_pipeline_explain_relabels_filter_only_variables(self):
        analysis_set = AnalysisSet(
            data_model=self.dm,
            datasets=[self.adni],
            variables=[self.age],
        )
        pipeline = Pipeline(
            analysis_set=analysis_set,
            filters=F(self.sex).isin(["Male"]),
        )
        explained = pipeline.explain()
        self.assertEqual(explained["filters"]["field"], "Sex")
        self.assertEqual(explained["filters"]["id"], "Sex")
        self.assertEqual(explained["filters"]["value"], ["Male"])
        self.assertNotIn('"sex"', json.dumps(explained))

    def test_tree_output_uses_labels_only(self):
        tree = str(self.dm.tree(include_variables=True))
        self.assertIn("Age", tree)
        self.assertNotIn("age [", tree)

    def test_focused_tree_title_uses_label_only(self):
        tree = str(self.dm.tree(group="Clinical"))
        self.assertIn("Dementia", tree)
        self.assertIn("Clinical", tree)
        self.assertNotIn("dementia:0.1", tree)
        self.assertNotIn("dementia:0.1 (Dementia)", tree)


if __name__ == "__main__":
    unittest.main()
