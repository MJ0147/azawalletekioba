from html import escape
from typing import Any, Dict


def _build_style_attr(styles: Dict[str, str]) -> str:
    if not styles:
        return ""
    style_str = "; ".join(f"{k}:{v}" for k, v in styles.items())
    return f' style="{escape(style_str)}"'


def render_component(component: Dict[str, Any]) -> str:
    type_ = escape(str(component.get("type", "div")))
    props = component.get("props", {})
    children = component.get("children", [])
    styles = component.get("styles", {})

    class_attr = ""
    if "className" in props:
        class_attr = f' class="{escape(str(props.get("className", "")))}"'

    style_attr = _build_style_attr(styles)

    if isinstance(children, list):
        children_html = "".join(render_component(child) for child in children)
        if not children_html:
            children_html = escape(str(props.get("text", "")))
    elif isinstance(children, dict):
        children_html = render_component(children)
    elif isinstance(children, str):
        children_html = escape(children)
    else:
        children_html = escape(str(props.get("text", "")))

    return f"<{type_}{class_attr}{style_attr}>{children_html}</{type_}>"
