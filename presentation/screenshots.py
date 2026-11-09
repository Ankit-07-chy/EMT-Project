"""Screenshots of the running dashboard for the presentation (presentation/screens/*.png).

Needs Playwright (``pip install playwright``) and an installed Chrome or Edge; the
dashboard itself runs from the project venv:

    <python-with-playwright> presentation/screenshots.py [--python .venv/Scripts/python.exe]
"""
from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "screens"


def wait_idle(page, timeout=180):
    """Wait until Streamlit has finished running the script."""
    t0 = time.time()
    page.wait_for_selector("[data-testid='stApp']", timeout=timeout * 1000)
    time.sleep(1.0)
    while time.time() - t0 < timeout:
        running = page.locator("[data-testid='stStatusWidget']").count()
        if running == 0:
            break
        time.sleep(0.5)
    time.sleep(2.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", default=str(ROOT / ".venv" / "Scripts" / "python.exe"))
    ap.add_argument("--channel", default="chrome")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen([a.python, "-m", "streamlit", "run", str(ROOT / "app" / "dashboard.py"), "--server.headless", "true",
                             "--server.port", str(port), "--browser.gatherUsageStats", "false", "--theme.base", "light"],
                            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(120):
            try:
                if urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=2).read().strip() == b"ok":
                    break
            except OSError:
                time.sleep(1)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            br = pw.chromium.launch(channel=a.channel, headless=True)
            page = br.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=1.25)
            page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
            wait_idle(page)
            page.screenshot(path=str(OUT / "s01_analyze_open.png"), full_page=True)
            print("s01")
            # a partial fault: shunt resistor
            sb = page.locator("[data-testid='stSidebar']")
            sb.locator("[data-testid='stSelectbox']").nth(1).click()
            page.get_by_role("option", name="Shunt resistor (partial short)").click()
            wait_idle(page)
            page.screenshot(path=str(OUT / "s02_analyze_shunt.png"), full_page=True)
            print("s02")
            for label, name in (("Model comparison", "s03_model_comparison"), ("Real data (Zenodo)", "s04_real_data_zenodo"),
                                ("Calibration & lab", "s05_calibration_lab"), ("Physics", "s06_physics")):
                page.get_by_role("tab", name=label).click()
                wait_idle(page, 60)
                page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
                print(name)
            br.close()
    finally:
        proc.terminate()
        proc.wait(timeout=30)


if __name__ == "__main__":
    sys.exit(main())
