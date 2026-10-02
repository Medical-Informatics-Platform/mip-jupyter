import unittest
from unittest.mock import MagicMock

from mip.algorithms import AlgorithmRegistry


class TestAlgorithms(unittest.TestCase):
    def test_registry_lists_and_searches_algorithms(self):
        transport = MagicMock()
        transport.get.return_value = [
            {"name": "describe", "label": "Describe", "type": "statistics", "desc": "summary"},
            {"name": "logistic_regression", "label": "Logistic", "type": "model"},
        ]
        registry = AlgorithmRegistry(transport)

        self.assertEqual(registry.list()[0].label, "Describe")
        self.assertEqual(registry.search("logistic")[0].label, "Logistic")
        self.assertEqual(registry.statistics()[0].label, "Describe")
        self.assertEqual(registry.models()[0].label, "Logistic")
        self.assertNotIn("name", registry.list()[0].summary())
        transport.get.assert_called_with("/specifications/algorithms")


if __name__ == "__main__":
    unittest.main()
