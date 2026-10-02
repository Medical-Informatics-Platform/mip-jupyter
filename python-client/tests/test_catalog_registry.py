import unittest

from mip.catalog_registry import (
    PIPELINE_BACKEND_ALGORITHMS,
    validate_client_registry,
)
from mip.preprocessing import PREPROCESSING_STEP_CLASSES, PREPROCESSING_STEP_NAMES


class TestCatalogRegistry(unittest.TestCase):
    def test_validate_client_registry_passes(self):
        validate_client_registry()

    def test_pipeline_registry_has_unique_backend_mappings(self):
        self.assertEqual(len(PIPELINE_BACKEND_ALGORITHMS), len(set(PIPELINE_BACKEND_ALGORITHMS.values())))

    def test_preprocessing_registry_covers_five_steps(self):
        self.assertEqual(len(PREPROCESSING_STEP_CLASSES), 5)
        self.assertEqual(
            set(PREPROCESSING_STEP_NAMES),
            {
                "longitudinal_transformer",
                "missing_values_handler",
                "outlier_winsorizer",
                "categorical_column_creator",
                "kmeans_cluster_creator",
            },
        )


if __name__ == "__main__":
    unittest.main()
