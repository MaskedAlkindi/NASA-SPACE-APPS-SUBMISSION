"""Turn NASA web pages and PDF reports into plain text with section headings."""
from __future__ import annotations

import html as htmllib
import io
import re


def page_sections(raw_html: str) -> dict:
    """Return {"title", "sections": {heading: text}, "text", "links"} for a nasa.gov article page."""
    title_m = re.search(r"<title>(.*?)</title>", raw_html, re.S)
    title = htmllib.unescape(title_m.group(1)).replace(" - NASA", "").strip() if title_m else ""
    m = re.search(r'class="[^"]*entry-content[^"]*"(.*)', raw_html, re.S)
    body = (m.group(1) if m else raw_html).split("<footer")[0]
    links = sorted(set(re.findall(r'href="([^"#]+)"', body)))
    body = re.sub(r"<(script|style|svg|figure|noscript|nav)[^>]*>.*?</\1>", " ", body, flags=re.S)
    body = re.sub(r"<h[1-6][^>]*>", "\n## ", body)
    body = re.sub(r"</(p|li|h[1-6]|div|tr)>", "\n", body)
    body = re.sub(r"<li[^>]*>", "\n- ", body)
    text = htmllib.unescape(re.sub(r"<[^>]+>", " ", body))
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    # Drop navigation and "related content" tails.
    text = re.split(r"\n## (Related Content|Related Articles|Related Terms|Keep Exploring)\b", text)[0]
    sections: dict[str, str] = {}
    current = "intro"
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("## "):
            current = line[3:].strip() or current
            continue
        if line and line not in ("Read More", "Learn More", "Watch"):
            sections[current] = (sections.get(current, "") + " " + line).strip()
    return {"title": title, "sections": sections, "text": text, "links": links}


def pdf_pages(data: bytes) -> list[str]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return [re.sub(r"\s+", " ", p.extract_text() or "") for p in reader.pages]


def normalise(s: str) -> str:
    """Whitespace/dash/quote-insensitive form used to verify evidence quotes."""
    s = s.replace("–", "-").replace("—", "-").replace("’", "'").replace(" ", " ")
    return re.sub(r"\s+", "", s).lower()
