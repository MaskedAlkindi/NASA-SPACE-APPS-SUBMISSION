"""Write the shared system sketch: web/public/landing/architecture.svg."""
import base64
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "web" / "public" / "landing" / "architecture.svg"

woff = base64.b64encode(
    (ROOT / "web/node_modules/@fontsource/patrick-hand/files/patrick-hand-latin-400-normal.woff").read_bytes()
).decode()
logo_im = Image.open(ROOT / "web/public/logo.png").convert("RGBA")
logo_im.thumbnail((160, 160))
buf = BytesIO()
logo_im.save(buf, format="PNG")
logo = base64.b64encode(buf.getvalue()).decode()

# SpaceSketch paths, copied so the doodles match the landing page.
MOON = """
<path d="M70 14C44 16 24 38 25 63s23 45 48 44c-21-7-34-25-33-47 1-20 12-37 30-46Z"/>
<path d="M68 16C47 22 34 40 36 62c1 19 14 36 35 43" opacity=".35"/>
<path d="M44 52q3 3 7 0m-12 15q5 4 9 0"/><path d="M53 78q-4 4-9 1"/>
<circle cx="40" cy="42" r="3" opacity=".5"/><circle cx="48" cy="92" r="2.5" opacity=".5"/>
<path d="M90 30v10m-5-5h10M100 70v8m-4-4h8M84 96l2 4 4 2-4 2-2 4-2-4-4-2 4-2Z"/>
"""
STARS = """
<path d="M30 22l5 12 13 1-10 8 4 13-12-7-11 7 3-13-10-8 13-1Z"/>
<path d="M84 60l3 8 9 1-7 5 3 9-8-5-8 5 2-9-7-5 9-1Z"/>
<path d="M44 88v12m-6-6h12M92 20v10m-5-5h10M70 36l1 3 3 1-3 1-1 3-1-3-3-1 3-1Z"/>
<path d="M34 44c10 14 30 20 46 20" stroke-dasharray="2 5" opacity=".5"/>
"""
ROCKET = """
<path d="M47 75C33 47 61 18 82 13 93 38 79 66 60 80Z"/>
<path d="m48 43-22 10 1 23 19-9m27-6 1 23-20 14-1-19"/><circle cx="65" cy="40" r="10"/>
<path d="M43 82 32 106 53 91M39 81l-15 18m31-10-11 22M20 22v11m-5-6h10M96 85v10m-5-5h10"/>
"""
SATELLITE = """
<path d="m46 42 27 12-16 30-27-12Z"/>
<path d="m40 40-22-12-15 26 24 13m46-10 28 13-15 24-25-12M45 44l-12 23m27-16-14 23M18 33l-8 18m19-12-8 18m59 7-9 18m21-12-9 18M55 41l8-17m-7-4 14 7M50 85l-3 16"/>
<circle cx="64" cy="22" r="4"/>
"""
ASTRONAUT = """
<circle cx="60" cy="38" r="20"/>
<path d="M47 34c4-9 22-9 26 0 1 8-5 12-13 12s-14-4-13-12Z"/>
<path d="M44 56c-8 4-12 14-11 26l12 1 2-14m26-13c8 4 12 14 11 26l-12 1-2-14"/>
<path d="M46 60h28l-2 30H48Z"/><path d="M48 90l-3 18h12l3-16 3 16h12l-3-18"/>
<path d="M54 68h12v8H54Z" opacity=".6"/>
<path d="M77 60c10-6 22-4 30 4" stroke-dasharray="3 4" opacity=".5"/>
<path d="M16 20v8m-4-4h8M100 100v8m-4-4h8"/>
"""


def box(x, y, w, h, seed):
    j = [6, -4, 5, -5, 4, -3, 5, -6, 3][seed % 9]
    return (
        f"M {x+12} {y+j*0.15:.1f} "
        f"C {x+w*0.4:.0f} {y-4} {x+w*0.7:.0f} {y+5} {x+w-10} {y+3} "
        f"C {x+w+4} {y+h*0.35:.0f} {x+w-2} {y+h*0.7:.0f} {x+w-6} {y+h-8} "
        f"C {x+w*0.6:.0f} {y+h+5} {x+w*0.3:.0f} {y+h-3} {x+10} {y+h-2} "
        f"C {x-4} {y+h*0.6:.0f} {x+3} {y+h*0.28:.0f} {x+12} {y+2} Z"
    )


def card(x, y, w, h, title, sub, stroke, seed, title_fill="#ece7dc"):
    mid = x + w / 2
    title_y = y + (h * 0.40 if sub else h * 0.56)
    sub_y = y + h * 0.72
    sub_svg = (
        f'<text x="{mid}" y="{sub_y}" fill="#a9b0c0" font-size="16">{sub}</text>' if sub else ""
    )
    return f"""
    <path d="{box(x, y, w, h, seed)}" fill="#151a2c" stroke="{stroke}" stroke-width="2.2" filter="url(#rough)"/>
    <text x="{mid}" y="{title_y}" fill="{title_fill}" font-size="22">{title}</text>
    {sub_svg}
    """


def doodle(paths, tx, ty, scale):
    return f'<g transform="translate({tx} {ty}) scale({scale})" fill="none" stroke="#ece7dc" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{paths}</g>'


svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1400 640" role="img" aria-labelledby="archTitle archDesc">
  <title id="archTitle">HEALTH-01 system</title>
  <desc id="archDesc">Phones, check-ins and cabin sensors feed one HEALTH-01 server. NASA hazards, risks and evidence reports sit above it. The exercise module counts reps on the phone and keeps the video there. Alerts use each astronaut's own days, and a person decides.</desc>
  <style>
    @font-face {{
      font-family: "Patrick Hand";
      src: url("data:font/woff;base64,{woff}") format("woff");
      font-weight: 400;
    }}
    text {{ font-family: "Patrick Hand", cursive; text-anchor: middle; }}
  </style>
  <defs>
    <filter id="rough" x="-8%" y="-12%" width="116%" height="124%">
      <feTurbulence type="fractalNoise" baseFrequency="0.012" numOctaves="2" seed="4" result="n"/>
      <feDisplacementMap in="SourceGraphic" in2="n" scale="2.4"/>
    </filter>
  </defs>

  <path d="M700 22 C1080 8 1335 110 1348 310 C1360 510 1120 626 700 622 C270 628 48 520 42 312 C36 118 310 34 700 22"
        fill="none" stroke="#8fdcec" stroke-width="1.7" stroke-dasharray="8 9" stroke-linecap="round" opacity=".7" filter="url(#rough)"/>

  {doodle(MOON, 18, 8, 0.52)}
  {doodle(STARS, 1268, 12, 0.5)}
  {doodle(ROCKET, 1308, 118, 0.42)}
  {doodle(SATELLITE, 16, 500, 0.46)}
  {doodle(ASTRONAUT, 1292, 488, 0.42)}

  <text x="210" y="128" fill="#ffd66b" font-size="18">from the crew</text>
  <text x="1190" y="150" fill="#ffd66b" font-size="18">what comes out</text>

  {card(70, 142, 280, 70, "Apple Health", "the watch, on the iPhone", "#ece7dc", 1)}
  {card(70, 224, 280, 70, "Health Connect", "the watch, on Android", "#ece7dc", 2)}
  {card(70, 306, 280, 70, "check-ins", "how you feel", "#ece7dc", 3)}
  {card(70, 388, 280, 70, "cabin", "CO₂, air, radiation", "#ece7dc", 4)}

  {card(490, 28, 420, 86, "NASA resources", "hazards, risks, evidence reports", "#ffd66b", 5, "#ffd66b")}

  <path d="M700 118 C706 150 694 170 700 198" fill="none" stroke="#8fdcec" stroke-width="1.8" stroke-linecap="round" filter="url(#rough)"/>
  <path d="M692 188 L700 202 L708 188" fill="none" stroke="#8fdcec" stroke-width="1.8" stroke-linecap="round"/>

  <path d="M352 176 C400 176 440 228 492 236" fill="none" stroke="#8fdcec" stroke-width="1.7" stroke-linecap="round"/>
  <path d="M352 258 C400 258 440 270 492 276" fill="none" stroke="#8fdcec" stroke-width="1.7" stroke-linecap="round"/>
  <path d="M352 340 C400 340 440 320 492 316" fill="none" stroke="#8fdcec" stroke-width="1.7" stroke-linecap="round"/>
  <path d="M352 422 C400 422 440 360 492 348" fill="none" stroke="#8fdcec" stroke-width="1.7" stroke-linecap="round"/>
  <path d="M480 228 L492 236 L480 244 M480 268 L492 276 L480 284 M480 308 L492 316 L480 324 M480 340 L492 348 L480 356" fill="none" stroke="#8fdcec" stroke-width="1.7" stroke-linecap="round"/>

  <path d="M900 250 C980 230 990 190 1048 196" fill="none" stroke="#8fdcec" stroke-width="1.7" stroke-linecap="round"/>
  <path d="M900 295 C990 295 1000 292 1048 286" fill="none" stroke="#8fdcec" stroke-width="1.7" stroke-linecap="round"/>
  <path d="M900 340 C980 360 1000 390 1048 386" fill="none" stroke="#8fdcec" stroke-width="1.7" stroke-linecap="round"/>
  <path d="M1040 190 L1048 198 L1040 206 M1040 278 L1048 286 L1040 294 M1040 378 L1048 386 L1040 394" fill="none" stroke="#8fdcec" stroke-width="1.7" stroke-linecap="round"/>

  <path d="{box(500, 198, 400, 196, 6)}" fill="#12182c" stroke="#8fdcec" stroke-width="2.6" filter="url(#rough)"/>
  <image href="data:image/png;base64,{logo}" x="624" y="208" width="52" height="52"/>
  <text x="700" y="286" fill="#8fdcec" font-size="36">HEALTH-01</text>
  <text x="700" y="322" fill="#ece7dc" font-size="20">one server</text>
  <text x="700" y="352" fill="#a9b0c0" font-size="17">the modules plug in here</text>

  {card(1050, 164, 280, 74, "own baseline", "their earlier days", "#ece7dc", 7)}
  {card(1050, 252, 280, 74, "alerts", "the number, and its page", "#ece7dc", 8)}
  {card(1050, 348, 280, 78, "a person decides", "the flight surgeon", "#ff6b4a", 9, "#ffd66b")}

  <path d="M700 474 C706 450 694 430 700 406" fill="none" stroke="#8fdcec" stroke-width="1.8" stroke-linecap="round"/>
  <path d="M692 418 L700 404 L708 418" fill="none" stroke="#8fdcec" stroke-width="1.8" stroke-linecap="round"/>

  <path d="{box(455, 482, 490, 96, 2)}" fill="#151a2c" stroke="#8fdcec" stroke-width="2.2" filter="url(#rough)"/>
  <text x="700" y="518" fill="#8fdcec" font-size="22">exercise module</text>
  <text x="700" y="548" fill="#a9b0c0" font-size="16">camera counts the reps · video stays on the phone</text>
</svg>
"""

OUT.write_text(svg, encoding="utf-8")
print(OUT, OUT.stat().st_size)
