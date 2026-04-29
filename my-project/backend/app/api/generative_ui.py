from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class UIComponent(BaseModel):
    type: str
    props: Dict[str, Any]
    children: Optional[List["UIComponent"]] = None
    styles: Optional[Dict[str, str]] = None


class GenerateUIRequest(BaseModel):
    description: str
    componentType: str
    context: str = "ekioba-marketplace"


class GenerateLayoutRequest(BaseModel):
    description: str
    context: str = "ekioba-marketplace"


class GenerateUIResponse(BaseModel):
    component: UIComponent


class GenerateLayoutResponse(BaseModel):
    layout: List[UIComponent]


if hasattr(UIComponent, "model_rebuild"):
    UIComponent.model_rebuild()
else:
    UIComponent.update_forward_refs()


@router.post("/generate-ui", response_model=GenerateUIResponse)
async def generate_ui(payload: GenerateUIRequest) -> GenerateUIResponse:
    # Placeholder generation logic; replace with model-backed generation as needed.
    component = UIComponent(
        type=payload.componentType,
        props={"className": "bg-blue-500 text-white px-4 py-2 rounded"},
        children=[UIComponent(type="span", props={"text": payload.description})],
    )
    return GenerateUIResponse(component=component)


@router.post("/generate-layout", response_model=GenerateLayoutResponse)
async def generate_layout(payload: GenerateLayoutRequest) -> GenerateLayoutResponse:
    # Example layout output: heading + button.
    layout = [
        UIComponent(type="h1", props={"text": payload.description}),
        UIComponent(
            type="button",
            props={"className": "btn-primary"},
            children=[UIComponent(type="span", props={"text": "Click Me"})],
        ),
    ]
    return GenerateLayoutResponse(layout=layout)
