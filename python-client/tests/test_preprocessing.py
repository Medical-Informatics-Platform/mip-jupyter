import unittest

from mip.preprocessing import KMeansClusterCreator
from mip.preprocessing import LongitudinalTransformer
from mip.preprocessing import MissingValuesHandler
from mip.preprocessing import OutlierWinsorizer
from mip.results import Result


class Var:
    def __init__(self, code, *, label=None):
        self._code = code
        self.label = label or code


class TestPreprocessing(unittest.TestCase):
    def test_missing_values_handler_serializes_variable_keys(self):
        age = Var("age", label="Age")
        apoe4 = Var("apoe4", label="APOE4")
        handler = MissingValuesHandler(
            strategies={age: "median", apoe4: "constant"},
            fill_values={apoe4: "unknown"},
        )
        spec = handler.spec()

        self.assertEqual(spec["name"], "missing_values_handler")
        self.assertEqual(spec["parameters"]["strategies"], {"age": "median", "apoe4": "constant"})
        self.assertEqual(spec["parameters"]["fill_values"], {"apoe4": "unknown"})
        self.assertEqual(
            handler.user_summary()["strategies"],
            {"Age": "median", "APOE4": "constant"},
        )

    def test_outlier_winsorizer_omits_empty_optional_maps(self):
        mmse = Var("mmse", label="MMSE")
        handler = OutlierWinsorizer(strategies={mmse: "iqr"}, tails={mmse: "both"}, folds={mmse: 1.5})
        spec = handler.spec()

        self.assertEqual(spec["name"], "outlier_winsorizer")
        self.assertEqual(spec["parameters"]["strategies"], {"mmse": "iqr"})
        self.assertEqual(spec["parameters"]["tails"], {"mmse": "both"})
        self.assertEqual(spec["parameters"]["folds"], {"mmse": 1.5})
        self.assertNotIn("fill_values", spec["parameters"])
        self.assertEqual(handler.user_summary()["strategies"], {"MMSE": "iqr"})

    def test_longitudinal_transformer_serializes_visit_and_strategies(self):
        age = Var("age", label="Age")
        mmse = Var("mmse", label="MMSE")
        transformer = LongitudinalTransformer(
            visit1="BL",
            visit2="FL1",
            strategies={age: "diff", mmse: "second"},
        )
        spec = transformer.spec()

        self.assertEqual(spec["name"], "longitudinal_transformer")
        self.assertEqual(spec["parameters"]["visit1"], "BL")
        self.assertEqual(spec["parameters"]["visit2"], "FL1")
        self.assertEqual(spec["parameters"]["strategies"], {"age": "diff", "mmse": "second"})
        self.assertEqual(
            transformer.user_summary()["strategies"],
            {"Age": "diff", "MMSE": "second"},
        )


REUSABLE_PREPROCESSING = {
    "schema_version": "1",
    "preprocessing_name": "kmeans_cluster_creator",
    "cluster_variables": ["lefthippocampus", "righthippocampus"],
    "centers": {
        "cluster_0": {"lefthippocampus": 1.0, "righthippocampus": 2.0},
        "cluster_1": {"lefthippocampus": 3.0, "righthippocampus": 4.0},
        "cluster_2": {"lefthippocampus": 5.0, "righthippocampus": 6.0},
    },
    "source_context": {
        "data_model": "dementia:0.1",
        "datasets": ["adni"],
        "input_fingerprint": "abc123",
    },
    "available_outputs": [
        {
            "output_mode": "new_column",
            "semantic_operation": "cluster_assignment",
            "variable_type": "nominal",
            "number_of_variables": 1,
            "eligible_roles": ["x", "y"],
            "cardinality": 3,
            "selection_rule": "nearest_center",
        }
    ],
    "cluster_choices": [
        {"cluster_id": "cluster_0", "label": "Cluster 0"},
        {"cluster_id": "cluster_1", "label": "Cluster 1"},
        {"cluster_id": "cluster_2", "label": "Cluster 2"},
    ],
}


class TestKMeansClusterCreator(unittest.TestCase):
    def test_spec_serializes_code_and_reusable_preprocessing_verbatim(self):
        creator = KMeansClusterCreator(
            label="Hippocampus cluster",
            source=Result(raw={"reusable_preprocessing": REUSABLE_PREPROCESSING}, result_type="kmeans"),
        )
        spec = creator.spec()

        self.assertEqual(spec["name"], "kmeans_cluster_creator")
        self.assertEqual(spec["parameters"]["code"], "hippocampus_cluster")
        self.assertEqual(spec["parameters"]["reusable_preprocessing"], REUSABLE_PREPROCESSING)

    def test_variable_enumerations_are_cluster_ids(self):
        creator = KMeansClusterCreator(
            label="Hippocampus cluster",
            source=Result(raw={"reusable_preprocessing": REUSABLE_PREPROCESSING}, result_type="kmeans"),
        )

        self.assertEqual(creator.enumerations, ["cluster_0", "cluster_1", "cluster_2"])
        self.assertEqual(creator.variable.categories(), ["cluster_0", "cluster_1", "cluster_2"])
        self.assertTrue(creator.variable.is_categorical())
        self.assertEqual(creator.cluster_variables, ["lefthippocampus", "righthippocampus"])

    def test_user_summary_lists_label_categories_and_cluster_variables(self):
        creator = KMeansClusterCreator(
            label="Hippocampus cluster",
            source=Result(raw={"reusable_preprocessing": REUSABLE_PREPROCESSING}, result_type="kmeans"),
        )

        self.assertEqual(
            creator.user_summary(),
            {
                "name": "kmeans_cluster_creator",
                "label": "Hippocampus cluster",
                "categories": ["cluster_0", "cluster_1", "cluster_2"],
                "cluster_variables": ["lefthippocampus", "righthippocampus"],
            },
        )

    def test_raises_when_result_has_no_reusable_preprocessing(self):
        with self.assertRaises(ValueError):
            KMeansClusterCreator(label="Cluster", source=Result(raw={}, result_type="kmeans"))
        with self.assertRaises(ValueError):
            KMeansClusterCreator(
                label="Cluster",
                source=Result(raw={"reusable_preprocessing": None}, result_type="kmeans"),
            )


if __name__ == "__main__":
    unittest.main()
