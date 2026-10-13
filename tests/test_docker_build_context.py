"""Catch a Dockerfile COPY source accidentally excluded by .dockerignore.

The production image uses an explicit allowlist because project roots contain
credentials and story data. Keep the allowlist in sync as Python modules change.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_docker_copy_sources_are_allowlisted():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    ignore_lines = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert "**" in ignore_lines, "Docker context must exclude unlisted files"
    allow = {s[1:] for s in ignore_lines if s.startswith("!")}

    for line in dockerfile.splitlines():
        if not line.startswith("COPY "):
            continue
        tokens = line.removeprefix("COPY ").split()
        # Dockerfile COPY statements here specify one or more sources and a dest.
        assert len(tokens) >= 2
        for source in tokens[:-1]:
            assert source in allow, (
                f"Dockerfile copies {source!r}, but .dockerignore hides it. "
                f"Add '!{source}' to the Docker context allowlist."
            )
            if not source.endswith("/"):
                assert (ROOT / source).is_file(), (
                    f"Dockerfile COPY source {source!r} is missing"
                )


def test_docker_context_keeps_private_inputs_out():
    ignore_lines = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert "**" in ignore_lines
    for forbidden in [".env", ".git/", "stories/", "firebase-credentials.json"]:
        assert f"!{forbidden}" not in ignore_lines
