import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from mip import AnalysisSet
from mip import Pipeline
from mip.catalog_registry import PIPELINE_BACKEND_ALGORITHMS
from mip.filters import F
from mip.preprocessing import CategoricalColumnCreator
from mip.preprocessing import KMeansClusterCreator
from mip.preprocessing import LongitudinalTransformer
from mip.preprocessing import MissingValuesHandler
from mip.preprocessing import OutlierWinsorizer
from mip.results import Result


class Var:
    def __init__(self, code, *, label=None):
        self._code = code
        self.label = label or code


def _dm(transport):
    dm = SimpleNamespace(_code="dementia", label="Dementia", version="0.1", _transport=transport)
    dm.internal_name = lambda: "dementia:0.1"
    return dm


def _dataset(code, label):
    return SimpleNamespace(_code=code, label=label)


class TestPipeline(unittest.TestCase):
    def test_histogram_posts_transient_payload(self):
        transport = MagicMock()
        transport.post.return_value = {"status": "success", "result": {"bins": [1, 2], "counts": [3, 4]}}
        dm = _dm(transport)
        adni = _dataset("adni", "ADNI")
        age = Var("age", label="Age")
        mmse = Var("mmse", label="MMSE")
        analysis_set = AnalysisSet(data_model=dm, datasets=[adni], variables=[age, mmse])

        result = Pipeline(
            analysis_set=analysis_set,
            filters=F(age) >= 50,
            handle_missing=MissingValuesHandler(strategies={mmse: "mean"}),
            outlier_handling=OutlierWinsorizer(strategies={mmse: "iqr"}),
        ).histogram(variable=mmse, bins=20)

        endpoint, payload = transport.post.call_args.args
        analysis = payload["analysis"]
        self.assertEqual(endpoint, "/experiments/transient")
        self.assertEqual(analysis["algorithm"]["name"], "histogram")
        self.assertEqual(analysis["algorithm"]["y"], ["mmse"])
        self.assertEqual(analysis["algorithm"]["parameters"], {"bins": 20})
        self.assertEqual(analysis["inputdata"]["validation_datasets"], None)
        self.assertIn("age", analysis["inputdata"]["variables"])
        self.assertIn("mmse", analysis["inputdata"]["variables"])
        self.assertEqual(
            [step["name"] for step in analysis["preprocessing"]],
            ["missing_values_handler", "outlier_winsorizer"],
        )
        self.assertNotIn("mipVersion", payload)
        self.assertEqual(result.raw, {"bins": [1, 2], "counts": [3, 4]})

    def test_logistic_regression_uses_persisted_endpoint(self):
        transport = MagicMock()
        transport.post.return_value = {"status": "success", "result": {"summary": {"feature_names": ["Intercept", "age"], "coefficients": [0.1, 0.5]}}}
        dm = _dm(transport)
        age = Var("age", label="Age")
        diagnosis = Var("diagnosis", label="Diagnosis")
        analysis_set = AnalysisSet(data_model=dm, datasets=[_dataset("adni", "ADNI")], variables=[age, diagnosis])

        result = Pipeline(analysis_set=analysis_set).logistic_regression(x=[age], y=diagnosis, positive_class="AD", mode="persisted")

        endpoint, payload = transport.post.call_args.args
        analysis = payload["analysis"]
        self.assertEqual(endpoint, "/experiments")
        self.assertEqual(analysis["algorithm"]["name"], "logistic_regression")
        self.assertEqual(analysis["algorithm"]["x"], ["age"])
        self.assertEqual(analysis["algorithm"]["y"], ["diagnosis"])
        self.assertEqual(result.result_type, "logistic_regression")

    def test_t_test_serializes_required_backend_parameters(self):
        transport = MagicMock()
        transport.post.return_value = {"status": "success", "result": {}}
        dm = _dm(transport)
        age = Var("age", label="Age")
        diagnosis = Var("diagnosis", label="Diagnosis")
        analysis_set = AnalysisSet(
            data_model=dm,
            datasets=[_dataset("adni", "ADNI")],
            variables=[age, diagnosis],
        )

        Pipeline(analysis_set=analysis_set).t_test(
            variable=age,
            group_by=diagnosis,
            group_a="AD",
            group_b="CN",
        )

        parameters = transport.post.call_args.args[1]["analysis"]["algorithm"]["parameters"]
        self.assertEqual(
            parameters,
            {
                "alt_hypothesis": "two-sided",
                "alpha": 0.05,
                "groupA": "AD",
                "groupB": "CN",
            },
        )

    def test_pipeline_serializes_new_columns(self):
        transport = MagicMock()
        transport.post.return_value = {"status": "success", "result": {}}
        dm = _dm(transport)
        mmse = Var("mmse", label="MMSE")
        cdr = Var("cdr", label="CDR")
        analysis_set = AnalysisSet(
            data_model=dm,
            datasets=[_dataset("adni", "ADNI")],
            variables=[mmse, cdr],
        )
        creator = CategoricalColumnCreator(
            label="Cognitive profile",
            rules={
                "Preserved": F(mmse) >= 27,
                "Severe": F(mmse) < 20,
            },
            default_enumeration="Unclassified",
        )

        Pipeline(
            analysis_set=analysis_set,
            handle_missing=MissingValuesHandler(strategies={mmse: "drop", cdr: "drop"}),
            new_columns=[creator],
        ).histogram(variable=mmse)

        analysis = transport.post.call_args.args[1]["analysis"]
        self.assertEqual(
            [step["name"] for step in analysis["preprocessing"]],
            ["missing_values_handler", "categorical_column_creator"],
        )
        creator_step = analysis["preprocessing"][1]
        self.assertEqual(creator_step["parameters"]["strategy"], "filter_rules")
        self.assertEqual(creator_step["parameters"]["code"], "cognitive_profile")
        self.assertIn("Preserved", creator_step["parameters"]["rules"])

    def test_pipeline_logistic_regression_can_use_derived_variable(self):
        transport = MagicMock()
        transport.post.return_value = {"status": "success", "result": {"summary": {}}}
        dm = _dm(transport)
        age = Var("age", label="Age")
        diagnosis = Var("diagnosis", label="Diagnosis")
        mmse = Var("mmse", label="MMSE")
        analysis_set = AnalysisSet(
            data_model=dm,
            datasets=[_dataset("adni", "ADNI")],
            variables=[age, diagnosis, mmse],
        )
        creator = CategoricalColumnCreator(
            label="Cognitive profile",
            rules={"Preserved": F(mmse) >= 27},
        )

        Pipeline(
            analysis_set=analysis_set,
            new_columns=[creator],
        ).logistic_regression(x=[age, creator.variable], y=diagnosis, positive_class="AD")

        analysis = transport.post.call_args.args[1]["analysis"]
        self.assertEqual(analysis["algorithm"]["x"], ["age", "cognitive_profile"])
        self.assertNotIn("cognitive_profile", analysis["inputdata"]["variables"])
        self.assertIn("age", analysis["inputdata"]["variables"])
        self.assertIn("mmse", analysis["inputdata"]["variables"])

    def test_available_algorithms_lists_all_wrappers(self):
        transport = MagicMock()
        dm = _dm(transport)
        age = Var("age", label="Age")
        analysis_set = AnalysisSet(
            data_model=dm,
            datasets=[_dataset("adni", "ADNI")],
            variables=[age],
        )
        methods = Pipeline(analysis_set=analysis_set).available_algorithms()
        self.assertEqual(len(methods), len(PIPELINE_BACKEND_ALGORITHMS))
        self.assertIn("anova_oneway", methods)
        self.assertIn("pca", methods)
        self.assertIn("cox_regression_classical", methods)

    def test_anova_oneway_posts_expected_payload(self):
        transport = MagicMock()
        transport.post.return_value = {"status": "success", "result": {}}
        dm = _dm(transport)
        age = Var("age", label="Age")
        diagnosis = Var("diagnosis", label="Diagnosis")
        analysis_set = AnalysisSet(
            data_model=dm,
            datasets=[_dataset("adni", "ADNI")],
            variables=[age, diagnosis],
        )

        Pipeline(analysis_set=analysis_set).anova_oneway(group_by=diagnosis, outcome=age)

        analysis = transport.post.call_args.args[1]["analysis"]
        self.assertEqual(analysis["algorithm"]["name"], "anova_oneway")
        self.assertEqual(analysis["algorithm"]["x"], ["diagnosis"])
        self.assertEqual(analysis["algorithm"]["y"], ["age"])

    def test_pipeline_serializes_longitudinal_preprocessing(self):
        transport = MagicMock()
        transport.post.return_value = {"status": "success", "result": {}}
        dm = _dm(transport)
        age = Var("age", label="Age")
        mmse = Var("mmse", label="MMSE")
        analysis_set = AnalysisSet(
            data_model=dm,
            datasets=[_dataset("adni", "ADNI")],
            variables=[age, mmse],
        )
        transformer = LongitudinalTransformer(
            visit1="BL",
            visit2="FL1",
            strategies={age: "diff", mmse: "second"},
        )

        Pipeline(
            analysis_set=analysis_set,
            longitudinal=transformer,
            handle_missing=MissingValuesHandler(strategies={age: "median"}),
        ).paired_t_test(measurement_1=age, measurement_2=mmse)

        analysis = transport.post.call_args.args[1]["analysis"]
        self.assertEqual(
            [step["name"] for step in analysis["preprocessing"]],
            ["longitudinal_transformer", "missing_values_handler"],
        )
        self.assertEqual(analysis["algorithm"]["name"], "ttest_paired")
        variables = analysis["inputdata"]["variables"]
        self.assertIn("dataset", variables)
        self.assertIn("subjectid", variables)
        self.assertIn("visitid", variables)
        self.assertIn("age", variables)
        self.assertIn("mmse", variables)


    def test_kmeans_sends_manual_selection_parameters(self):
        transport = MagicMock()
        transport.post.return_value = {"status": "success", "result": {}}
        dm = _dm(transport)
        age = Var("age", label="Age")
        mmse = Var("mmse", label="MMSE")
        analysis_set = AnalysisSet(
            data_model=dm,
            datasets=[_dataset("adni", "ADNI")],
            variables=[age, mmse],
        )

        Pipeline(analysis_set=analysis_set).kmeans(features=[age, mmse])

        analysis = transport.post.call_args.args[1]["analysis"]
        self.assertEqual(analysis["algorithm"]["name"], "kmeans")
        self.assertEqual(analysis["algorithm"]["y"], ["age", "mmse"])
        self.assertEqual(
            analysis["algorithm"]["parameters"],
            {"k_selection": "manual", "maxiter": 100, "tol": 0.0001},
        )

    def test_kmeans_sends_elbow_selection_parameters(self):
        transport = MagicMock()
        transport.post.return_value = {"status": "success", "result": {}}
        dm = _dm(transport)
        age = Var("age", label="Age")
        mmse = Var("mmse", label="MMSE")
        analysis_set = AnalysisSet(
            data_model=dm,
            datasets=[_dataset("adni", "ADNI")],
            variables=[age, mmse],
        )

        Pipeline(analysis_set=analysis_set).kmeans(
            features=[age, mmse],
            k_selection="elbow",
            k_min=2,
            k_max=6,
        )

        parameters = transport.post.call_args.args[1]["analysis"]["algorithm"]["parameters"]
        self.assertEqual(
            parameters,
            {"k_selection": "elbow", "k_min": 2, "k_max": 6, "maxiter": 100, "tol": 0.0001},
        )

    def test_standardized_mean_difference_posts_expected_payload(self):
        transport = MagicMock()
        transport.post.return_value = {"status": "success", "result": {"comparisons": []}}
        dm = _dm(transport)
        age = Var("age", label="Age")
        diagnosis = Var("diagnosis", label="Diagnosis")
        analysis_set = AnalysisSet(
            data_model=dm,
            datasets=[_dataset("adni", "ADNI")],
            variables=[age, diagnosis],
        )

        result = Pipeline(analysis_set=analysis_set).standardized_mean_difference(
            variable=age,
            group_by=diagnosis,
        )

        analysis = transport.post.call_args.args[1]["analysis"]
        self.assertEqual(analysis["algorithm"]["name"], "standardized_mean_difference")
        self.assertEqual(analysis["algorithm"]["x"], ["diagnosis"])
        self.assertEqual(analysis["algorithm"]["y"], ["age"])
        self.assertEqual(analysis["algorithm"]["parameters"], {})
        self.assertEqual(result.result_type, "standardized_mean_difference")


