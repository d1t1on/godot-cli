from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .scene import inspect_project_scenes


ROLE_BY_CLASS = {
    "AcceptDialog": "dialog",
    "Button": "button",
    "CheckBox": "checkbox",
    "CheckButton": "checkbox",
    "ConfirmationDialog": "dialog",
    "Control": "control",
    "ColorRect": "control",
    "HSlider": "slider",
    "ItemList": "list",
    "Label": "text",
    "LineEdit": "textbox",
    "MenuButton": "button",
    "OptionButton": "combobox",
    "Panel": "panel",
    "PanelContainer": "panel",
    "PopupMenu": "menu",
    "ProgressBar": "progressbar",
    "RichTextLabel": "text",
    "SpinBox": "spinbutton",
    "TabBar": "tablist",
    "TabContainer": "tabpanel",
    "TextEdit": "textbox",
    "Tree": "list",
    "VSlider": "slider",
    "Window": "window",
}


class ProjectNodeQueryError(RuntimeError):
    def __init__(self, report: dict[str, Any]):
        self.report = report
        super().__init__(_project_node_query_error_message(report))


def find_project_nodes(
    project: str | Path,
    scenes: list[str | Path] | None = None,
    *,
    exclude: list[str] | None = None,
    selector: str | dict[str, Any] | None = None,
    name: str | None = None,
    name_contains: str | None = None,
    class_name: str | None = None,
    role: str | None = None,
    role_name: str | None = None,
    role_name_contains: str | None = None,
    test_id: str | None = None,
    text: str | None = None,
    text_contains: str | None = None,
    property_name: str | None = None,
    property_value: Any = None,
    include_properties: bool = False,
    limit: int = 0,
    check: bool = False,
) -> dict[str, Any]:
    project_path = Path(project).expanduser().resolve()
    started = time.monotonic()
    query = _query_from_args(
        selector=selector,
        name=name,
        name_contains=name_contains,
        class_name=class_name,
        role=role,
        role_name=role_name,
        role_name_contains=role_name_contains,
        test_id=test_id,
        text=text,
        text_contains=text_contains,
        property_name=property_name,
        property_value=property_value,
    )
    scene_report = inspect_project_scenes(
        project_path,
        scenes or [],
        exclude=exclude or [],
        include_properties=True,
    )
    matches: list[dict[str, Any]] = []
    for scene in scene_report.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        for node in scene.get("nodes", []):
            if not isinstance(node, dict):
                continue
            indexed = _indexed_node(scene, node, include_properties)
            if _node_matches_query(indexed, query):
                matches.append(_public_indexed_node(indexed, include_properties))
                if limit > 0 and len(matches) >= limit:
                    break
        if limit > 0 and len(matches) >= limit:
            break
    report = {
        "project": str(project_path),
        "ok": bool(scene_report.get("ok", False)),
        "query": query,
        "scene_count": scene_report.get("scene_count", 0),
        "node_count": sum(len(scene.get("nodes", [])) for scene in scene_report.get("scenes", []) if isinstance(scene, dict)),
        "match_count": len(matches),
        "matches": matches,
        "diagnostics": scene_report.get("diagnostics", []),
        "diagnostic_count": scene_report.get("diagnostic_count", 0),
        "duration_ms": round((time.monotonic() - started) * 1000.0, 3),
    }
    if check and not report["ok"]:
        raise ProjectNodeQueryError(report)
    return report


def _query_from_args(
    *,
    selector: str | dict[str, Any] | None,
    name: str | None,
    name_contains: str | None,
    class_name: str | None,
    role: str | None,
    role_name: str | None,
    role_name_contains: str | None,
    test_id: str | None,
    text: str | None,
    text_contains: str | None,
    property_name: str | None,
    property_value: Any,
) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if selector is not None:
        query.update(_selector_to_query(selector))
    if name is not None:
        query["name"] = name
    if name_contains is not None:
        query["node_name_contains"] = name_contains
    if class_name is not None:
        query["class"] = class_name
    if role is not None:
        query["role"] = role
    if role_name is not None:
        query["role_name"] = role_name
    if role_name_contains is not None:
        query["role_name_contains"] = role_name_contains
    if test_id is not None:
        query["test_id"] = test_id
    if text is not None:
        query["text"] = text
    if text_contains is not None:
        query["text_contains"] = text_contains
    if property_name is not None:
        query["property"] = property_name
        if property_value is not None:
            query["value"] = property_value
    return query


