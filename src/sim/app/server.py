"""Local web app.

    python -m sim.app.server            # http://127.0.0.1:8765
    python -m sim.app.server --open     # and open the browser
"""
import argparse
import socket
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn
from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .. import config
from ..weekly import read_status
from . import api, live

STATIC = Path(__file__).parent / "static"
PORT = 8765

app = FastAPI(title="Matchday", docs_url=None, redoc_url=None)


@app.get("/api/meta")
def get_meta():
    return api.meta()


@app.get("/api/matchweek")
def get_matchweek(mw: int | None = None):
    return api.matchweek(mw)


@app.get("/api/fixture/{match_id}")
def get_fixture(match_id: int):
    try:
        return api.fixture(match_id)
    except KeyError:
        raise HTTPException(404, "No such fixture")


@app.post("/api/whatif/{match_id}")
def post_whatif(match_id: int, body: dict = Body(...)):
    try:
        return api.whatif(match_id, body.get("home"), body.get("away"), int(body.get("sims", 1000)))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/live")
def get_live(mw: int | None = None):
    return live.live(mw)


@app.get("/api/live/event/{espn_id}")
def get_live_event(espn_id: str):
    if not espn_id.isdigit():
        raise HTTPException(400, "Not an ESPN event id")
    try:
        return live.event(espn_id)
    except Exception as exc:   # upstream down or changed: say so plainly
        raise HTTPException(502, f"ESPN did not answer ({exc.__class__.__name__})")


@app.get("/api/season")
def get_season():
    return api.season()


@app.get("/api/team/{name}")
def get_team(name: str):
    try:
        return api.team(name)
    except KeyError as exc:
        raise HTTPException(404, str(exc))


@app.get("/api/players")
def get_players(season: int | None = None, min_minutes: int = 270):
    return api.players(season, min_minutes)


@app.get("/api/player/{player_id}")
def get_player(player_id: int, season: int | None = None):
    return api.player(player_id, season)


@app.get("/api/styles")
def get_styles():
    return api.styles()


@app.put("/api/styles")
def put_styles(body: dict = Body(...)):
    article = body.get("article")
    if article is not None and len(article) > 50_000:
        raise HTTPException(400, "The article is too long (50,000 characters at most)")
    return api.save_styles(article=article, overrides=body.get("overrides"), reset=body.get("reset"))


@app.get("/api/model")
def get_model():
    return api.model()


@app.get("/api/status")
def get_status():
    return read_status()


@app.post("/api/update")
def post_update(body: dict = Body(default={})):
    if read_status().get("running"):
        raise HTTPException(409, "An update is already running")
    kind = body.get("kind", "full")
    if kind not in ("full", "light"):
        raise HTTPException(400, "kind must be full or light")
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    subprocess.Popen([sys.executable, "-m", "sim.weekly", "--kind", kind], cwd=config.ROOT, creationflags=flags)
    return {"started": kind}


@app.middleware("http")
async def revalidate_assets(request, call_next):
    """The app changes on disk between versions; make the browser check before reusing a cached file."""
    response = await call_next(request)
    if request.url.path.startswith("/assets/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


app.mount("/assets", StaticFiles(directory=STATIC), name="assets")


@app.get("/{path:path}")
def index(path: str = ""):
    return FileResponse(STATIC / "index.html")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--port", type=int, default=PORT)
    args = ap.parse_args()
    if sys.stdout is None or sys.stderr is None:   # started windowless (pythonw): log to a file
        log = open(config.ROOT / "data" / "server.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = log
    url = f"http://127.0.0.1:{args.port}/"
    with socket.socket() as sock:
        sock.settimeout(0.5)
        if sock.connect_ex(("127.0.0.1", args.port)) == 0:   # already running: just open it
            if args.open:
                webbrowser.open(url)
            return
    if args.open:
        def open_when_ready():
            for _ in range(240):   # up to a minute
                with socket.socket() as probe:
                    probe.settimeout(0.25)
                    if probe.connect_ex(("127.0.0.1", args.port)) == 0:
                        webbrowser.open(url)
                        return
                threading.Event().wait(0.25)
        threading.Thread(target=open_when_ready, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
