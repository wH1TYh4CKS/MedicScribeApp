from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
_ASSETS = ("app.js", "style.css", "pcm-worklet.js", "index.html", "feedback.html", "feedback.js")


def _asset_version() -> str:
    """A token that changes whenever any front-end asset changes (max mtime), so
    browsers cache normally but always re-fetch after a deploy. Kills the stale-JS
    class of bugs (stuck button, stuck status pill)."""
    mtimes = [(WEB_DIR / f).stat().st_mtime for f in _ASSETS if (WEB_DIR / f).exists()]
    return str(int(max(mtimes))) if mtimes else "0"


def _render(filename: str) -> HTMLResponse:
    """Serve a web page with cache-busted asset URLs so a redeploy is picked up
    without a manual hard-refresh."""
    html = (WEB_DIR / filename).read_text(encoding="utf-8")
    return HTMLResponse(html.replace("__ASSET_V__", _asset_version()))


@router.get("/", response_class=HTMLResponse)
async def root_page() -> HTMLResponse:
    """Serve at root so the URL is just the hostname (no /scribe path)."""
    return _render("index.html")


@router.get("/scribe", response_class=HTMLResponse)
async def scribe_page() -> HTMLResponse:
    """Back-compat alias for the original /scribe path."""
    return _render("index.html")


@router.get("/feedback", response_class=HTMLResponse)
async def feedback_page() -> HTMLResponse:
    """Feedback form (posts to /api/feedback)."""
    return _render("feedback.html")
