"""IID-MULTI-DEPLOY: the deployed instances — one list for every script that needs it
(`make_qr.py`, `health_check.py` / IID-HEALTH-MONITOR). Keep in sync with the service table
in CLAUDE.md and the matrix in `.github/workflows/health.yml`."""

# short name -> public URL
# `teachbot` (Predictions lecture, Heidelberg; https://teachbot-production-2e85.up.railway.app)
# was taken offline on 2026-10-22 — the course is over. Re-add it here, in the health.yml
# matrix and in the CLAUDE.md table if the service is brought back.
DEPLOYS = {
    "public": "https://teachbot-public-production.up.railway.app",
    "dcm": "https://teachbot-dcm-production.up.railway.app",
    "timeseries": "https://teachbot-timeseries-production.up.railway.app",
}


def railway_service(name: str) -> str:
    """Railway service name for a DEPLOYS key (`teachbot`, `teachbot-public`, ...)."""
    return "teachbot" if name == "teachbot" else f"teachbot-{name}"
