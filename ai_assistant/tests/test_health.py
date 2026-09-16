from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "iyobo"


def test_a_failed_connection_says_why_without_naming_the_host():
    """"Database connection failed" alone gave nobody anywhere to start."""
    from app.main import database_problem

    class Unreachable(Exception):
        pass

    cases = {
        "connection to server at \"db.example.supabase.co\" failed: Network is unreachable": "IPv6",
        "password authentication failed for user \"postgres\"": "credentials",
        "could not translate host name \"nope\" to address": "host name",
        "connection timed out": "timed out",
    }
    for message, expected in cases.items():
        said = database_problem(Unreachable(message))
        assert expected.lower() in said.lower(), (message, said)
        # The driver's own text can name the host and user; it belongs in the log, not the reply.
        assert "db.example.supabase.co" not in said
        assert "postgres" not in said


def test_an_unrecognised_failure_gives_only_the_exception_name():
    class OperationalError(Exception):
        pass

    from app.main import database_problem

    assert database_problem(OperationalError("something odd with secret=hunter2")) == "OperationalError"
