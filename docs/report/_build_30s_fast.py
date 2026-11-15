"""Build the fast 30-second deck. Same notebook look as HEALTH-01_30_seconds.pptx."""
from io import BytesIO
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "HEALTH-01_30_seconds_fast.pptx"

INK = RGBColor(0xEC, 0xE7, 0xDC)
GOLD = RGBColor(0xFF, 0xD6, 0x6B)
MUTED = RGBColor(0xA9, 0xB0, 0xC0)
RULE = "1C243A"
RED = "FF6B4A"
PAPER = "0C0F1C"

W = 12191695
H = 6858000


def rgb(h):
    return RGBColor.from_string(h)


def set_run(run, text, name, size, color):
    run.text = text
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = False
    run.font.italic = False
    run.font.color.rgb = color
    # Force latin typeface so PowerPoint does not swap in Calibri.
    rpr = run._r.get_or_add_rPr()
    for tag in ("latin", "cs", "ea"):
        el = rpr.find(qn(f"a:{tag}"))
        if el is None:
            el = rpr.makeelement(qn(f"a:{tag}"), {})
            rpr.append(el)
        el.set("typeface", name)


def add_text(slide, l, t, w, h, lines, name, size, color, align=PP_ALIGN.LEFT, spacing=1.0):
    box = slide.shapes.add_textbox(Emu(l), Emu(t), Emu(w), Emu(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.auto_size = None
    tf.margin_left = Emu(0)
    tf.margin_right = Emu(0)
    tf.margin_top = Emu(0)
    tf.margin_bottom = Emu(0)
    body = tf._txBody.bodyPr
    body.set("anchor", "t")
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_before = Pt(0)
        p.space_after = Pt(size * 0.28)
        p.line_spacing = spacing
        set_run(p.add_run(), line, name, size, color)
    return box


def rect(slide, l, t, w, h, fill):
    sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(l), Emu(t), Emu(w), Emu(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = rgb(fill)
    sh.line.fill.background()
    # Keep notebook lines behind the words.
    sp = sh._element
    slide.shapes._spTree.remove(sp)
    slide.shapes._spTree.insert(2, sp)
    return sh


def notebook(slide):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = rgb(PAPER)
    for y in (1097280, 2194560, 3291840, 4389120, 5486400):
        rect(slide, 0, y, W, 10972, RULE)
    rect(slide, 384048, 0, 27432, H, RED)


def picture(slide, path, l, t, w, h):
    pic = slide.shapes.add_picture(str(path), Emu(l), Emu(t), Emu(w), Emu(h))
    pic.line.fill.background()
    return pic


def png_bytes(path, crop=None):
    im = Image.open(path).convert("RGBA")
    if crop:
        im = im.crop(crop)
    buf = BytesIO()
    im.save(buf, format="PNG")
    buf.seek(0)
    return buf


def chrome(slide, when, page, pages=5):
    notebook(slide)
    # Team logo and the sleepy-moon sketch, every slide.
    picture(slide, ROOT / "LOGO CUSTOM" / "Amerat-01-logo-transperent.png", 10260000, 80000, 860000, 860000)
    picture(slide, ROOT / "web" / "public" / "landing" / "sleepy-moon.png", 11220000, 100000, 860000, 860000)
    add_text(slide, 685800, 230000, 9000000, 340000, [when], "Segoe Print", 16, GOLD)
    add_text(slide, 640080, 6360000, 7800000, 360000,
             ["30 seconds  ·  NASA SPACE APPS SUBMISSION 2026"], "Segoe Print", 12, MUTED)
    add_text(slide, 9800000, 6360000, 1900000, 360000, [f"{page}  /  {pages}"], "Segoe Print", 12, MUTED, align=PP_ALIGN.RIGHT)


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def build():
    prs = Presentation()
    prs.slide_width = Emu(W)
    prs.slide_height = Emu(H)
    prs.core_properties.title = "HEALTH-01 — 30 seconds"
    prs.core_properties.subject = "NASA Space Apps 2026"
    blank = prs.slide_layouts[6]

    # --- title ---
    s = prs.slides.add_slide(blank)
    notebook(s)
    picture(s, ROOT / "web" / "public" / "landing" / "sleepy-moon.png", 11220000, 100000, 860000, 860000)
    picture(s, ROOT / "LOGO CUSTOM" / "Amerat-01-logo-transperent.png", 4495000, 420000, 3200000, 3200000)
    add_text(s, 1200000, 3720000, 9800000, 780000, ["HEALTH-01"], "Ink Free", 54, INK, align=PP_ALIGN.CENTER)
    add_text(s, 1200000, 4520000, 9800000, 520000, ["Team Amerat 01"], "Segoe Print", 32, GOLD, align=PP_ALIGN.CENTER)
    add_text(s, 1200000, 5120000, 9800000, 480000, ["Hajid Alkindi"], "Segoe Print", 28, INK, align=PP_ALIGN.CENTER)
    add_text(s, 640080, 6360000, 7800000, 360000,
             ["30 seconds  ·  NASA SPACE APPS SUBMISSION 2026"], "Segoe Print", 12, MUTED)
    add_text(s, 9800000, 6360000, 1900000, 360000, ["1  /  5"], "Segoe Print", 12, MUTED, align=PP_ALIGN.RIGHT)
    notes(s, "Title card. Hold it for a moment, then click.\n\nHajid Alkindi. Team Amerat 01.")

    # --- 1. the system ---
    s = prs.slides.add_slide(blank)
    chrome(s, "0 – 9 seconds", 2)
    # Same drawing as the landing page (web/public/landing/architecture.svg).
    s.shapes.add_picture(str(ROOT / "docs" / "report" / "architecture.png"), Emu(736000), Emu(1020000), Emu(10720000), Emu(4900000))
    notes(s, "\n".join([
        "Say this while you point around the drawing. About 9 seconds. Brisk.",
        "",
        "HEALTH-01 is modular. One server. Each module plugs in on its own.",
        "Phones: Apple Health and Health Connect.",
        "Cabin: the environment module.",
        "Check-ins: how you feel.",
        "Research: NASA HRP and OSDR.",
        "",
        "The drawing is the system. Same figure as the landing page. Doodles sit around it.",
    ]))

    # --- 2. the resources ---
    s = prs.slides.add_slide(blank)
    chrome(s, "9 – 18 seconds", 3)
    add_text(s, 685800, 620000, 9000000, 900000, ["from their resources."], "Ink Free", 36, INK)
    add_text(
        s, 777240, 1750000, 5600000, 4300000,
        [
            " five hazards.",
            " the HRP risk pages, including food.",
            " evidence reports. the page stays on the number.",
            " each astronaut, scored on their own earlier days.",
        ],
        "Segoe Print", 20, INK, spacing=1.08,
    )
    # Drop the left nav so the five hazard cards fill the frame.
    hazards = png_bytes(ROOT / "docs" / "screenshots" / "12-settings-hazards.png", crop=(210, 150, 1440, 860))
    s.shapes.add_picture(hazards, Emu(6600000), Emu(1900000), Emu(5200000), Emu(3000000))
    notes(s, "\n".join([
        "Say this, then click. Land by 18 seconds.",
        "",
        "We built it from the resources on the challenge page, then followed their links.",
        "Five hazards. The HRP risk pages, including inadequate food and nutrition. The evidence reports.",
        "Every number we kept has its page.",
        "That is why we measure these things, and why each astronaut is scored against their own earlier days.",
        "",
        "On screen: the hazards page in the app, taken from those NASA pages.",
    ]))

    # --- 3. exercise on the devices ---
    s = prs.slides.add_slide(blank)
    chrome(s, "18 – 27 seconds", 4)
    add_text(s, 685800, 620000, 9000000, 800000, ["exercise, and the food log."], "Ink Free", 32, INK)
    add_text(
        s, 777240, 1550000, 5600000, 4500000,
        [
            " the camera counts each rep.",
            " the video stays on the device.",
            " meals, fluid and body mass are logged.",
            " a short day shows on the rings.",
            " example marks. not a menu.",
        ],
        "Segoe Print", 18, INK, spacing=1.0,
    )
    ios = ROOT / "web" / "public" / "landing" / "phones" / "ios-exercise.jpg"
    android = ROOT / "web" / "public" / "landing" / "phones" / "android-exercise.jpg"
    # Phone shots are 739×1600. Keep that ratio so the screens are not stretched.
    s.shapes.add_picture(str(ios), Emu(6900000), Emu(1580000), Emu(2100000), Emu(4550000))
    s.shapes.add_picture(str(android), Emu(9200000), Emu(1580000), Emu(2100000), Emu(4550000))
    notes(s, "\n".join([
        "Start the device clip as you click in. About 9 seconds. The stills are the iPhone and Android exercise screens, if the clip is late.",
        "",
        "Exercise runs on the phone. The camera counts each rep. The video stays on the device.",
        "Nutrition is the food log: meals, fluid and body mass. A short day shows on the rings.",
        "The marks are examples, not a flight menu.",
        "",
        "Do not count reps live in this cut.",
    ]))

    # --- 4. close ---
    s = prs.slides.add_slide(blank)
    chrome(s, "27 – 30 seconds", 5)
    add_text(s, 685800, 620000, 7000000, 1600000, ["a person still decides."], "Ink Free", 36, INK)
    add_text(
        s, 777240, 2400000, 6200000, 2200000,
        [
            " research prototype.",
            " health, training and food, for the people on board.",
        ],
        "Segoe Print", 24, INK, spacing=1.05,
    )
    s.shapes.add_picture(png_bytes(ROOT / "web" / "public" / "landing" / "me-and-space-donkey.webp"),
                         Emu(7000000), Emu(2300000), Emu(4600000), Emu(3200000))
    notes(s, "\n".join([
        "Say this and stop. Do not open another topic.",
        "",
        "A person still decides. Research prototype.",
        "",
        "Whole cut is about 100 words. Read it briskly. That is the 30 seconds.",
    ]))

    tmp = OUT.with_suffix(".tmp.pptx")
    prs.save(tmp)
    try:
        tmp.replace(OUT)
        print(OUT)
    except PermissionError:
        fallback = OUT.with_name(OUT.stem + "_system.pptx")
        tmp.replace(fallback)
        print("locked, wrote", fallback)


if __name__ == "__main__":
    build()
