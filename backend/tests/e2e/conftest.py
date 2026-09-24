"""Real browser -> real ASGI handlers -> existing isolated PostgreSQL fixture.

Only transport is bridged: API responses and Set-Cookie come from FastAPI, not
mock JSON. YouTube embeds/API are local stubs and all other external browser
requests are rejected. No production catalog or reviewed sample CSV is used.
"""

import os
import shutil
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_session
from app.main import app
from app.models import Trigger, TriggerSample, Video, VideoTrigger
from app.sound_test import BASE, OPTIONAL

playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def frontend_server(migrated, tmp_path_factory):
    frontend = Path(__file__).resolve().parents[3] / "frontend"
    next_cli = frontend / "node_modules/next/dist/bin/next"
    if not next_cli.exists() or not shutil.which("node"):
        pytest.fail("E2E requires Node and frontend dependencies (npm ci)")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    env = {
        **os.environ,
        "NEXT_PUBLIC_API_BASE_URL": origin,
        "NEXT_TELEMETRY_DISABLED": "1",
        "YOUTUBE_API_KEY": "",
    }
    log_path = tmp_path_factory.mktemp("e2e") / "next.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [shutil.which("node"), str(next_cli), "dev", "--hostname",
             "127.0.0.1", "--port", str(port)],
            cwd=frontend,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            deadline = time.monotonic() + 120
            with httpx.Client(trust_env=False) as client:
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        pytest.fail(f"Next exited; see {log_path}")
                    try:
                        if client.get(origin, timeout=2).status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(0.2)
                else:
                    pytest.fail(f"Next did not become ready; see {log_path}")
            yield origin
        finally:
            if os.name == "nt" and process.poll() is None:
                # Next dev has a worker process; stop this fixture's tree too.
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW, check=False,
                )
            elif process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=15)


@pytest.fixture
def flow(db, frontend_server, monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "e2e-only-session-secret-at-least-32-bytes")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    monkeypatch.setenv("YOUTUBE_API_KEY", "")

    def no_http(*args, **kwargs):
        pytest.fail("Backend attempted an outbound HTTP request")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", no_http)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", no_http)
    with Session(db, join_transaction_mode="create_savepoint") as session:
        now = datetime.now(timezone.utc)
        features = {}
        videos = {}
        keys = [(key, "sound") for key in BASE + OPTIONAL]
        keys += [("hand_movements", "visual"), ("roleplay", "format")]
        for index, (key, family) in enumerate(keys):
            feature = Trigger(
                key=key, display_name=key, family=family,
                is_core=family == "sound",
            )
            video = Video(
                youtube_video_id=f"e2e{index:08d}", title=f"Fixture {key}",
                channel_id=f"fixture-{index}", channel_name="Fixture channel",
                duration_sec=120, language="en", last_synced_at=now,
            )
            session.add_all([feature, video])
            session.flush()
            session.add(VideoTrigger(
                video_id=video.id, trigger_id=feature.id, confidence=1,
                source="manual", tagger_version="e2e", created_at=now,
            ))
            if family == "sound":
                # Synthetic test intervals, never imported as production samples.
                session.add(TriggerSample(
                    primary_trigger_id=feature.id, video_id=video.id,
                    start_sec=0, end_sec=10, verified=True, created_at=now,
                ))
            features[key] = feature.id
            videos[key] = video.id
        # Same-feature siblings prove Skip is item-only, independently of Dislike.
        for index in (1, 2):
            sibling = Video(
                youtube_video_id=f"e2esibling{index}",
                title=f"Fixture tapping sibling {index}",
                channel_id=f"sibling-{index}", channel_name="Fixture channel",
                last_synced_at=now,
            )
            session.add(sibling)
            session.flush()
            session.add(VideoTrigger(
                video_id=sibling.id, trigger_id=features["tapping"], confidence=1,
                source="manual", tagger_version="e2e", created_at=now,
            ))
            videos[f"sibling{index}"] = sibling.id
        session.commit()

        def override():
            try:
                yield session
            finally:
                session.rollback()

        app.dependency_overrides[get_session] = override
        external = []
        api_calls = []
        youtube = []
        try:
            with TestClient(app) as client, playwright.sync_playwright() as pw:
                browser = pw.chromium.launch()
                context = browser.new_context(service_workers="block")

                def dispatch(route):
                    request = route.request
                    url = urlsplit(request.url)
                    if request.url.startswith(frontend_server + "/api/v1/"):
                        # Never let TestClient's jar mask missing browser cookies.
                        client.cookies.clear()
                        response = client.request(
                            request.method,
                            url.path + (f"?{url.query}" if url.query else ""),
                            headers=request.all_headers(),
                            content=request.post_data_buffer,
                        )
                        api_calls.append((
                            request.method, url.path, response.status_code,
                        ))
                        route.fulfill(
                            status=response.status_code,
                            headers=dict(response.headers), body=response.content,
                        )
                    elif url.hostname == "www.youtube.com":
                        youtube.append(url.path)
                        if url.path == "/iframe_api":
                            route.fulfill(
                                content_type="application/javascript",
                                body="window.YT={Player:class {destroy(){}}};"
                                     "window.onYouTubeIframeAPIReady?.();",
                            )
                        elif url.path.startswith("/embed/"):
                            route.fulfill(
                                content_type="text/html",
                                body="<!doctype html><title>Mock YouTube</title>",
                            )
                        else:
                            external.append(request.url)
                            route.abort()
                    elif request.url.startswith(frontend_server + "/"):
                        route.continue_()
                    else:
                        external.append(request.url)
                        route.abort()

                context.route("**/*", dispatch)
                page = context.new_page()
                page.set_default_timeout(30000)
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                try:
                    yield SimpleNamespace(
                        page=page, context=context, db=session,
                        origin=frontend_server, features=features, videos=videos,
                        api_calls=api_calls, youtube=youtube,
                    )
                    assert not external, f"Unexpected external requests: {external}"
                    assert not errors, f"Browser errors: {errors}"
                    assert all(status < 400 for _, _, status in api_calls), api_calls
                finally:
                    context.close()
                    browser.close()
        finally:
            app.dependency_overrides.pop(get_session)
