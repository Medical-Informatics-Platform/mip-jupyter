import unittest

from mip.exceptions import UnsupportedOperationError
from mip.results import ModelResult
from mip.sklearn import feature_schema_from_logistic_result


class TestSklearnExport(unittest.TestCase):
    def test_helper_module_exposes_feature_schema(self):
        schema = feature_schema_from_logistic_result({"summary": {"feature_names": ["Intercept", "age"], "coefficients": [0.1, 0.2]}})
        self.assertEqual(schema["feature_names"], ["age"])

    def test_feature_schema_uses_backend_features(self):
        result = ModelResult(
            raw={"summary": {"feature_names": ["Intercept", "age", "mmse"], "coefficients": [0.1, 0.2, -0.3]}},
            result_type="logistic_regression",
            positive_class="AD",
        )
        self.assertEqual(result.feature_schema()["feature_names"], ["age", "mmse"])

    def test_to_sklearn_exports_real_model_when_dependency_available(self):
        try:
            import sklearn  # noqa: F401
        except Exception:
            self.skipTest("scikit-learn is not installed")

        result = ModelResult(
            raw={"summary": {"feature_names": ["Intercept", "age"], "coefficients": [0.1, 0.5]}},
            result_type="logistic_regression",
            positive_class="AD",
        )
        model = result.to_sklearn()
        self.assertEqual(list(model.feature_names_in_), ["age"])
        self.assertEqual(model.n_features_in_, 1)

    def test_model_result_to_sklearn_requires_feature_schema(self):
        result = ModelResult(raw={"summary": {}}, result_type="logistic_regression")
        with self.assertRaises(UnsupportedOperationError):
            result.to_sklearn()

    def test_missing_export_data_raises(self):
        result = ModelResult(raw={"summary": {}}, result_type="logistic_regression")
        with self.assertRaises(UnsupportedOperationError):
            result.to_sklearn()


if __name__ == "__main__":
    unittest.main()
