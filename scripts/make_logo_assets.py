"""Generate every logo/icon size used by the web, iOS and Android apps from the team logo.

    pip install pillow
    python scripts/make_logo_assets.py            # run from the repository root

Source: LOGO CUSTOM/Amerat-01-logo-transperent.png (2048x2048, transparent outside the sticker).
Re-run after replacing the logo file.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "LOGO CUSTOM" / "Amerat-01-logo-transperent.png"
BRAND_BLUE = (0, 92, 150)          # steel blue taken from the logo outline


def square(img: Image.Image, size: int) -> Image.Image:
    return img.resize((size, size), Image.LANCZOS)


def on_background(img: Image.Image, size: int, pad: float = 0.06) -> Image.Image:
    """Opaque square icon (app stores reject transparency): logo on the brand blue."""
    canvas = Image.new("RGB", (size, size), BRAND_BLUE)
    inner = int(size * (1 - 2 * pad))
    logo = square(img, inner)
    canvas.paste(logo, ((size - inner) // 2, (size - inner) // 2), logo)
    return canvas


def save(img: Image.Image, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, optimize=True)
    print("wrote", path.relative_to(ROOT))


def main():
    logo = Image.open(SRC).convert("RGBA")

    # Web
    web = ROOT / "web" / "public"
    save(square(logo, 512), web / "logo.png")
    save(square(logo, 64), web / "favicon.png")
    save(on_background(logo, 180), web / "apple-touch-icon.png")

    # iOS app icon (single 1024 universal size, no alpha)
    appicon = ROOT / "ios" / "HealthMonitor" / "HealthMonitor" / "Assets.xcassets" / "AppIcon.appiconset"
    save(on_background(logo, 1024), appicon / "AppIcon-1024.png")
    (appicon / "Contents.json").write_text(json.dumps({
        "images": [{"filename": "AppIcon-1024.png", "idiom": "universal", "platform": "ios", "size": "1024x1024"}],
        "info": {"author": "xcode", "version": 1}}, indent=2))
    # iOS in-app logo
    imgset = appicon.parent / "TeamLogo.imageset"
    save(square(logo, 512), imgset / "TeamLogo.png")
    (imgset / "Contents.json").write_text(json.dumps({
        "images": [{"filename": "TeamLogo.png", "idiom": "universal"}], "info": {"author": "xcode", "version": 1}}, indent=2))

    # Android launcher icons + in-app logo
    res = ROOT / "android" / "app" / "src" / "main" / "res"
    for density, px in {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}.items():
        save(on_background(logo, px), res / f"mipmap-{density}" / "ic_launcher.png")
    save(square(logo, 512), res / "drawable-nodpi" / "team_logo.png")


if __name__ == "__main__":
    main()
