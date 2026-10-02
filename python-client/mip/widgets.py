"""Optional interactive notebook widgets for catalog browsing."""

from __future__ import annotations

from typing import Any
from typing import Callable

from .exceptions import UnsupportedOperationError


def browse_analysis_set(
    data_model: Any,
    *,
    on_select: Callable[[Any], None] | None = None,
    max_variable_options: int = 200,
):
    """Interactive dataset/variable picker that builds an AnalysisSet.

    Requires the optional ``ipywidgets`` dependency (notebook extra).
    """
    widgets, display = _require_ipywidgets()

    dataset_options = [dataset.label for dataset in data_model.datasets.to_list() if dataset.label]
    variable_options = [variable.label for variable in data_model.variables.to_list() if variable.label]
    if len(variable_options) > max_variable_options:
        variable_options = variable_options[:max_variable_options]

    dataset_select = widgets.SelectMultiple(
        options=dataset_options,
        value=tuple(dataset_options[:1]),
        description="Datasets",
        layout=widgets.Layout(width="100%", height="120px"),
    )
    variable_search = widgets.Text(description="Search", placeholder="filter variables…")
    variable_select = widgets.SelectMultiple(
        options=variable_options,
        value=tuple(variable_options[: min(5, len(variable_options))]),
        description="Variables",
        layout=widgets.Layout(width="100%", height="220px"),
    )
    status = widgets.HTML(value="<em>Select datasets and variables, then click Build.</em>")
    output = widgets.Output()
    build_button = widgets.Button(description="Build AnalysisSet", button_style="primary")
    state: dict[str, Any] = {"analysis_set": None}

    def _filter_variables(_change=None) -> None:
        needle = (variable_search.value or "").strip().lower()
        if not needle:
            variable_select.options = variable_options
            return
        variable_select.options = [label for label in variable_options if needle in label.lower()]

    def _build(_button=None) -> None:
        datasets = list(dataset_select.value)
        variables = list(variable_select.value)
        with output:
            output.clear_output()
            if not datasets or not variables:
                status.value = "<span style='color:#a00'>Choose at least one dataset and one variable.</span>"
                return
            analysis_set = data_model.select(datasets=datasets, variables=variables)
            state["analysis_set"] = analysis_set
            status.value = (
                f"<strong>AnalysisSet ready</strong> — {len(datasets)} dataset(s), "
                f"{len(variables)} variable(s)."
            )
            display(analysis_set)
            if on_select is not None:
                on_select(analysis_set)

    variable_search.observe(_filter_variables, names="value")
    build_button.on_click(_build)

    panel = widgets.VBox(
        [
            widgets.HTML(
                f"<strong>Browse {getattr(data_model, 'name', data_model)}</strong>"
                "<div style='color:#666;font-size:12px'>Optional interactive picker (ipywidgets).</div>"
            ),
            dataset_select,
            variable_search,
            variable_select,
            build_button,
            status,
            output,
        ]
    )
    display(panel)
    return state


def browse_catalog(catalog: Any, *, max_variable_options: int = 200):
    """Pick a data model, then browse datasets/variables into an AnalysisSet."""
    widgets, display = _require_ipywidgets()
    models = catalog.list()
    if not models:
        raise UnsupportedOperationError("Catalog has no authorized data models to browse.")

    options = [(model.name, index) for index, model in enumerate(models)]
    model_dropdown = widgets.Dropdown(options=options, description="Data model")
    container = widgets.Output()
    state: dict[str, Any] = {"analysis_set": None}

    def _forward(analysis_set: Any) -> None:
        state["analysis_set"] = analysis_set

    def _render(_change=None) -> None:
        with container:
            container.clear_output()
            model = models[int(model_dropdown.value)]
            nested = browse_analysis_set(
                model,
                on_select=_forward,
                max_variable_options=max_variable_options,
            )
            state["picker"] = nested

    model_dropdown.observe(_render, names="value")
    display(widgets.VBox([model_dropdown, container]))
    _render()
    return state


def _require_ipywidgets():
    try:
        import ipywidgets as widgets
        from IPython.display import display
    except Exception as exc:
        raise UnsupportedOperationError(
            "Interactive browsing requires ipywidgets and IPython. "
            "Install the notebook extra: pip install 'mip[notebook]' and ipywidgets."
        ) from exc
    return widgets, display
