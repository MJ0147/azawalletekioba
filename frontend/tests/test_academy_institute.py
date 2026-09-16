import asyncio
import base64
import hashlib
import importlib.util
import struct
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from nacl.signing import SigningKey
from tonsdk.contract.wallet import Wallets, WalletVersionEnum
from tonsdk.utils import Address

from services import academy_routes, academy_translate, ton_proof

FRONTEND_DIR = Path(__file__).resolve().parents[1]
SECRET = "test-academy-secret-0123456789abcdef"
ADMIN_TOKEN = "test-academy-admin"
DOMAIN = "testserver"  # the host TestClient sends


@pytest.fixture(scope="module")
def frontend():
    spec = importlib.util.spec_from_file_location("ekioba_frontend_app_academy", FRONTEND_DIR / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def client(frontend, tmp_path, monkeypatch):
    monkeypatch.setenv("ACADEMY_DATABASE_URL", f"sqlite:///{(tmp_path / 'academy.db').as_posix()}")
    monkeypatch.setenv("ACADEMY_SESSION_SECRET", SECRET)
    monkeypatch.setenv("ACADEMY_ADMIN_TOKEN", ADMIN_TOKEN)
    return TestClient(frontend.app)


# ── Wallets and proofs ───────────────────────────────────────────────────────


def make_wallet():
    """A v4r2 TON wallet: its raw address, its state (walletStateInit) and its signing key."""
    signing_key = SigningKey.generate()
    public_key = bytes(signing_key.verify_key)
    wallet = Wallets.ALL[WalletVersionEnum.v4r2](public_key=public_key, private_key=bytes(signing_key) + public_key, wc=0)
    state = wallet.create_state_init()
    address = state["address"].to_string(False)
    return address, base64.b64encode(state["state_init"].to_boc(False)).decode(), signing_key


def sign_proof(address, signing_key, payload, *, domain=DOMAIN, timestamp=None):
    """What a wallet returns for TON Connect's ton_proof, following the documented message format."""
    wallet = Address(address)
    stamp = int(timestamp if timestamp is not None else time.time())
    domain_bytes = domain.encode()
    message = (
        b"ton-proof-item-v2/" + struct.pack(">i", wallet.wc) + bytes(wallet.hash_part)
        + struct.pack("<I", len(domain_bytes)) + domain_bytes + struct.pack("<Q", stamp) + payload.encode()
    )
    digest = hashlib.sha256(b"\xff\xff" + b"ton-connect" + hashlib.sha256(message).digest()).digest()
    signature = signing_key.sign(digest).signature
    return {"timestamp": stamp, "domain": {"lengthBytes": len(domain_bytes), "value": domain}, "payload": payload, "signature": base64.b64encode(signature).decode()}


def test_a_signed_proof_proves_who_owns_the_wallet():
    address, state_init, key = make_wallet()
    payload = ton_proof.new_payload(SECRET)

    def check(**changes):
        arguments = {"address": address, "proof": sign_proof(address, key, payload), "state_init": state_init,
                     "allowed_domains": {DOMAIN}, "secret": SECRET, **changes}
        return ton_proof.verify_proof(**arguments)

    assert check() == address

    other_address, other_state, other_key = make_wallet()
    failures = {
        "another site": {"proof": sign_proof(address, key, payload, domain="evil.example")},
        "an old proof": {"proof": sign_proof(address, key, payload, timestamp=time.time() - 3600)},
        "a challenge this site didn't issue": {"proof": sign_proof(address, key, ton_proof.new_payload("another-secret"))},
        "an expired challenge": {"proof": sign_proof(address, key, ton_proof.new_payload(SECRET, now=time.time() - 3600))},
        "someone else's key": {"proof": sign_proof(address, other_key, payload)},
        "someone else's wallet state": {"state_init": other_state},
        "a claimed address the key doesn't own": {"address": other_address, "proof": sign_proof(other_address, key, payload)},
    }
    for reason, changes in failures.items():
        with pytest.raises(ton_proof.TonProofError):
            check(**changes)
            pytest.fail(f"accepted {reason}")


def sign_in(client):
    address, state_init, key = make_wallet()
    payload = client.get("/api/academy/auth/challenge").json()["payload"]
    response = client.post("/api/academy/auth/verify", json={"address": address, "state_init": state_init, "proof": sign_proof(address, key, payload)})
    assert response.status_code == 200, response.text
    return address


# ── Exams, grades and points ─────────────────────────────────────────────────


def take_exam(client, grade, correct_count):
    """Answer a whole exam, getting `correct_count` right. Returns the result."""
    started = client.post("/api/academy/exams", json={"grade": grade})
    assert started.status_code == 200, started.text
    view = started.json()
    assert "answer" not in view["question"] and "answer_label" not in view["question"]
    attempt = asyncio.run(academy_routes.get_store().get_attempt(view["attempt_id"]))
    result = None
    for index, question in enumerate(attempt["questions"]):
        right = question["answer_label"]
        wrong = next(option["label"] for option in question["options"] if option["label"] != right)
        response = client.post(f"/api/academy/exams/{view['attempt_id']}/answer",
                               json={"index": index, "choice": right if index < correct_count else wrong})
        assert response.status_code == 200, response.text
        body = response.json()
        if "next_question" in body:
            assert "answer" not in body["next_question"] and "answer_label" not in body["next_question"]
        result = body.get("result", result)
    return result


def me(client):
    response = client.get("/api/academy/me")
    assert response.status_code == 200, response.text
    return response.json()


def test_the_academy_needs_its_database_and_a_signed_in_wallet(frontend, client, monkeypatch):
    assert client.get("/api/academy/me").status_code == 401
    client.cookies.set("academy_session", "forged")
    assert client.get("/api/academy/me").status_code == 401
    client.cookies.clear()

    monkeypatch.delenv("ACADEMY_DATABASE_URL")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert client.get("/api/academy/me").status_code == 503


def test_exams_are_marked_on_the_server_and_passing_unlocks_the_next_grade(client):
    wallet = sign_in(client)
    record = me(client)
    assert record["wallet"] == wallet
    assert [g["unlocked"] for g in record["grades"]] == [True, False, False, False]
    assert client.post("/api/academy/exams", json={"grade": 2}).status_code == 403

    started = client.post("/api/academy/exams", json={"grade": 1}).json()
    assert started["total"] == 50 and len(started["question"]["options"]) == 4
    assert client.post(f"/api/academy/exams/{started['attempt_id']}/answer", json={"index": 5, "choice": "A"}).status_code == 409
    resumed = client.post("/api/academy/exams", json={"grade": 1}).json()
    assert resumed["attempt_id"] == started["attempt_id"]  # the same exam resumes

    result = take_exam(client, 1, correct_count=50)
    assert result == {"correct": 50, "total": 50, "percent": 100, "passed": True, "pass_percent": 70, "points_awarded": 500, "next_grade": 2}
    record = me(client)
    assert record["points"]["available"] == 500
    assert record["grades"][0]["passed"] and record["grades"][1]["unlocked"]


def test_failing_keeps_the_next_grade_locked(client):
    sign_in(client)
    result = take_exam(client, 1, correct_count=34)  # 68%
    assert result["passed"] is False and result["points_awarded"] == 340
    assert me(client)["grades"][1]["unlocked"] is False


def test_retakes_only_earn_points_for_beating_the_best_score(client):
    sign_in(client)
    assert take_exam(client, 1, correct_count=40)["points_awarded"] == 400
    assert take_exam(client, 1, correct_count=40)["points_awarded"] == 0
    assert take_exam(client, 1, correct_count=45)["points_awarded"] == 50
    record = me(client)
    assert record["points"]["available"] == 450 and record["grades"][0]["best_percent"] == 90


def test_points_convert_to_idia_after_grades_one_to_four_with_owner_review(client):
    wallet = sign_in(client)
    take_exam(client, 1, correct_count=50)
    assert client.post("/api/academy/conversions").status_code == 403  # Grades 2-4 not passed yet
    for grade in (2, 3, 4):
        take_exam(client, grade, correct_count=50)

    record = me(client)
    assert record["idia"]["eligible"] and record["idia"]["convertible_idia"] == 20
    requested = client.post("/api/academy/conversions")
    assert requested.status_code == 201, requested.text
    request = requested.json()
    assert (request["points"], request["idia_amount"], request["status"]) == (2000, "20", "pending")
    assert me(client)["points"]["available"] == 0
    assert client.post("/api/academy/conversions").status_code == 409

    queue = "/api/academy/admin/conversions"
    admin = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    assert client.get(queue).status_code == 401
    assert client.get(queue, headers={"Authorization": "Bearer wrong"}).status_code == 401
    pending = client.get(queue, headers=admin).json()["conversions"]
    assert [(c["id"], c["wallet"]) for c in pending] == [(request["id"], wallet)]

    declined = client.post(f"{queue}/{request['id']}/reject", json={"note": "Please retake Grade 4"}, headers=admin)
    assert declined.json()["status"] == "rejected"
    assert me(client)["points"]["available"] == 2000  # declined points come back

    second = client.post("/api/academy/conversions").json()
    assert client.post(f"{queue}/{second['id']}/paid", json={}, headers=admin).status_code == 400  # the transfer hash is required
    sent = client.post(f"{queue}/{second['id']}/paid", json={"tx_hash": "abc123"}, headers=admin).json()
    assert (sent["status"], sent["tx_hash"]) == ("paid", "abc123")
    assert client.post(f"{queue}/{second['id']}/paid", json={"tx_hash": "abc123"}, headers=admin).status_code == 404
    record = me(client)
    assert record["points"]["available"] == 0 and record["conversions"][0]["status"] == "paid"


# ── Translator and pages ─────────────────────────────────────────────────────


def test_translator_answers_from_the_knowledge_base_offline(client, monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    known = client.post("/api/academy/translate", json={"text": "the dog", "direction": "en_to_edo"}).json()
    assert known["translated_text"] == "ekita" and known["source"] == "knowledge_base" and not known["unknown_words"]

    partial = client.post("/api/academy/translate", json={"text": "dog spaceship", "direction": "en_to_edo"}).json()
    assert partial["translated_text"] == "ekita [spaceship]" and partial["unknown_words"] == ["spaceship"]
    assert client.post("/api/academy/translate", json={"text": " ", "direction": "en_to_edo"}).status_code == 400


def test_translator_asks_grok_for_words_the_knowledge_base_lacks(client, monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    requests = []

    async def fake_create_response(*, api_key, base_url, payload, timeout):
        requests.append(payload)
        return {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": "ekita [spaceship]"}]}]}

    monkeypatch.setattr(academy_translate, "create_response", fake_create_response)
    result = client.post("/api/academy/translate", json={"text": "dog spaceship", "direction": "en_to_edo"}).json()
    assert result["source"] == "ai" and "native speaker" in result["note"]
    assert "- dog = ekita" in requests[0]["input"][0]["content"] and "tools" not in requests[0]


def test_academy_page_runs_exams_full_page_and_offers_wallet_sign_in(client):
    page = client.get("/academy").text
    assert "Sign in with TON wallet" in page
    assert "academyRunner()" in page and "position:fixed;inset:0" in page
    assert "temporarily offline" not in page
    assert "window.ekiobaTonReady" in page
    assert client.get("/academy/admin", follow_redirects=False).headers["location"] == "/admin#conversions"
