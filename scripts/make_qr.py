"""IID-MULTI-DEPLOY: Generate QR codes for the deployed instances into qr/<name>.png + .svg.

Usage:
    python scripts/make_qr.py                     # all instances in DEPLOYS
    python scripts/make_qr.py --name dcm          # one instance
    python scripts/make_qr.py --name foo --url https://example.org   # ad-hoc

Requires `pip install "qrcode[pil]"` (dev-only, not in requirements.txt).
Output folder: qr/ (repo root) — the only place QR codes live.
"""
import argparse
from pathlib import Path

import qrcode
from qrcode.image.svg import SvgPathImage

# IID-MULTI-DEPLOY: keep in sync with the service table in CLAUDE.md
DEPLOYS = {
    "teachbot": "https://teachbot-production-2e85.up.railway.app",
    "public": "https://teachbot-public-production.up.railway.app",
    "dcm": "https://teachbot-dcm-production.up.railway.app",
}

OUT_DIR = Path(__file__).resolve().parent.parent / "qr"


def make(name: str, url: str) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=20, border=4)
    q.add_data(url)
    q.make(fit=True)
    q.make_image(fill_color="black", back_color="white").save(OUT_DIR / f"teachbot_{name}_qr.png")
    qrcode.make(url, image_factory=SvgPathImage, box_size=20, border=4).save(OUT_DIR / f"teachbot_{name}_qr.svg")
    print(f"qr/teachbot_{name}_qr.png + .svg  ->  {url}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generate QR codes for teachbot instances")
    ap.add_argument("--name", help="instance key from DEPLOYS (or any label when --url is given)")
    ap.add_argument("--url", help="override/ad-hoc URL")
    a = ap.parse_args()
    if a.url:
        make(a.name or "custom", a.url)
    elif a.name:
        make(a.name, DEPLOYS[a.name])
    else:
        for n, u in DEPLOYS.items():
            make(n, u)
