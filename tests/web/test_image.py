"""The image carries what the marketplace's web server needs: a service that starts without them serves nothing."""

import pathlib
import re

ROOT = pathlib.Path(__file__).parents[2]
DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")


def test_the_image_copies_the_web_server_and_the_built_frontend() -> None:
    assert re.search(r"^COPY web \./web$", DOCKERFILE, re.M)
    # Where web/main.py looks for it: frontend/dist next to the web/ package.
    assert re.search(r"^COPY --from=frontend /frontend/dist \./frontend/dist$", DOCKERFILE, re.M)


def test_the_frontend_is_built_from_the_lockfile() -> None:
    stage = DOCKERFILE.split("FROM ghcr.io/astral-sh/uv")[0]

    assert "COPY frontend/package.json frontend/package-lock.json" in stage
    assert re.search(r"^RUN npm ci$", stage, re.M), "npm install would resolve new versions at build time"
    assert re.search(r"^RUN npm run build$", stage, re.M)


def test_the_node_version_of_the_image_is_the_one_the_project_declares() -> None:
    declared = (ROOT / "frontend" / ".nvmrc").read_text(encoding="utf-8").strip()

    assert f"FROM node:{declared}-slim AS frontend" in DOCKERFILE
