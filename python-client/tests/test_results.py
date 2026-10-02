import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

import pandas as pd

from mip.exceptions import UnsupportedOperationError
from mip.results import ModelResult
from mip.results import Result
from mip.results import _histogram_data


class TestResults(unittest.TestCase):
    def test_summary_returns_raw(self):
        result = Result(raw={"a": 1}, payload={"result": {"a": 1}})
        self.assertEqual(result.summary(), {"a": 1})
        self.assertEqual(result.raw, {"a": 1})
        self.assertEqual(result.payload, {"result": {"a": 1}})

    def test_plot_raises_for_non_plot_result(self):
        with self.assertRaises(UnsupportedOperationError):
            Result(raw={}, result_type="kmeans").plot()

    def test_histogram_data_reads_list_payload(self):
        data = _histogram_data({"histogram": [{"var": "age", "bins": [1, 2, 3], "counts": [4, 5]}]})
        self.assertEqual(data, ([1, 2, 3], [4, 5]))

    def test_histogram_highlights_and_to_frame(self):
        result = Result(
            raw={"variable": "Age", "bins": [40, 50, 60], "counts": [10, 20, 5]},
            result_type="histogram",
        )
        highlights = result.highlights()
        self.assertEqual(highlights["bins"], 3)
        self.assertEqual(highlights["total_count"], 35.0)
        frame = result.to_frame()
        self.assertEqual(frame["bin"].tolist(), [40, 50, 60])
        self.assertEqual(frame["count"].tolist(), [10, 20, 5])
        html = result._repr_html_()
        self.assertIn("Preview", html)
        self.assertIn("histogram", html.lower())
        self.assertIn(".plot()", html)

    def test_describe_to_frame(self):
        result = Result(
            raw={
                "featurewise": [
                    {
                        "variable": "Age",
                        "dataset": "ADNI",
                        "data": {"num_dtps": 100, "mean": 72.5, "std": 8.1, "min": 50, "max": 90},
                    }
                ]
            },
            result_type="describe",
        )
        frame = result.to_frame()
        self.assertEqual(frame.iloc[0]["variable"], "Age")
        self.assertEqual(frame.iloc[0]["n"], 100)
        self.assertIn("Age", result._repr_html_())

    def test_t_test_highlights(self):
        result = Result(
            raw={"t_stat": 2.1, "p": 0.04, "mean_diff": 1.5, "cohens_d": 0.3, "ci_lower": 0.2, "ci_upper": 2.8},
            result_type="t_test",
        )
        highlights = result.highlights()
        self.assertEqual(highlights["p"], 0.04)
        frame = result.to_frame()
        self.assertEqual(frame.iloc[0]["t_stat"], 2.1)
        self.assertEqual(frame.iloc[0]["ci_lower"], 0.2)

    def test_chi_square_to_frame(self):
        result = Result(raw={"chi2": 9.2, "p_value": 0.002, "dof": 2}, result_type="chi_square_test")
        frame = result.to_frame()
        self.assertEqual(frame.iloc[0]["chi2"], 9.2)
        self.assertEqual(frame.iloc[0]["p_value"], 0.002)

    def test_logistic_to_frame_and_model_card(self):
        result = ModelResult(
            raw={
                "summary": {
                    "n_obs": 200,
                    "feature_names": ["Intercept", "Age", "Sex"],
                    "coefficients": [0.1, 0.2, -0.3],
                    "pvalues": [0.5, 0.01, 0.2],
                    "lower_ci": [-0.1, 0.05, -0.6],
                    "upper_ci": [0.3, 0.35, 0.0],
                }
            },
            result_type="logistic_regression",
        )
        self.assertEqual(result.highlights()["n_obs"], 200)
        frame = result.to_frame()
        self.assertEqual(frame["feature"].tolist(), ["Intercept", "Age", "Sex"])
        self.assertEqual(frame.iloc[1]["p"], 0.01)
        self.assertIn("odds_ratio", frame.columns)
        html = result._repr_html_()
        self.assertIn("Age", html)
        self.assertIn(".to_sklearn()", html)
        self.assertIn(".plot()", html)

    def test_to_frame_raises_when_unsupported(self):
        with self.assertRaises(UnsupportedOperationError):
            Result(raw={"opaque": True}, result_type="kmeans").to_frame()

    def test_kmeans_to_frame_and_highlights(self):
        result = Result(
            raw={
                "variables": ["a", "b"],
                "clusters": [
                    {
                        "cluster_id": "cluster_0",
                        "label": "Cluster 0",
                        "size_interval": "10-14",
                        "center": {"a": 1.0, "b": 2.0},
                    },
                    {
                        "cluster_id": "cluster_1",
                        "label": "Cluster 1",
                        "size_interval": "10-14",
                        "center": {"a": 3.0, "b": 4.0},
                    },
                ],
                "selected_k": 2,
                "k_selection": "manual",
                "n_obs_interval": "20-24",
                "converged": True,
                "n_iter": 3,
                "elbow": None,
                "reusable_preprocessing": None,
            },
            result_type="kmeans",
        )
        frame = result.to_frame()
        self.assertEqual(len(frame), 2)
        self.assertIn("cluster", frame.columns)
        self.assertIn("size", frame.columns)
        self.assertIn("a", frame.columns)
        self.assertIn("b", frame.columns)
        self.assertEqual(frame["cluster_id"].tolist(), ["cluster_0", "cluster_1"])
        self.assertEqual(frame["cluster"].tolist(), ["Cluster 0", "Cluster 1"])
        self.assertEqual(frame["size"].tolist(), ["10-14", "10-14"])
        self.assertEqual(frame["a"].tolist(), [1.0, 3.0])
        highlights = result.highlights()
        self.assertEqual(highlights["selected_k"], 2)
        self.assertEqual(highlights["k_selection"], "manual")
        self.assertEqual(highlights["n_obs_interval"], "20-24")
        self.assertEqual(highlights["converged"], True)
        self.assertEqual(highlights["n_iter"], 3)

    def test_kmeans_center_feature_named_like_identity_column_is_prefixed(self):
        result = Result(
            raw={"clusters": [{"cluster_id": "cluster_0", "label": "Cluster 0", "size_interval": "10-14", "center": {"size": 2.0}}]},
            result_type="kmeans",
        )
        row = result.to_frame().iloc[0]
        self.assertEqual(row["size"], "10-14")
        self.assertEqual(row["center_size"], 2.0)

    def test_standardized_mean_difference_to_frame(self):
        result = Result(
            raw={"comparisons": [{"group1": "x", "group2": "y", "smd": 0.5}]},
            result_type="standardized_mean_difference",
        )
        frame = result.to_frame()
        self.assertEqual(len(frame), 1)
        self.assertEqual(frame.iloc[0]["smd"], 0.5)
        self.assertEqual(frame.iloc[0]["group1"], "x")
        self.assertEqual(frame.iloc[0]["group2"], "y")

    def test_plot_labels_histogram(self):
        result = Result(
            raw={"variable": "MMSE", "bins": ["a", "b"], "counts": [3, 7]},
            result_type="histogram",
        )
        axis = MagicMock()
        figure = MagicMock()
        with patch("matplotlib.pyplot.subplots", return_value=(figure, axis)):
            returned = result.plot()
        self.assertIs(returned, axis)
        axis.bar.assert_called_once()
        axis.set_ylabel.assert_called_with("count")
        axis.set_xlabel.assert_called_with("MMSE")
        axis.set_title.assert_called_with("Histogram: MMSE")
        figure.tight_layout.assert_called_once()

    def test_plot_histogram_labels_bars_from_bin_edges(self):
        result = Result(
            raw={"variable": "Age", "bins": [20, 40, 60, 80], "counts": [3, 7, 5]},
            result_type="histogram",
        )
        axis = MagicMock()
        with patch("matplotlib.pyplot.subplots", return_value=(MagicMock(), axis)):
            result.plot()
        self.assertEqual(axis.bar.call_args.kwargs["tick_label"], ["20-40", "40-60", "60-80"])

    def test_plot_logistic_forest(self):
        result = ModelResult(
            raw={
                "indep_vars": ["Intercept", "Age"],
                "summary": {
                    "coefficients": [0.0, 0.693147],
                    "lower_ci": [-0.1, 0.2],
                    "upper_ci": [0.1, 1.2],
                    "pvalues": [1.0, 0.01],
                },
            },
            result_type="logistic_regression",
        )
        axis = MagicMock()
        figure = MagicMock()
        with patch("matplotlib.pyplot.subplots", return_value=(figure, axis)):
            returned = result.plot()
        self.assertIs(returned, axis)
        axis.errorbar.assert_called_once()
        axis.set_xscale.assert_called_with("log")

    def test_plot_describe_means(self):
        result = Result(
            raw={
                "featurewise": [
                    {"variable": "Age", "dataset": "ADNI", "data": {"mean": 70.0}},
                    {"variable": "MMSE", "dataset": "ADNI", "data": {"mean": 24.0}},
                ]
            },
            result_type="describe",
        )
        axis = MagicMock()
        figure = MagicMock()
        with patch("matplotlib.pyplot.subplots", return_value=(figure, axis)):
            returned = result.plot()
        self.assertIs(returned, axis)
        axis.barh.assert_called_once()

    def test_histogram_highlights_tolerate_null_counts(self):
        result = Result(
            raw={"bins": ["ACS", "PCS", "other"], "counts": [10, None, 2]},
            result_type="histogram",
        )
        self.assertEqual(result.highlights()["total_count"], 12.0)
        axis = MagicMock()
        figure = MagicMock()
        with patch("matplotlib.pyplot.subplots", return_value=(figure, axis)):
            result.plot()
        axis.bar.assert_called_once()
        plotted_counts = axis.bar.call_args[0][1]
        self.assertEqual(list(plotted_counts), [10.0, 0.0, 2.0])

    def test_backend_result_types_map_to_frames(self):
        t_result = Result(
            raw={"t_stat": 2.1, "p": 0.04, "mean_diff": 1.5, "ci_lower": 0.2, "ci_upper": 2.8},
            result_type="ttest_independent",
        )
        self.assertEqual(t_result.to_frame().iloc[0]["t_stat"], 2.1)
        self.assertIn(".plot()", t_result._repr_html_())

        chi = Result(raw={"chi2": 9.2, "p_value": 0.002, "dof": 2}, result_type="chi_squared")
        self.assertEqual(chi.to_frame().iloc[0]["chi2"], 9.2)
        axis = MagicMock()
        figure = MagicMock()
        with patch("matplotlib.pyplot.subplots", return_value=(figure, axis)):
            chi.plot()
        axis.bar.assert_called_once()

    def test_to_frame_keeps_numeric_dtypes_for_styler(self):
        result = Result(
            raw={"u_stat": 84037773.0, "z_score": 18.46, "p_value": 1e-8, "n1": 19952, "n2": 7356},
            result_type="binned_mann_whitney_u_test",
        )
        frame = result.to_frame()
        self.assertTrue(pd.api.types.is_numeric_dtype(frame["u_stat"]))
        self.assertTrue(pd.api.types.is_numeric_dtype(frame["p_value"]))
        # Styler must not raise Unknown format code 'f' for str.
        html = frame.style.format({"u_stat": "{:.2f}", "p_value": "{:.4g}"}).to_html()
        self.assertIn("84037773", html)


if __name__ == "__main__":
    unittest.main()
