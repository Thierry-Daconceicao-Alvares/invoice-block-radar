"""Record the captioned demo video of the interface for the README.

    uvicorn api.main:app --port 8000 &
    (cd web && npm run build && npm start) &
    python scripts/record_demo.py --url http://localhost:3000

Writes docs/media/invoice-block-radar-demo.mp4 and a lighter .gif. Frames come
from Chromium's own screencast (DevTools protocol) with their timestamps, then
ffmpeg joins them at their real timing. Needs ffmpeg.
"""

from __future__ import annotations

import argparse
import base64
import shutil
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "docs" / "media"
SIZE = {"width": 1440, "height": 900}

CAPTION_JS = """text => {
  let box = document.getElementById('demo-caption');
  if (!box) {
    box = document.createElement('div');
    box.id = 'demo-caption';
    box.style.cssText = 'position:fixed;left:50%;bottom:28px;transform:translateX(-50%);'
      + 'z-index:2147483647;max-width:1100px;padding:14px 22px;border-radius:10px;'
      + 'background:rgba(10,18,26,0.92);color:#f2f6f9;font:500 22px/1.35 system-ui,sans-serif;'
      + 'box-shadow:0 6px 24px rgba(0,0,0,0.45);text-align:center;pointer-events:none;';
    document.body.appendChild(box);
  }
  box.textContent = text;
  box.style.display = text ? 'block' : 'none';
}"""


class Screencast:
    def __init__(self, page: Page, folder: Path) -> None:
        self.folder, self.frames = folder, []
        folder.mkdir(parents=True, exist_ok=True)
        self.session = page.context.new_cdp_session(page)
        self.session.on("Page.screencastFrame", self._frame)
        self.session.send(
            "Page.startScreencast",
            {"format": "jpeg", "quality": 90, "maxWidth": SIZE["width"], "maxHeight": SIZE["height"]},
        )

    def _frame(self, event: dict) -> None:
        path = self.folder / f"{len(self.frames):05d}.jpg"
        path.write_bytes(base64.b64decode(event["data"]))
        self.frames.append((event["metadata"]["timestamp"], path))
        self.session.send("Page.screencastFrameAck", {"sessionId": event["sessionId"]})

    def stop(self, hold: float = 2.0) -> Path:
        self.session.send("Page.stopScreencast")
        lines = []
        nexts = [*self.frames[1:], (self.frames[-1][0] + hold, None)]
        for (time_, path), (next_time, _) in zip(self.frames, nexts, strict=True):
            lines += [f"file '{path}'", f"duration {max(next_time - time_, 0.001):.3f}"]
        lines.append(f"file '{self.frames[-1][1]}'")
        listing = self.folder / "frames.txt"
        listing.write_text("\n".join(lines) + "\n")
        return listing


def caption(page: Page, text: str) -> None:
    page.evaluate(CAPTION_JS, text)


def scroll_to(page: Page, selector: str, offset: int = 80) -> None:
    page.evaluate(
        """([sel, off]) => {
            const el = document.querySelector(sel);
            window.scrollTo({top: el.getBoundingClientRect().top + window.scrollY - off, behavior: 'smooth'});
        }""",
        [selector, offset],
    )
    page.wait_for_timeout(900)


def glide(page: Page, pixels: int, steps: int = 30, pause: int = 60) -> None:
    for _ in range(steps):
        page.mouse.wheel(0, pixels / steps)
        page.wait_for_timeout(pause)


