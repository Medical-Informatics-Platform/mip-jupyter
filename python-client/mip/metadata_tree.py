"""ASCII and HTML metadata tree rendering for catalog discovery in notebooks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import Iterable
from typing import Mapping

from .datamodel import DataModel
from .display import escape_html


class MetadataTree(str):
    """ASCII tree text with optional collapsible HTML for notebooks."""

    def __new__(cls, text: str, *, html: str | None = None):
        instance = super().__new__(cls, text)
        instance._html = html
        return instance

    def __repr__(self) -> str:
        return str(self)

    def _repr_html_(self) -> str:
        if self._html:
            return self._html
        escaped = escape_html(str(self))
        return f"<pre style=\"white-space:pre-wrap\">{escaped}</pre>"

    def display(self) -> None:
        try:
            from IPython.display import display
        except ImportError:
            print(self)
            return
        display(self)


@dataclass(frozen=True)
class PathologyView:
    """Notebook-friendly view of a backend data model."""

    code: str | None
    version: str | None
    label: str | None
    longitudinal: bool | None
    variables: list[Any]
    groups: list[Any]
    datasets: list[Any]
    datasets_variables: Mapping[str, list[Any]]

    @property
    def name(self) -> str:
        if self.code and self.version:
            return f"{self.code}:{self.version}"
        return str(self.code or self.version or "")


def pathology_from_data_model(model: DataModel) -> PathologyView:
    return PathologyView(
        code=model._code,
        version=model.version,
        label=model.label,
        longitudinal=model.longitudinal,
        variables=list(model.root_variables()),
        groups=list(model.groups or []),
        datasets=[dataset.details() for dataset in model.datasets.to_list()],
        datasets_variables=dict(model.datasets_variables or {}),
    )


def variable_group_paths(groups: Iterable[Any]) -> dict[str, str]:
    """Map variable codes to label-only group paths (e.g. Clinical > Cognitive)."""
    paths: dict[str, str] = {}

    def visit(group: Any, path: list[str]) -> None:
        label = str(_item_get(group, "label") or "").strip() or "<unknown>"
        current = path + [label]
        path_text = " > ".join(current)
        for variable in _as_list(_item_get(group, "variables", default=[])):
            code = _item_get(variable, "code")
            if code is None or code in paths:
                continue
            paths[str(code)] = path_text
        for child in _as_list(_item_get(group, "groups", default=[])):
            visit(child, current)

    for group in _as_list(groups):
        visit(group, [])
    return paths


def render_catalog_tree(models: list[DataModel], *, max_lines: int = 250) -> str:
    writer = _LineWriter(max_lines=max_lines)
    writer.add(f"Data models ({len(models)})")
    if not models:
        return writer.render()

    ordered = sorted(
        [pathology_from_data_model(model) for model in models],
        key=lambda model: (str(model.label or "").lower(), str(model.version or "").lower()),
    )
    for index, model in enumerate(ordered):
        connector = "`--" if index == len(ordered) - 1 else "|--"
        groups_count = _count_group_nodes(model.groups)
        grouped_variables_count = _count_group_variables(model.groups)
        summary = [
            f"{len(model.datasets)} datasets",
            f"{len(model.variables)} root vars",
            f"{groups_count} groups",
            f"{grouped_variables_count} grouped vars",
        ]
        writer.add(
            f"{connector} {model.label or model.name} [{', '.join(summary)}]"
        )
    return writer.render()


def render_catalog_tree_html(models: list[DataModel], *, max_nodes: int = 250) -> str:
    counter = _NodeCounter(max_nodes=max_nodes)
    ordered = sorted(
        [pathology_from_data_model(model) for model in models],
        key=lambda model: (str(model.label or "").lower(), str(model.version or "").lower()),
    )
    items = []
    for model in ordered:
        if not counter.consume():
            break
        groups_count = _count_group_nodes(model.groups)
        grouped_variables_count = _count_group_variables(model.groups)
        summary = (
            f"{len(model.datasets)} datasets · {len(model.variables)} root vars · "
            f"{groups_count} groups · {grouped_variables_count} grouped vars"
        )
        label = escape_html(model.label or model.name or "<unknown>")
        version = f" ({escape_html(model.version)})" if model.version else ""
        items.append(
            f"<li><strong>{label}{version}</strong>"
            f"<div style=\"color:#666;font-size:12px\">{escape_html(summary)}</div></li>"
        )
    truncated = (
        '<li style="color:#666">… (truncated)</li>' if counter.truncated else ""
    )
    return (
        '<div style="font-family:system-ui,sans-serif;font-size:13px;line-height:1.45">'
        f"<p><strong>Data models ({len(models)})</strong></p>"
        f"<ul style=\"margin:0;padding-left:1.2em\">{''.join(items)}{truncated}</ul>"
        "</div>"
    )


def render_pathology_tree(
    pathology: PathologyView,
    *,
    include_variables: bool = False,
    max_lines: int = 250,
    focus_group: Any | None = None,
    focus_group_path: list[str] | None = None,
) -> str:
    if focus_group is not None:
        display_name = pathology.label or "<unknown>"
        if pathology.version:
            display_name = f"{display_name} ({pathology.version})"
        return render_group_subtree(
            focus_group,
            model_display_name=display_name,
            group_path=focus_group_path,
            include_variables=include_variables,
            max_lines=max_lines,
        )

    writer = _LineWriter(max_lines=max_lines)
    title = f"Metadata tree for {pathology.label or pathology.name or '<unknown>'}"
    if pathology.version:
        title += f" ({pathology.version})"
    writer.add(title)

    sections: list[tuple[str, Any]] = []
    if pathology.longitudinal is not None:
        sections.append(("longitudinal", pathology.longitudinal))
    sections.append(("datasets", pathology.datasets))
    sections.append(("groups", pathology.groups))
    sections.append(("root_variables", pathology.variables))

    for index, (name, value) in enumerate(sections):
        is_last = index == len(sections) - 1
        connector = "`--" if is_last else "|--"
        prefix = "   " if is_last else "|  "

        if name == "longitudinal":
            writer.add(f"{connector} longitudinal: {bool(value)}")
            continue

        if name == "datasets":
            datasets = _as_list(value)
            writer.add(f"{connector} datasets ({len(datasets)})")
            for dataset_index, dataset in enumerate(datasets):
                dataset_last = dataset_index == len(datasets) - 1
                dataset_connector = "`--" if dataset_last else "|--"
                writer.add(f"{prefix}{dataset_connector} {_format_dataset(dataset)}")
            continue

        if name == "groups":
            groups = _as_list(value)
            writer.add(f"{connector} groups ({len(groups)})")
            for group_index, group in enumerate(groups):
                _render_group(
                    writer=writer,
                    group=group,
                    prefix=prefix,
                    is_last=group_index == len(groups) - 1,
                    include_variables=include_variables,
                )
            continue

        if name == "root_variables":
            variables = _as_list(value)
            writer.add(f"{connector} root_variables ({len(variables)})")
            if include_variables:
                for variable_index, variable in enumerate(variables):
                    variable_last = variable_index == len(variables) - 1
                    variable_connector = "`--" if variable_last else "|--"
                    writer.add(f"{prefix}{variable_connector} {_format_variable(variable)}")
            continue

    return writer.render()


def render_pathology_tree_html(
    pathology: PathologyView,
    *,
    include_variables: bool = False,
    max_nodes: int = 250,
    focus_group: Any | None = None,
    focus_group_path: list[str] | None = None,
) -> str:
    counter = _NodeCounter(max_nodes=max_nodes)
    if focus_group is not None:
        display_name = pathology.label or "<unknown>"
        if pathology.version:
            display_name = f"{display_name} ({pathology.version})"
        path_parts = [str(part) for part in (focus_group_path or []) if part]
        if not path_parts:
            path_parts = [_format_name_label(_item_get(focus_group, "code"), _item_get(focus_group, "label"))]
        title = f"{display_name} › {' › '.join(path_parts)}"
        body = _render_group_html(
            group=focus_group,
            include_variables=include_variables,
            counter=counter,
            open_root=True,
        )
        return _wrap_tree_html(title, body, truncated=counter.truncated)

    title = f"Metadata tree for {pathology.label or pathology.name or '<unknown>'}"
    if pathology.version:
        title += f" ({pathology.version})"

    sections: list[str] = []
    if pathology.longitudinal is not None and counter.consume():
        sections.append(f"<div>longitudinal: <code>{escape_html(bool(pathology.longitudinal))}</code></div>")

    datasets = _as_list(pathology.datasets)
    if counter.consume():
        dataset_items = []
        for dataset in datasets:
            if not counter.consume():
                break
            dataset_items.append(f"<li>{escape_html(_format_dataset(dataset))}</li>")
        sections.append(
            _details_block(
                f"datasets ({len(datasets)})",
                f"<ul style=\"margin:0.25em 0;padding-left:1.2em\">{''.join(dataset_items)}</ul>",
                open_by_default=True,
            )
        )

    groups = _as_list(pathology.groups)
    if counter.consume():
        group_html = "".join(
            _render_group_html(
                group=group,
                include_variables=include_variables,
                counter=counter,
                open_root=False,
            )
            for group in groups
            if not counter.truncated
        )
        sections.append(
            _details_block(
                f"groups ({len(groups)})",
                group_html or "<div style=\"color:#666\">(none)</div>",
                open_by_default=True,
            )
        )

    variables = _as_list(pathology.variables)
    if counter.consume():
        if include_variables:
            variable_html = "".join(
                _variable_html(variable)
                for variable in variables
                if counter.consume()
            )
        else:
            variable_html = (
                '<div style="color:#666;font-size:12px">'
                "Use include_variables=True or dm.variables.tree(group=...) to list variables."
                "</div>"
            )
        sections.append(
            _details_block(
                f"root_variables ({len(variables)})",
                variable_html,
                open_by_default=include_variables,
            )
        )

    return _wrap_tree_html(title, "".join(sections), truncated=counter.truncated)


def render_group_subtree(
    group: Any,
    *,
    model_display_name: str | None = None,
    group_path: list[str] | None = None,
    include_variables: bool = True,
    max_lines: int = 250,
) -> str:
    writer = _LineWriter(max_lines=max_lines)
    path_parts = [str(part) for part in (group_path or []) if part]
    if not path_parts:
        path_parts = [_format_name_label(_item_get(group, "code"), _item_get(group, "label"))]
    path_text = " > ".join(path_parts)
    if model_display_name:
        title = f"Metadata tree for {model_display_name} > {path_text}"
    else:
        title = f"Variables > {path_text}"
    writer.add(title)
    _render_group(
        writer=writer,
        group=group,
        prefix="",
        is_last=True,
        include_variables=include_variables,
    )
    return writer.render()


def find_group(groups: Iterable[Any], selector: Any) -> tuple[Any, list[str]] | None:
    needle = _group_selector(selector)
    if not needle:
        return None

    def visit(group: Any, path: list[str]) -> tuple[Any, list[str]] | None:
        label = str(_item_get(group, "label") or "").strip()
        current_path = path + [label or "<unknown>"]
        if _matches_group_selector(group, needle):
            return group, current_path
        for child in _item_get(group, "groups", default=[]):
            found = visit(child, current_path)
            if found is not None:
                return found
        return None

    for group in _as_list(groups):
        found = visit(group, [])
        if found is not None:
            return found
    return None


def list_groups(groups: Iterable[Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    def visit(group: Any, path: list[str]) -> None:
        code = str(_item_get(group, "code") or "").strip()
        label = str(_item_get(group, "label") or "").strip()
        current_path = path + [label or "<unknown>"]
        items.append({"code": code or None, "label": label or None, "path": current_path})
        for child in _item_get(group, "groups", default=[]):
            visit(child, current_path)

    for group in _as_list(groups):
        visit(group, [])
    return items


def _group_selector(selector: Any) -> str:
    if isinstance(selector, Mapping):
        return str(selector.get("code") or selector.get("label") or "").strip().lower()
    return str(selector or "").strip().lower()


def _matches_group_selector(group: Any, needle: str) -> bool:
    code = str(_item_get(group, "code") or "").strip().lower()
    label = str(_item_get(group, "label") or "").strip().lower()
    return needle in {code, label}


class _LineWriter:
    def __init__(self, max_lines: int):
        self.max_lines = max(1, int(max_lines))
        self.lines: list[str] = []
        self.truncated = False

    def add(self, line: str) -> bool:
        if len(self.lines) >= self.max_lines:
            self.truncated = True
            return False
        self.lines.append(line)
        return True

    def render(self) -> str:
        if self.truncated:
            if self.lines:
                self.lines[-1] = "... (truncated)"
            else:
                self.lines.append("... (truncated)")
        return "\n".join(self.lines)


class _NodeCounter:
    def __init__(self, max_nodes: int):
        self.max_nodes = max(1, int(max_nodes))
        self.count = 0
        self.truncated = False

    def consume(self) -> bool:
        if self.count >= self.max_nodes:
            self.truncated = True
            return False
        self.count += 1
        return True


def _wrap_tree_html(title: str, body: str, *, truncated: bool) -> str:
    note = (
        '<div style="color:#666;margin-top:0.5em;font-size:12px">… (truncated)</div>'
        if truncated
        else ""
    )
    return (
        '<div style="font-family:system-ui,sans-serif;font-size:13px;line-height:1.45">'
        f"<p><strong>{escape_html(title)}</strong></p>"
        f"{body}{note}"
        "</div>"
    )


def _details_block(summary: str, body: str, *, open_by_default: bool) -> str:
    open_attr = " open" if open_by_default else ""
    return (
        f"<details{open_attr} style=\"margin:0.2em 0\">"
        f"<summary style=\"cursor:pointer\">{escape_html(summary)}</summary>"
        f"<div style=\"margin-left:0.9em;margin-top:0.25em\">{body}</div>"
        "</details>"
    )


def _render_group_html(
    *,
    group: Any,
    include_variables: bool,
    counter: _NodeCounter,
    open_root: bool,
) -> str:
    if not counter.consume():
        return ""
    variables = _as_list(_item_get(group, "variables", default=[]))
    subgroups = _as_list(_item_get(group, "groups", default=[]))
    node_name = _format_name_label(_item_get(group, "code"), _item_get(group, "label"))
    summary_parts = [f"{len(variables)} vars"]
    if subgroups:
        summary_parts.append(f"{len(subgroups)} groups")
    summary = f"{node_name} [{', '.join(summary_parts)}]"

    children: list[str] = []
    if include_variables:
        for variable in variables:
            if not counter.consume():
                break
            children.append(_variable_html(variable))
    for subgroup in subgroups:
        if counter.truncated:
            break
        children.append(
            _render_group_html(
                group=subgroup,
                include_variables=include_variables,
                counter=counter,
                open_root=False,
            )
        )
    return _details_block(
        summary,
        "".join(children) or "<div style=\"color:#666\">(empty)</div>",
        open_by_default=open_root,
    )


def _variable_html(variable: Any) -> str:
    label = escape_html(_format_name_label(_item_get(variable, "code"), _item_get(variable, "label")))
    variable_type = _item_get(variable, "type")
    type_html = (
        f' <span style="color:#666;font-size:12px">[{escape_html(variable_type)}]</span>'
        if variable_type
        else ""
    )
    return f"<div style=\"padding:0.1em 0\">{label}{type_html}</div>"


def _render_group(
    writer: _LineWriter,
    group: Any,
    prefix: str,
    is_last: bool,
    include_variables: bool,
) -> None:
    variables = _as_list(_item_get(group, "variables", default=[]))
    subgroups = _as_list(_item_get(group, "groups", default=[]))
    connector = "`--" if is_last else "|--"
    node_name = _format_name_label(_item_get(group, "code"), _item_get(group, "label"))
    summary_parts = [f"{len(variables)} vars"]
    if subgroups:
        summary_parts.append(f"{len(subgroups)} groups")
    writer.add(f"{prefix}{connector} {node_name} [{', '.join(summary_parts)}]")

    child_prefix = prefix + ("   " if is_last else "|  ")
    children: list[tuple[str, Any]] = []
    if include_variables:
        for variable in variables:
            children.append(("variable", variable))
    for subgroup in subgroups:
        children.append(("group", subgroup))

    for child_index, (kind, node) in enumerate(children):
        child_last = child_index == len(children) - 1
        if kind == "variable":
            child_connector = "`--" if child_last else "|--"
            writer.add(f"{child_prefix}{child_connector} {_format_variable(node)}")
            continue

        _render_group(
            writer=writer,
            group=node,
            prefix=child_prefix,
            is_last=child_last,
            include_variables=include_variables,
        )


def _count_group_nodes(groups: Iterable[Any]) -> int:
    total = 0
    for group in _as_list(groups):
        total += 1
        total += _count_group_nodes(_item_get(group, "groups", default=[]))
    return total


def _count_group_variables(groups: Iterable[Any]) -> int:
    total = 0
    for group in _as_list(groups):
        total += len(_as_list(_item_get(group, "variables", default=[])))
        total += _count_group_variables(_item_get(group, "groups", default=[]))
    return total


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _item_get(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(key, default)
    return getattr(item, key, default)


def _format_name_label(code: Any, label: Any) -> str:
    label_text = str(label or "").strip()
    if label_text:
        return label_text
    return str(code or "<unknown>")


def _format_dataset(dataset: Any) -> str:
    if isinstance(dataset, str):
        return dataset
    label = str(_item_get(dataset, "label") or "").strip()
    if label:
        return label
    return "<unknown>"


def _format_variable(variable: Any) -> str:
    code = _item_get(variable, "code")
    label = _item_get(variable, "label")
    variable_type = _item_get(variable, "type")
    text = _format_name_label(code, label)
    if variable_type:
        text += f" [{variable_type}]"
    return text
