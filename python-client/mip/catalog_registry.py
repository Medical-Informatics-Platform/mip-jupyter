"""Pipeline catalog registry and client-side validation."""

from __future__ import annotations

# Public Pipeline method name -> backend algorithm name.
PIPELINE_BACKEND_ALGORITHMS: dict[str, str] = {
    "describe": "describe",
    "histogram": "histogram",
    "t_test": "ttest_independent",
    "one_sample_t_test": "ttest_onesample",
    "paired_t_test": "ttest_paired",
    "chi_square_test": "chi_squared",
    "fisher_exact": "fisher_exact",
    "pearson_correlation": "pearson_correlation",
    "quartiles": "quartiles",
    "anova_oneway": "anova_oneway",
    "anova_twoway": "anova_twoway",
    "mann_whitney_u_test": "binned_mann_whitney_u_test",
    "standardized_mean_difference": "standardized_mean_difference",
    "outlier_report": "outlier_report",
    "linear_regression": "linear_regression",
    "linear_regression_cv": "linear_regression_cv",
    "logistic_regression": "logistic_regression",
    "logistic_regression_cv": "logistic_regression_cv",
    "cox_regression_classical": "cox_regression_classical",
    "cox_regression_stacked": "cox_regression_stacked",
    "lmm": "lmm",
    "glmm_binary": "glmm_binary",
    "glmm_ordinal": "glmm_ordinal",
    "linear_svm": "linear_svm",
    "kmeans": "kmeans",
    "pca": "pca",
    "pca_with_transformation": "pca_with_transformation",
    "naive_bayes_gaussian": "naive_bayes_gaussian",
    "naive_bayes_categorical": "naive_bayes_categorical",
    "naive_bayes_gaussian_cv": "naive_bayes_gaussian_cv",
    "naive_bayes_categorical_cv": "naive_bayes_categorical_cv",
}

PIPELINE_METHOD_NAMES: list[str] = list(PIPELINE_BACKEND_ALGORITHMS.keys())


def wrapped_preprocessing_steps() -> set[str]:
    from .preprocessing import PREPROCESSING_STEP_NAMES

    return set(PREPROCESSING_STEP_NAMES)


def validate_client_registry() -> None:
    """Ensure Pipeline methods and preprocessing classes match the registry."""
    from .pipeline_algorithms import PipelineAlgorithmsMixin
    from .preprocessing import PREPROCESSING_STEP_CLASSES

    missing_methods = [
        name for name in PIPELINE_METHOD_NAMES if not hasattr(PipelineAlgorithmsMixin, name)
    ]
    if missing_methods:
        raise AssertionError(f"Registry methods missing on PipelineAlgorithmsMixin: {missing_methods}")

    extra_methods = sorted(
        name
        for name in dir(PipelineAlgorithmsMixin)
        if not name.startswith("_")
        and callable(getattr(PipelineAlgorithmsMixin, name))
        and name not in PIPELINE_METHOD_NAMES
    )
    if extra_methods:
        raise AssertionError(f"PipelineAlgorithmsMixin methods missing from registry: {extra_methods}")

    backend_names = list(PIPELINE_BACKEND_ALGORITHMS.values())
    if len(backend_names) != len(set(backend_names)):
        raise AssertionError("Duplicate backend algorithm names in PIPELINE_BACKEND_ALGORITHMS")

    declared_names = {cls.name for cls in PREPROCESSING_STEP_CLASSES}
    wrapped_names = wrapped_preprocessing_steps()
    if declared_names != wrapped_names:
        raise AssertionError(
            f"Preprocessing registry drift: classes={sorted(declared_names)} "
            f"names={sorted(wrapped_names)}"
        )
