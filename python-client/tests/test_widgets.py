"""Tests for optional interactive browse widgets."""

import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

from mip.catalog import Catalog
from mip.exceptions import UnsupportedOperationError
from mip.widgets import browse_analysis_set
from mip.widgets import browse_catalog

from test_catalog import MOCK_DATA_MODELS


class TestWidgets(unittest.TestCase):
    def setUp(self):
        self.transport = MagicMock()
        self.transport.get.return_value = MOCK_DATA_MODELS
        self.catalog = Catalog(self.transport)
        self.dm = self.catalog.data_model("Dementia")

    def test_browse_requires_ipywidgets(self):
        with patch.dict("sys.modules", {"ipywidgets": None}):
            with self.assertRaises(UnsupportedOperationError):
                browse_analysis_set(self.dm)

    def test_browse_analysis_set_builds_selection(self):
        fake_widgets = MagicMock()
        fake_widgets.SelectMultiple = MagicMock(side_effect=lambda **kwargs: MagicMock(**kwargs, value=kwargs.get("value", ())))
        fake_widgets.Text = MagicMock(return_value=MagicMock(value=""))
        fake_widgets.HTML = MagicMock(return_value=MagicMock(value=""))
        fake_widgets.Output = MagicMock(return_value=MagicMock())
        fake_widgets.Button = MagicMock(return_value=MagicMock())
        fake_widgets.VBox = MagicMock(side_effect=lambda children: MagicMock(children=children))
        fake_widgets.Layout = MagicMock(return_value=MagicMock())

        displayed = []

        def fake_display(obj):
            displayed.append(obj)

        dataset_widget = MagicMock(value=("ADNI",))
        variable_widget = MagicMock(value=("Age", "MMSE"))
        search_widget = MagicMock(value="")
        status_widget = MagicMock(value="")
        output_widget = MagicMock()
        button = MagicMock()

        def select_multiple(**kwargs):
            description = kwargs.get("description")
            if description == "Datasets":
                return dataset_widget
            return variable_widget

        fake_widgets.SelectMultiple = MagicMock(side_effect=select_multiple)
        fake_widgets.Text = MagicMock(return_value=search_widget)
        fake_widgets.HTML = MagicMock(return_value=status_widget)
        fake_widgets.Output = MagicMock(return_value=output_widget)
        fake_widgets.Button = MagicMock(return_value=button)

        with patch("mip.widgets._require_ipywidgets", return_value=(fake_widgets, fake_display)):
            state = browse_analysis_set(self.dm)

        self.assertIsNone(state["analysis_set"])
        self.assertTrue(button.on_click.called)
        build_callback = button.on_click.call_args[0][0]
        build_callback(button)
        self.assertIsNotNone(state["analysis_set"])
        self.assertEqual(state["analysis_set"].summary()["datasets"], ["ADNI"])
        self.assertEqual(state["analysis_set"].summary()["variables"], ["Age", "MMSE"])

    def test_catalog_browse_delegates(self):
        with patch("mip.widgets.browse_catalog") as mocked:
            mocked.return_value = {"analysis_set": None}
            result = self.catalog.browse()
        mocked.assert_called_once()
        self.assertEqual(result, {"analysis_set": None})


if __name__ == "__main__":
    unittest.main()