def _selector_to_query(selector: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(selector, dict):
        return dict(selector)
    text = selector
    if text.startswith("#"):
        return {"name": text[1:]}
    if text.startswith("."):
        return {"group": text[1:]}
    if text.startswith("type="):
        return {"class": text[5:]}
    if text.startswith("class="):
        return {"class": text[6:]}
    if text.startswith("name="):
        return {"name": text[5:]}
    if text.startswith("role="):
        return {"role": text[5:]}
    if text.startswith("test_id="):
        return {"test_id": text[8:]}
    if text.startswith("testid="):
        return {"test_id": text[7:]}
    if text.startswith("path="):
        return {"path": text[5:]}
    if text.startswith("/"):
        return {"path": text}
    if text.startswith("text*="):
        return {"text_contains": text[6:]}
    if text.startswith("text="):
        return {"text": text[5:]}
    if text.startswith("placeholder*="):
        return {"placeholder_contains": text[13:]}
    if text.startswith("placeholder="):
        return {"placeholder": text[12:]}
    if text.startswith("tooltip*="):
        return {"tooltip_contains": text[9:]}
    if text.startswith("tooltip="):
        return {"tooltip": text[8:]}
    return {"any": [{"name": text}, {"class": text}]}


def _indexed_node(scene: dict[str, Any], node: dict[str, Any], include_properties: bool) -> dict[str, Any]:
    properties = node.get("properties", {}) if isinstance(node.get("properties"), dict) else {}
    metadata = _node_metadata(properties)
    class_name = str(node.get("class", node.get("type", "")))
    role = _node_role(class_name)
    indexed = {
        "scene": scene.get("scene", ""),
        "scene_path": scene.get("scene_path", ""),
        "name": node.get("name", ""),
        "class": class_name,
        "type": class_name,
        "path": node.get("path", ""),
        "node_path": node.get("path", ""),
        "scene_node_path": node.get("scene_path", ""),
        "parent_path": node.get("parent_path", ""),
        "role": role,
        "accessible_names": _accessible_names(node),
        "test_id": metadata.get("test_id", ""),
        "metadata": metadata,
        "line": node.get("line"),
        "property_count": node.get("property_count", 0),
        "_properties": properties,
    }
    if include_properties:
        indexed["properties"] = properties
    return indexed


def _public_indexed_node(node: dict[str, Any], include_properties: bool) -> dict[str, Any]:
    public = {key: value for key, value in node.items() if not key.startswith("_")}
    if include_properties and "properties" not in public:
        public["properties"] = _node_properties(node)
    return public


def _node_metadata(properties: dict[str, Any]) -> dict[str, Any]:
    metadata = {}
    for name, value in properties.items():
        if name.startswith("metadata/"):
            metadata[name.removeprefix("metadata/")] = value
    return metadata


def _accessible_names(node: dict[str, Any]) -> list[Any]:
    properties = node.get("properties", {}) if isinstance(node.get("properties"), dict) else {}
    names = []
    for property_name in ("text", "placeholder_text", "tooltip_text"):
        value = properties.get(property_name, "")
        if value != "":
            names.append(value)
    node_name = node.get("name", "")
    if node_name != "":
        names.append(node_name)
    return names


def _node_role(class_name: str) -> str:
    return ROLE_BY_CLASS.get(class_name, class_name.lower())


def _node_matches_query(node: dict[str, Any], query: dict[str, Any]) -> bool:
    if not query:
        return True
    if "all" in query or "and" in query:
        selectors = query.get("all", query.get("and", []))
        if not isinstance(selectors, list) or not all(_node_matches_query(node, _selector_to_query(item)) for item in selectors):
            return False
    if "any" in query or "or" in query:
        selectors = query.get("any", query.get("or", []))
        if not isinstance(selectors, list) or not any(_node_matches_query(node, _selector_to_query(item)) for item in selectors):
            return False
    if "not" in query and _node_matches_query(node, _selector_to_query(query["not"])):
        return False
    if "base" in query and not _node_matches_query(node, _selector_to_query(query["base"])):
        return False
    if query.get("name") is not None and node.get("name") != query.get("name"):
        return False
    if query.get("node_name_contains") is not None and str(query.get("node_name_contains")) not in str(node.get("name", "")):
        return False
    if query.get("name_contains") is not None:
        needle = str(query.get("name_contains"))
        if not any(needle in str(value) for value in node.get("accessible_names", [])):
            return False
    if query.get("group") is not None:
        return False
    if query.get("class") is not None and node.get("class") != query.get("class"):
        return False
    if query.get("type") is not None and node.get("class") != query.get("type"):
        return False
    if query.get("path") is not None and node.get("path") != query.get("path"):
        return False
    if query.get("role") is not None and not _role_matches(str(node.get("role", "")), str(query.get("role"))):
        return False
    if query.get("role_name") is not None and query.get("role_name") not in node.get("accessible_names", []):
        return False
    if query.get("role_name_contains") is not None:
        needle = str(query.get("role_name_contains"))
        if not any(needle in str(value) for value in node.get("accessible_names", [])):
            return False
    if query.get("test_id") is not None and node.get("test_id") != query.get("test_id"):
        return False
    if query.get("testid") is not None and node.get("test_id") != query.get("testid"):
        return False
    if "metadata" in query or "meta" in query:
        expected_metadata = query.get("metadata", query.get("meta", {}))
        if not isinstance(expected_metadata, dict):
            return False
        metadata = node.get("metadata", {})
        if not all(metadata.get(key) == value for key, value in expected_metadata.items()):
            return False
    if query.get("text") is not None and not _property_matches(node, "text", query.get("text")):
        return False
    if query.get("text_contains") is not None and not _property_contains(node, "text", query.get("text_contains")):
        return False
    if query.get("placeholder") is not None and not _property_matches(node, "placeholder_text", query.get("placeholder")):
        return False
    if query.get("placeholder_contains") is not None and not _property_contains(node, "placeholder_text", query.get("placeholder_contains")):
        return False
    if query.get("tooltip") is not None and not _property_matches(node, "tooltip_text", query.get("tooltip")):
        return False
    if query.get("tooltip_contains") is not None and not _property_contains(node, "tooltip_text", query.get("tooltip_contains")):
        return False
    if query.get("property") is not None:
        property_name = str(query.get("property"))
        properties = _node_properties(node)
        if property_name not in properties:
            return False
        if "value" in query and properties.get(property_name) != query.get("value"):
            return False
        if "contains" in query and str(query.get("contains")) not in str(properties.get(property_name, "")):
            return False
    if query.get("properties") is not None:
        expected = query.get("properties")
        properties = _node_properties(node)
        if not isinstance(expected, dict) or not all(properties.get(key) == value for key, value in expected.items()):
            return False
    return True


def _role_matches(actual: str, expected: str) -> bool:
    normalized_actual = _normalize_role(actual)
    normalized_expected = _normalize_role(expected)
    return (
        normalized_actual == normalized_expected
        or (normalized_expected == "label" and normalized_actual == "text")
        or (normalized_expected == "text-box" and normalized_actual == "textbox")
        or (normalized_expected == "menuitem" and normalized_actual == "menu-item")
    )


def _normalize_role(role: str) -> str:
    return role.strip().lower().replace("_", "-")


def _property_matches(node: dict[str, Any], property_name: str, expected: Any) -> bool:
    properties = _node_properties(node)
    return isinstance(properties, dict) and properties.get(property_name) == expected


def _property_contains(node: dict[str, Any], property_name: str, expected: Any) -> bool:
    properties = _node_properties(node)
    return isinstance(properties, dict) and str(expected) in str(properties.get(property_name, ""))


def _node_properties(node: dict[str, Any]) -> dict[str, Any]:
    properties = node.get("_properties", node.get("properties", {}))
    return properties if isinstance(properties, dict) else {}


def _project_node_query_error_message(report: dict[str, Any]) -> str:
    diagnostics = report.get("diagnostics", [])
    if diagnostics:
        details = "\n".join(
            f"{item.get('kind')}: {item.get('message')} {item.get('scene', item.get('path', ''))}".rstrip()
            for item in diagnostics[:8]
        )
    else:
        details = "unknown error"
    return f"Godot project node query failed for {report.get('project')!r}\n{details}"