REUSABLE_PREPROCESSING = {
    "schema_version": "1",
    "preprocessing_name": "kmeans_cluster_creator",
    "cluster_variables": ["a", "b"],
    "centers": {
        "cluster_0": {"a": 1.0, "b": 2.0},
        "cluster_1": {"a": 3.0, "b": 4.0},
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
            "cardinality": 2,
            "selection_rule": "nearest_center",
        }
    ],
    "cluster_choices": [
        {"cluster_id": "cluster_0", "label": "Cluster 0"},
        {"cluster_id": "cluster_1", "label": "Cluster 1"},
    ],
}


def _kmeans_result():
    return Result(raw={"reusable_preprocessing": REUSABLE_PREPROCESSING}, result_type="kmeans")


class TestPipelineKMeansClusterCreator(unittest.TestCase):
    def _pipeline_inputs(self, transport):
        dm = _dm(transport)
        a = Var("a", label="A")
        b = Var("b", label="B")
        diagnosis = Var("diagnosis", label="Diagnosis")
        analysis_set = AnalysisSet(
            data_model=dm,
            datasets=[_dataset("adni", "ADNI")],
            variables=[a, b, diagnosis],
        )
        return a, b, diagnosis, analysis_set

    def test_cluster_variables_are_requested_and_dropped_by_default(self):
        transport = MagicMock()
        transport.post.return_value = {"status": "success", "result": {}}
        a, _, diagnosis, analysis_set = self._pipeline_inputs(transport)
        creator = KMeansClusterCreator(label="Cluster", source=_kmeans_result())
        handler = MissingValuesHandler(strategies={a: "mean"})

        Pipeline(
            analysis_set=analysis_set,
            handle_missing=handler,
            new_columns=[creator],
        ).chi_square_test(x=creator.variable, y=diagnosis)

        analysis = transport.post.call_args.args[1]["analysis"]
        variables = analysis["inputdata"]["variables"]
        self.assertIn("a", variables)
        self.assertIn("b", variables)
        self.assertNotIn("cluster", variables)
        self.assertEqual(
            [step["name"] for step in analysis["preprocessing"]],
            ["missing_values_handler", "kmeans_cluster_creator"],
        )
        self.assertEqual(analysis["preprocessing"][0]["parameters"]["strategies"], {"a": "mean", "b": "drop"})
        self.assertEqual(handler.spec()["parameters"]["strategies"], {"a": "mean"})

    def test_missing_values_handler_is_added_for_cluster_variables(self):
        transport = MagicMock()
        transport.post.return_value = {"status": "success", "result": {}}
        _, _, diagnosis, analysis_set = self._pipeline_inputs(transport)
        creator = KMeansClusterCreator(label="Cluster", source=_kmeans_result())

        Pipeline(analysis_set=analysis_set, new_columns=[creator]).chi_square_test(
            x=creator.variable,
            y=diagnosis,
        )

        analysis = transport.post.call_args.args[1]["analysis"]
        self.assertEqual(
            [step["name"] for step in analysis["preprocessing"]],
            ["missing_values_handler", "kmeans_cluster_creator"],
        )
        self.assertEqual(analysis["preprocessing"][0]["parameters"]["strategies"], {"a": "drop", "b": "drop"})

    def test_summary_shows_cluster_variable_drops(self):
        _, _, _, analysis_set = self._pipeline_inputs(MagicMock())
        creator = KMeansClusterCreator(label="Cluster", source=_kmeans_result())

        summary = Pipeline(analysis_set=analysis_set, new_columns=[creator])._preprocessing_user_summary()

        self.assertEqual(summary[0]["name"], "missing_values_handler")
        self.assertEqual(summary[0]["strategies"], {"a": "drop", "b": "drop"})


if __name__ == "__main__":
    unittest.main()
