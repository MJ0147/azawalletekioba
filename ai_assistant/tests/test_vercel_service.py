import json
from pathlib import Path

from fastapi.testclient import TestClient

ASSISTANT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ASSISTANT_DIR.parent


def test_vercel_routes_iyobo_to_the_assistant_and_everything_else_to_the_website():
    config = json.loads((REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))
    services = config["services"]
    for service in services.values():
        module, _, variable = service["entrypoint"].partition(":")
        assert (REPO_ROOT / service["root"] / f"{module.replace('.', '/')}.py").is_file(), service
        assert variable == "app"
    assert services["iyobo"]["root"] == "ai_assistant/"

    rules = [(rule["source"], rule["destination"]["service"]) for rule in config["rewrites"]]
    assert rules[-1] == ("/(.*)", "website")  # the catch-all must come last
    assert {("/iyobo", "iyobo"), ("/iyobo/(.*)", "iyobo")} <= set(rules[:-1])


def test_the_assistant_answers_under_the_iyobo_path():
    import vercel_app

    try:
        client = TestClient(vercel_app.app)
        assert client.get("/iyobo/ready").json() == {"status": "ready"}
        assert client.get("/ready").status_code == 200
        assert client.get("/iyobo/admin/knowledge-suggestions").status_code == 401
    finally:
        vercel_app.app.root_path = ""


def test_the_assistant_ships_its_own_knowledge_base_copy():
    from app.knowledge_base import BUNDLED_KNOWLEDGE_BASE

    assert BUNDLED_KNOWLEDGE_BASE == ASSISTANT_DIR / "knowledge_base"
    assert (BUNDLED_KNOWLEDGE_BASE / "INDEX.md").is_file()
