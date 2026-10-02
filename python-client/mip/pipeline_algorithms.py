"""Typed Pipeline algorithm methods mapped to Exaflow backend names."""

from __future__ import annotations

from typing import Any
from typing import Mapping
from typing import Sequence

from .labels import public_label
from .request_builder import code
from .results import ModelResult
from .results import Result


def _code_map(values: Mapping[Any, Any]) -> dict[str, Any]:
    return {code(key): value for key, value in values.items()}


class PipelineAlgorithmsMixin:
    """Exaflow analysis algorithm wrappers for Pipeline."""

    def describe(self, mode: str = "transient") -> Result:
        return self._execute_algorithm(
            "describe",
            algorithm_y=self.analysis_set.variables,
            parameters={},
            mode=mode,
            name_for_ui="Describe",
        )

    def histogram(
        self,
        variable: Any,
        *,
        bins: int | None = None,
        histogram_type: str | None = None,
        mode: str = "transient",
    ) -> Result:
        parameters: dict[str, Any] = {}
        if bins is not None:
            parameters["bins"] = bins
        if histogram_type is not None:
            parameters["histogram_type"] = histogram_type
        return self._execute_algorithm(
            "histogram",
            algorithm_y=[variable],
            parameters=parameters,
            mode=mode,
            name_for_ui=f"Histogram: {public_label(variable)}",
            result_type="histogram",
        )

    def t_test(
        self,
        *,
        variable: Any,
        group_by: Any,
        group_a: Any,
        group_b: Any,
        alt_hypothesis: str = "two-sided",
        alpha: float = 0.05,
        mode: str = "transient",
    ) -> Result:
        return self._execute_algorithm(
            "ttest_independent",
            algorithm_x=[group_by],
            algorithm_y=[variable],
            parameters={
                "alt_hypothesis": alt_hypothesis,
                "alpha": alpha,
                "groupA": group_a,
                "groupB": group_b,
            },
            mode=mode,
            name_for_ui=f"T-test: {public_label(variable)}",
            result_type="t_test",
        )

    def one_sample_t_test(
        self,
        *,
        variable: Any,
        mu: float = 0.0,
        alt_hypothesis: str = "two-sided",
        alpha: float = 0.05,
        mode: str = "transient",
    ) -> Result:
        return self._execute_algorithm(
            "ttest_onesample",
            algorithm_y=[variable],
            parameters={
                "alt_hypothesis": alt_hypothesis,
                "alpha": alpha,
                "mu": mu,
            },
            mode=mode,
            name_for_ui=f"One-sample t-test: {public_label(variable)}",
            result_type="one_sample_t_test",
        )

    def paired_t_test(
        self,
        *,
        measurement_1: Any,
        measurement_2: Any,
        alt_hypothesis: str = "two-sided",
        alpha: float = 0.05,
        mode: str = "transient",
    ) -> Result:
        return self._execute_algorithm(
            "ttest_paired",
            algorithm_x=[measurement_2],
            algorithm_y=[measurement_1],
            parameters={
                "alt_hypothesis": alt_hypothesis,
                "alpha": alpha,
            },
            mode=mode,
            name_for_ui=(
                f"Paired t-test: {public_label(measurement_1)} vs {public_label(measurement_2)}"
            ),
            result_type="paired_t_test",
        )

    def pearson_correlation(
        self,
        *,
        x: Any,
        y: Any,
        alpha: float = 0.95,
        mode: str = "transient",
    ) -> Result:
        return self._execute_algorithm(
            "pearson_correlation",
            algorithm_x=[x],
            algorithm_y=[y],
            parameters={"alpha": alpha},
            mode=mode,
            name_for_ui=f"Pearson correlation: {public_label(x)} vs {public_label(y)}",
        )

    def chi_square_test(self, *, x: Any, y: Any, mode: str = "transient") -> Result:
        return self._execute_algorithm(
            "chi_squared",
            algorithm_x=[x],
            algorithm_y=[y],
            parameters={},
            mode=mode,
            name_for_ui=f"Chi-square test: {public_label(x)} vs {public_label(y)}",
            result_type="chi_square_test",
        )

    def fisher_exact(self, *, x: Any, y: Any, mode: str = "transient") -> Result:
        return self._execute_algorithm(
            "fisher_exact",
            algorithm_x=[x],
            algorithm_y=[y],
            parameters={},
            mode=mode,
            name_for_ui=f"Fisher exact test: {public_label(x)} vs {public_label(y)}",
            result_type="fisher_exact",
        )

    def quartiles(
        self,
        *,
        variable: Any,
        num_bins: int | None = None,
        mode: str = "transient",
    ) -> Result:
        parameters: dict[str, Any] = {}
        if num_bins is not None:
            parameters["num_bins"] = num_bins
        return self._execute_algorithm(
            "quartiles",
            algorithm_y=[variable],
            parameters=parameters,
            mode=mode,
            name_for_ui=f"Quartiles: {public_label(variable)}",
        )

    def anova_oneway(
        self,
        *,
        group_by: Any,
        outcome: Any,
        mode: str = "transient",
    ) -> Result:
        return self._execute_algorithm(
            "anova_oneway",
            algorithm_x=[group_by],
            algorithm_y=[outcome],
            parameters={},
            mode=mode,
            name_for_ui=f"One-way ANOVA: {public_label(outcome)}",
        )

    def anova_twoway(
        self,
        *,
        factor_a: Any,
        factor_b: Any,
        outcome: Any,
        sstype: int = 2,
        mode: str = "transient",
    ) -> Result:
        return self._execute_algorithm(
            "anova_twoway",
            algorithm_x=[factor_a, factor_b],
            algorithm_y=[outcome],
            parameters={"sstype": sstype},
            mode=mode,
            name_for_ui=f"Two-way ANOVA: {public_label(outcome)}",
        )

    def mann_whitney_u_test(
        self,
        *,
        variable: Any,
        group_by: Any,
        group_a: Any,
        group_b: Any,
        alt_hypothesis: str = "two-sided",
        num_bins: int | None = None,
        mode: str = "transient",
    ) -> Result:
        parameters: dict[str, Any] = {
            "alt_hypothesis": alt_hypothesis,
            "groupA": group_a,
            "groupB": group_b,
        }
        if num_bins is not None:
            parameters["num_bins"] = num_bins
        return self._execute_algorithm(
            "binned_mann_whitney_u_test",
            algorithm_x=[group_by],
            algorithm_y=[variable],
            parameters=parameters,
            mode=mode,
            name_for_ui=f"Mann-Whitney U test: {public_label(variable)}",
            result_type="mann_whitney_u_test",
        )

    def standardized_mean_difference(
        self,
        *,
        variable: Any,
        group_by: Any,
        mode: str = "transient",
    ) -> Result:
        return self._execute_algorithm(
            "standardized_mean_difference",
            algorithm_x=[group_by],
            algorithm_y=[variable],
            parameters={},
            mode=mode,
            name_for_ui=f"Standardized mean difference: {public_label(variable)}",
        )

    def outlier_report(
        self,
        *,
        variables: Sequence[Any],
        strategies: Mapping[Any, str],
        tails: Mapping[Any, str] | None = None,
        folds: Mapping[Any, float] | None = None,
        additional_variables: Sequence[Any] | None = None,
        mode: str = "transient",
    ) -> Result:
        parameters: dict[str, Any] = {
            "strategies": _code_map(strategies),
        }
        if tails:
            parameters["tails"] = _code_map(tails)
        if folds:
            parameters["folds"] = _code_map(folds)
        label = ", ".join(public_label(item) for item in variables[:3])
        if len(variables) > 3:
            label += ", ..."
        return self._execute_algorithm(
            "outlier_report",
            algorithm_x=list(additional_variables or []),
            algorithm_y=list(variables),
            parameters=parameters,
            mode=mode,
            name_for_ui=f"Outlier report: {label}",
        )

    def logistic_regression(
        self,
        *,
        x: Sequence[Any],
        y: Any,
        positive_class: Any,
        mode: str = "transient",
    ) -> ModelResult:
        return self._execute_algorithm(
            "logistic_regression",
            algorithm_x=list(x),
            algorithm_y=[y],
            parameters={"positive_class": positive_class},
            mode=mode,
            name_for_ui=f"Logistic regression: {public_label(y)}",
            result_class=ModelResult,
            result_type="logistic_regression",
            result_kwargs={"positive_class": positive_class},
        )

    def logistic_regression_cv(
        self,
        *,
        x: Sequence[Any],
        y: Any,
        positive_class: Any,
        n_splits: int = 5,
        mode: str = "transient",
    ) -> Result:
        return self._execute_algorithm(
            "logistic_regression_cv",
            algorithm_x=list(x),
            algorithm_y=[y],
            parameters={"positive_class": positive_class, "n_splits": n_splits},
            mode=mode,
            name_for_ui=f"Logistic regression CV: {public_label(y)}",
        )

    def linear_regression(
        self,
        *,
        x: Sequence[Any],
        y: Any,
        mode: str = "transient",
    ) -> Result:
        return self._execute_algorithm(
            "linear_regression",
            algorithm_x=list(x),
            algorithm_y=[y],
            parameters={},
            mode=mode,
            name_for_ui=f"Linear regression: {public_label(y)}",
        )

    def linear_regression_cv(
        self,
        *,
        x: Sequence[Any],
        y: Any,
        n_splits: int = 5,
        mode: str = "transient",
    ) -> Result:
        return self._execute_algorithm(
            "linear_regression_cv",
            algorithm_x=list(x),
            algorithm_y=[y],
            parameters={"n_splits": n_splits},
            mode=mode,
            name_for_ui=f"Linear regression CV: {public_label(y)}",
        )

    def cox_regression_classical(
        self,
        *,
        time: Any,
        event_var: Any,
        covariates: Sequence[Any],
        positive_class: Any | None = None,
        mode: str = "transient",
    ) -> Result:
        x = [event_var, *covariates]
        parameters: dict[str, Any] = {"event_var": code(event_var)}
        if positive_class is not None:
            parameters["positive_class"] = positive_class
        return self._execute_algorithm(
            "cox_regression_classical",
            algorithm_x=x,
            algorithm_y=[time],
            parameters=parameters,
            mode=mode,
            name_for_ui=f"Cox regression: {public_label(time)}",
        )

    def cox_regression_stacked(
        self,
        *,
        time: Any,
        event_var: Any,
        covariates: Sequence[Any],
        positive_class: Any | None = None,
        time_grid_strategy: str = "distinct_event_times",
        n_time_bins: int | None = None,
        mode: str = "transient",
    ) -> Result:
        x = [event_var, *covariates]
        parameters: dict[str, Any] = {
            "event_var": code(event_var),
            "time_grid_strategy": time_grid_strategy,
        }
        if positive_class is not None:
            parameters["positive_class"] = positive_class
        if n_time_bins is not None:
            parameters["n_time_bins"] = n_time_bins
        return self._execute_algorithm(
            "cox_regression_stacked",
            algorithm_x=x,
            algorithm_y=[time],
            parameters=parameters,
            mode=mode,
            name_for_ui=f"Stacked Cox regression: {public_label(time)}",
        )

    def lmm(
        self,
        *,
        outcome: Any,
        covariates: Sequence[Any],
        grouping_var: Sequence[Any],
        mode: str = "transient",
    ) -> Result:
        x = [*covariates, *grouping_var]
        return self._execute_algorithm(
            "lmm",
            algorithm_x=x,
            algorithm_y=[outcome],
            parameters={"grouping_var": [code(item) for item in grouping_var]},
            mode=mode,
            name_for_ui=f"Linear mixed model: {public_label(outcome)}",
        )

    def glmm_binary(
        self,
        *,
        outcome: Any,
        covariates: Sequence[Any],
        grouping_var: Sequence[Any],
        positive_class: Any,
        mode: str = "transient",
    ) -> Result:
        x = [*covariates, *grouping_var]
        return self._execute_algorithm(
            "glmm_binary",
            algorithm_x=x,
            algorithm_y=[outcome],
            parameters={
                "positive_class": positive_class,
                "grouping_var": [code(item) for item in grouping_var],
            },
            mode=mode,
            name_for_ui=f"GLMM binary: {public_label(outcome)}",
        )

    def glmm_ordinal(
        self,
        *,
        outcome: Any,
        covariates: Sequence[Any],
        grouping_var: Sequence[Any],
        category_order: Sequence[Any],
        mode: str = "transient",
    ) -> Result:
        x = [*covariates, *grouping_var]
        return self._execute_algorithm(
            "glmm_ordinal",
            algorithm_x=x,
            algorithm_y=[outcome],
            parameters={
                "grouping_var": [code(item) for item in grouping_var],
                "category_order": list(category_order),
            },
            mode=mode,
            name_for_ui=f"GLMM ordinal: {public_label(outcome)}",
        )

    def linear_svm(
        self,
        *,
        features: Sequence[Any],
        target: Any,
        gamma: float = 0.1,
        c: float = 1.0,
        mode: str = "transient",
    ) -> Result:
        return self._execute_algorithm(
            "linear_svm",
            algorithm_x=list(features),
            algorithm_y=[target],
            parameters={"gamma": gamma, "C": c},
            mode=mode,
            name_for_ui=f"Linear SVM: {public_label(target)}",
        )

    def kmeans(
        self,
        *,
        features: Sequence[Any],
        k_selection: str = "manual",
        k: int | None = None,
        k_min: int | None = None,
        k_max: int | None = None,
        maxiter: int = 100,
        tol: float = 0.0001,
        init_method: str | None = None,
        n_init: int | None = None,
        random_state: int | None = None,
        mode: str = "transient",
    ) -> Result:
        parameters: dict[str, Any] = {
            "k_selection": k_selection,
            "maxiter": maxiter,
            "tol": tol,
        }
        if k is not None:
            parameters["k"] = k
        if k_min is not None:
            parameters["k_min"] = k_min
        if k_max is not None:
            parameters["k_max"] = k_max
        if init_method is not None:
            parameters["init_method"] = init_method
        if n_init is not None:
            parameters["n_init"] = n_init
        if random_state is not None:
            parameters["random_state"] = random_state
        return self._execute_algorithm(
            "kmeans",
            algorithm_y=list(features),
            parameters=parameters,
            mode=mode,
            name_for_ui="K-means clustering",
        )

    def pca(
        self,
        *,
        variables: Sequence[Any],
        mode: str = "transient",
    ) -> Result:
        return self._execute_algorithm(
            "pca",
            algorithm_y=list(variables),
            parameters={},
            mode=mode,
            name_for_ui="PCA",
        )

    def pca_with_transformation(
        self,
        *,
        variables: Sequence[Any],
        data_transformation: Mapping[str, Sequence[Any]] | None = None,
        mode: str = "transient",
    ) -> Result:
        parameters: dict[str, Any] = {}
        if data_transformation:
            parameters["data_transformation"] = {
                key: [code(item) for item in values]
                for key, values in data_transformation.items()
            }
        return self._execute_algorithm(
            "pca_with_transformation",
            algorithm_y=list(variables),
            parameters=parameters,
            mode=mode,
            name_for_ui="PCA with transformation",
        )

    def naive_bayes_gaussian(
        self,
        *,
        features: Sequence[Any],
        target: Any,
        mode: str = "transient",
    ) -> Result:
        return self._execute_algorithm(
            "naive_bayes_gaussian",
            algorithm_x=list(features),
            algorithm_y=[target],
            parameters={},
            mode=mode,
            name_for_ui=f"Naive Bayes (Gaussian): {public_label(target)}",
        )

    def naive_bayes_categorical(
        self,
        *,
        features: Sequence[Any],
        target: Any,
        mode: str = "transient",
    ) -> Result:
        return self._execute_algorithm(
            "naive_bayes_categorical",
            algorithm_x=list(features),
            algorithm_y=[target],
            parameters={},
            mode=mode,
            name_for_ui=f"Naive Bayes (categorical): {public_label(target)}",
        )

    def naive_bayes_gaussian_cv(
        self,
        *,
        features: Sequence[Any],
        target: Any,
        n_splits: int = 5,
        mode: str = "transient",
    ) -> Result:
        return self._execute_algorithm(
            "naive_bayes_gaussian_cv",
            algorithm_x=list(features),
            algorithm_y=[target],
            parameters={"n_splits": n_splits},
            mode=mode,
            name_for_ui=f"Naive Bayes CV (Gaussian): {public_label(target)}",
        )

    def naive_bayes_categorical_cv(
        self,
        *,
        features: Sequence[Any],
        target: Any,
        n_splits: int = 5,
        mode: str = "transient",
    ) -> Result:
        return self._execute_algorithm(
            "naive_bayes_categorical_cv",
            algorithm_x=list(features),
            algorithm_y=[target],
            parameters={"n_splits": n_splits},
            mode=mode,
            name_for_ui=f"Naive Bayes CV (categorical): {public_label(target)}",
        )
