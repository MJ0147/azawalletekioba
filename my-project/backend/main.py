from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.api import generative_ui
from app.utils.render_ui import render_component

app = FastAPI()
app.include_router(generative_ui.router, prefix="/api/ai")

# Create Jinja2Templates instance (not attached to app)
templates = Jinja2Templates(directory="app/templates")

@app.get("/preview", response_class=HTMLResponse)
async def preview_ui(request: Request):
    component = {
        "type": "button",
        "props": {"className": "bg-green-500 px-4 py-2", "aria-label": "Hello EKIOBA"},
        "children": "Hello EKIOBA"
    }
    rendered = render_component(component)
    return templates.TemplateResponse(
        "generated.html",
        {"request": request, "rendered_ui": rendered}
    )
