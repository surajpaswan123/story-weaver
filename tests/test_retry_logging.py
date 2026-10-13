"""Retry instrumentation: visibility without changing backoff or retry policy."""

import main


def test_transient_retry_reports_when_new_attempt_actually_starts(monkeypatch, capsys):
    pauses = []
    monkeypatch.setattr(main, "_transient_delay", lambda attempt: 2.3)
    monkeypatch.setattr(main.time, "sleep", pauses.append)
    calls = []

    def flaky_provider():
        calls.append(True)
        if len(calls) == 1:
            raise RuntimeError("ngrok gateway 502 bad gateway")
        return "finished"

    result = main._retry_transient(flaky_provider, label="BA/Verify/items.md", max_retries=20)
    output = capsys.readouterr().out
    assert result == "finished"
    assert len(calls) == 2
    assert pauses == [2.3]
    assert "[BA/Verify/items.md] transient error, retry 1/20 in 2.3s:" in output
    assert "[BA/Verify/items.md] retry 1/20 starting now (provider request in progress)..." in output
    assert "[BA/Verify/items.md] retry 1/20 succeeded" in output


def test_nested_retry_layers_log_their_own_attempts(monkeypatch, capsys):
    monkeypatch.setattr(main, "_transient_delay", lambda attempt: 0)
    monkeypatch.setattr(main.time, "sleep", lambda seconds: None)
    calls = []

    def provider():
        calls.append(True)
        if len(calls) < 3:
            raise RuntimeError("503 temporarily unavailable")
        return "verified"

    def complete():
        return main._retry_transient(
            provider, label="BA/Verify/OpenAI/antigravity", max_retries=1
        )

    assert main._retry_transient(
        complete, label="BA/Verify/items.md", max_retries=1
    ) == "verified"
    output = capsys.readouterr().out
    assert "BA/Verify/OpenAI/antigravity] retry 1/1 starting now" in output
    assert "BA/Verify/items.md] retry 1/1 starting now" in output
    assert "BA/Verify/items.md] retry 1/1 succeeded" in output


def test_initial_success_does_not_announce_a_retry(capsys):
    assert main._retry_transient(lambda: "ok", label="BA/Verify", max_retries=20) == "ok"
    assert "retry" not in capsys.readouterr().out.lower()