def film(page: Page, url: str, frames: Path) -> Path:
    page.goto(url)
    page.locator("canvas").first.wait_for()
    page.wait_for_timeout(1500)
    recording = Screencast(page, frames)

    caption(page, "One purchase order line in five hits a payment block before it is paid.")
    page.wait_for_timeout(3500)
    caption(page, "Process mining on 55,839 blocked items: invoices pile up before the release.")
    scroll_to(page, ".panel")
    page.wait_for_timeout(5000)
    caption(page, "65% of blocks end with nothing corrected: a person checks, then releases.")
    scroll_to(page, ".grid-2")
    page.wait_for_timeout(3500)

    page.goto(f"{url}/queue")
    page.locator("tr.row").first.wait_for()
    page.locator(".case .writeup").wait_for()
    page.wait_for_timeout(1000)
    caption(page, "The detective sorts the 3,690 invoices on hold on 15 October 2018.")
    page.wait_for_timeout(3500)
    page.locator("tr.row").nth(1).click()
    page.locator(".case .email").wait_for()
    scroll_to(page, ".split", 70)
    caption(page, "Rules decide the cause and who acts. Mistral only writes the note and the email.")
    page.wait_for_timeout(4500)
    scroll_to(page, ".case .email", 120)
    caption(page, "Code checks every note: no invented figure, an email only when needed.")
    page.wait_for_timeout(4000)
    scroll_to(page, ".case .outcome", 300)
    caption(page, "And what really happened next, read from the log.")
    page.wait_for_timeout(3500)

    page.goto(f"{url}/radar")
    page.locator(".result .verdict").wait_for()
    page.wait_for_timeout(800)
    caption(page, "At order time, a line is scored with how earlier invoices of the same vendor went.")
    page.wait_for_timeout(4500)
    options = page.locator("#example option")
    page.locator("#example").select_option(index=min(7, options.count() - 1))
    page.wait_for_timeout(600)
    caption(page, "Real order lines of September-October 2018, scored with only what was known that day.")
    page.wait_for_timeout(4000)

    page.goto(f"{url}/evidence")
    page.locator("canvas").first.wait_for()
    page.wait_for_timeout(800)
    caption(page, "Every claim measured on months the models never saw, against simple baselines.")
    page.wait_for_timeout(3000)
    scroll_to(page, "main > section:nth-of-type(2)", 70)
    caption(page, "Checking the riskiest 20% of new lines catches 34% of future blocks; a random check, 20%.")
    page.wait_for_timeout(4500)
    glide(page, 650)
    caption(page, "This simple rate beat two LightGBM models every month. Shown as it came out.")
    page.wait_for_timeout(4500)
    caption(page, "")
    return recording.stop()


def encode(listing: Path) -> None:
    MEDIA.mkdir(parents=True, exist_ok=True)
    mp4, gif = MEDIA / "invoice-block-radar-demo.mp4", MEDIA / "invoice-block-radar-demo.gif"
    ffmpeg = ["ffmpeg", "-y", "-loglevel", "error"]
    subprocess.run(
        [*ffmpeg, "-f", "concat", "-safe", "0", "-i", str(listing), "-vf", "fps=25,format=yuv420p",
         "-c:v", "libx264", "-crf", "24", "-preset", "slow", "-movflags", "+faststart", str(mp4)],
        check=True,
    )
    palette = listing.with_name("palette.png")
    scale = "fps=6,scale=880:-1:flags=lanczos"
    subprocess.run([*ffmpeg, "-i", str(mp4), "-vf", f"{scale},palettegen=max_colors=64", str(palette)], check=True)
    subprocess.run(
        [*ffmpeg, "-i", str(mp4), "-i", str(palette), "-lavfi",
         f"{scale}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4", str(gif)],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://localhost:3000")
    parser.add_argument("--chromium", help="path to a Chromium binary")
    args = parser.parse_args()
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is needed for the video.")
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
        browser = p.chromium.launch(**({"executable_path": args.chromium} if args.chromium else {}))
        page = browser.new_page(viewport=SIZE, color_scheme="light")
        page.set_default_timeout(60_000)
        encode(film(page, args.url.rstrip("/"), Path(tmp) / "frames"))
        browser.close()
    print("Written: docs/media/invoice-block-radar-demo.mp4 and .gif")


if __name__ == "__main__":
    main()
