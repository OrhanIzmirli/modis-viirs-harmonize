"""make_presentation.py: builds docs/presentation.pdf (7 slides, 16:9) with matplotlib.

One question per slide, one dominant visual per slide (real site screenshots in figures/site_*.png),
little text. Needs: matplotlib, qrcode.

    python src/make_presentation.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import qrcode
from matplotlib import font_manager as fm
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch, Rectangle

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "figures"
OUT = ROOT / "docs" / "presentation.pdf"

PAPER, PAPER2, RULE = "#faf7f2", "#f3eee6", "#d9d2c6"
INK, INK2, MUTED, ACCENT = "#1a1816", "#4a4540", "#7a736b", "#c2410c"
SITE = "https://orhanizmirli.github.io/modis-viirs-harmonize/"
REPO = "https://github.com/OrhanIzmirli/modis-viirs-harmonize"


def _family(paths, fallback):
    for p in paths:
        if Path(p).exists():
            fm.fontManager.addfont(p)
            return fm.FontProperties(fname=p).get_name()
    return fallback


SERIF = _family([r"C:\Windows\Fonts\georgia.ttf"], "DejaVu Serif")
for p in (r"C:\Windows\Fonts\georgiab.ttf", r"C:\Windows\Fonts\georgiai.ttf"):
    if Path(p).exists():
        fm.fontManager.addfont(p)
SERIFS = [SERIF, "DejaVu Serif"]  # DejaVu supplies glyphs Georgia lacks (→)
MONO = _family([r"C:\Windows\Fonts\consola.ttf"], "DejaVu Sans Mono")
SANS = _family([r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"], "DejaVu Sans")
plt.rcParams["pdf.fonttype"] = 42

W, H = 13.333, 7.5
TOTAL = 7


def slide(n, title, sub=None):
    fig = plt.figure(figsize=(W, H), facecolor=PAPER)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")
    if n > 1:
        ax.text(0.6, 6.72, f"{n:02d}", family=MONO, size=15, color=ACCENT, va="center")
        ax.text(1.2, 6.72, title, family=SERIFS, size=32, color=INK, weight="bold", va="center")
        if sub:
            ax.text(1.2, 6.18, sub, family=SANS, size=15, color=INK2, va="center")
    ax.plot([0.6, W - 0.6], [0.55, 0.55], color=RULE, lw=0.8)
    ax.text(0.6, 0.28, "THE FIRE ALMANAC OF TÜRKIYE  ·  FIREWATCH TR  ·  NASA SPACE APPS 2026", family=MONO,
            size=9.5, color=MUTED)
    ax.text(W - 0.6, 0.28, f"{n} / {TOTAL}", family=MONO, size=9.5, color=MUTED, ha="right")
    return fig, ax


def image(fig, src, x, y, w, h, crop=None, frame=True):
    """Place an image (path or array) in the box (inches), aspect kept, centred.
    crop = (x0, x1, y0, y1) as fractions of the image (y from top)."""
    img = plt.imread(src) if isinstance(src, (str, Path)) else src
    if crop:
        ih, iw = img.shape[:2]
        img = img[int(crop[2] * ih):int(crop[3] * ih), int(crop[0] * iw):int(crop[1] * iw)]
    ih, iw = img.shape[:2]
    s = min(w / iw, h / ih)
    dw, dh = iw * s, ih * s
    x0, y0 = x + (w - dw) / 2, y + (h - dh) / 2
    a = fig.add_axes([x0 / W, y0 / H, dw / W, dh / H]); a.imshow(img, interpolation="lanczos")
    a.set_xticks([]); a.set_yticks([])
    for sp in a.spines.values():
        sp.set_visible(frame); sp.set_color(RULE); sp.set_linewidth(1.0)
    return x0, y0, dw, dh


def label(ax, x, y, text, color=ACCENT, size=11, **kw):
    return ax.text(x, y, text, family=MONO, size=size, color=color, **kw)


def link(ax, x, y, text, url, size=15, **kw):
    t = ax.text(x, y, text, family=MONO, size=size, color=ACCENT, **kw)
    t.set_url(url)
    return t


def numbered(ax, x, y, w, items, size=14, numsize=20):
    """Row of numbered features: [(no, head, words), ...] across width w."""
    cw = w / len(items)
    for i, (no, head, words) in enumerate(items):
        cx = x + i * cw
        ax.text(cx, y, no, family=MONO, size=numsize, color=ACCENT, weight="bold", va="top")
        ax.text(cx + 0.62, y - 0.02, head, family=SERIFS, size=size + 2, color=INK, weight="bold", va="top")
        ax.text(cx + 0.62, y - 0.42, words, family=SANS, size=size - 1, color=INK2, va="top", linespacing=1.25)


pages = []

# 1 — cover: title left, the site on a phone right --------------------------------------------
fig, ax = slide(1, "")
ax.add_patch(Rectangle((0.6, 1.25), 0.08, 5.35, fc=ACCENT, ec="none"))
label(ax, 1.0, 6.45, "NASA SPACE APPS CHALLENGE 2026  ·  ANKARA", size=14, va="top")
ax.text(1.0, 5.65, "The Fire Almanac\nof Türkiye", family=SERIFS, size=56, color=INK, weight="bold", va="top",
        linespacing=1.05)
ax.text(1.0, 3.35, "Harmonization of MODIS and VIIRS Hot Spots", family=SERIFS, size=24, color=INK2,
        style="italic", va="top")
ax.text(1.0, 2.55, "Team FireWatch TR", family=SANS, size=20, color=INK, va="top")
label(ax, 1.0, 1.75, "LIVE SITE", color=MUTED)
link(ax, 2.3, 1.75, SITE.replace("https://", ""), SITE, size=14)
label(ax, 1.0, 1.35, "REPO", color=MUTED)
link(ax, 2.3, 1.35, REPO.replace("https://", ""), REPO, size=14)
px, py, pw, ph = 9.55, 0.85, 2.95, 5.9
ax.add_patch(FancyBboxPatch((px, py), pw, ph, boxstyle="round,pad=0,rounding_size=0.32", fc=INK, ec=INK))
image(fig, FIG / "site_phone.png", px + 0.13, py + 0.2, pw - 0.26, ph - 0.4, crop=(0, 1, 0, 0.82), frame=False)
pages.append(fig)

# 2 — what's broken --------------------------------------------------------------------------
fig, ax = slide(2, "What's broken?",
                "Two NASA satellite records describe the same fires in different ways.")
image(fig, FIG / "slide_before_after.png", 0.6, 0.95, 6.9, 4.85, crop=(0, 0.5, 0.135, 0.93))
label(ax, 0.6, 0.72, "ONE AFTERNOON NEAR MANAVGAT, 29 JUL 2021: 1,540 ROWS FOR 3 FIRES", color=MUTED, size=10)
pts = [("1 km  vs  375 m", "MODIS pixels are 7× larger\nthan VIIRS pixels."),
       ("0–100  vs  low · nominal · high", "Confidence on two scales\nthat do not compare."),
       ("One fire, many rows", "Two sensors, many passes:\nthe same fire, counted again.")]
for i, (h_, b) in enumerate(pts):
    y = 5.55 - i * 1.55
    ax.add_patch(Rectangle((7.9, y - 1.15), 0.06, 1.15, fc=ACCENT, ec="none"))
    ax.text(8.2, y, h_, family=SERIFS, size=20, color=INK, weight="bold", va="top")
    ax.text(8.2, y - 0.5, b, family=SANS, size=15, color=INK2, va="top", linespacing=1.3)
ax.text(7.9, 0.95, "FireWatch TR, our free alert app on Google Play, notifies\n"
        "people when NASA FIRMS detects fire near their places.\n"
        "Context needs 25 years of both records.",
        family=SANS, size=11.5, color=MUTED, va="center", linespacing=1.35)
pages.append(fig)

# 3 — how we fix it --------------------------------------------------------------------------
fig, ax = slide(3, "How we fix it", "Four steps turn two archives into one list of fire events.")
image(fig, FIG / "slide_before_after.png", 0.6, 2.35, W - 1.2, 3.55, crop=(0, 1, 0.135, 0.93))
numbered(ax, 0.6, 1.95, W - 1.2, [
    ("1", "One schema", "same columns for\nevery detection"),
    ("2", "One confidence", "both scales\nmapped to 0–1"),
    ("3", "One event", "footprints touch,\n≤ 12 h apart"),
    ("4", "Trust Score", "higher when both\nsatellites agree")], size=14)
pages.append(fig)

# 4 — the product ----------------------------------------------------------------------------
fig, ax = slide(4, "The product",
                "988,698 detections → 448,364 fire events: 2.2 records per fire, 2001–2025.")
image(fig, FIG / "site_map.png", 0.6, 1.95, W - 1.2, 3.95)
numbered(ax, 0.6, 1.62, W - 1.2, [
    ("01", "Calendar", "every week since\n2001, at a glance"),
    ("02", "Trust Score", "how sure we are,\nper fire"),
    ("03", "Live map", "any week, any\nprovince"),
    ("04", "Education", "sourced facts\nbefore the season"),
    ("05", "Open data", "three files,\nMIT license")], size=12.5, numsize=15)
pages.append(fig)

# 5 — does it work ---------------------------------------------------------------------------
fig, ax = slide(5, "Does it work? We checked.", "Same fire, two satellites, minutes apart: do they agree?")
image(fig, FIG / "slide_frp_scatter.png", 0.6, 0.85, 5.1, 5.05, crop=(0, 1, 0, 0.935))
stats = [("r = 0.69", "fire energy, MODIS vs VIIRS,\n25,171 same-fire pairs ≤ 30 min apart"),
         ("8.7%", "of fire-days seen by both satellites:\nneither one alone sees the season"),
         ("r = 0.76", "vs official OGM burnt area (log), 14 Aegean/\nMediterranean provinces, Jun–Oct, 2001–24"),
         ("≤ 6%", "change in event count when distance and\ntime thresholds move ±50% (2021)")]
for i, (k, t) in enumerate(stats):
    y = 5.75 - i * 1.25
    ax.text(6.3, y, k, family=SERIFS, size=30, color=ACCENT, weight="bold", va="top")
    ax.text(9.0, y - 0.05, t, family=SANS, size=14, color=INK, va="top", linespacing=1.3)
pages.append(fig)

# 6 — who needs this -------------------------------------------------------------------------
fig, ax = slide(6, "Who needs this?", "Three people the site was written for, in its own words.")
image(fig, FIG / "site_who.png", 0.6, 3.15, W - 1.2, 2.75, crop=(0.105, 0.895, 0.31, 0.95))
image(fig, FIG / "site_learn.png", 0.6, 0.95, 4.0, 1.85, crop=(0.105, 0.895, 0.04, 0.42))
label(ax, 0.6, 2.88, "EDUCATION LAYER", size=10)
image(fig, FIG / "site_data.png", 4.85, 0.95, 4.0, 1.85, crop=(0.105, 0.895, 0.06, 0.62))
label(ax, 4.85, 2.88, "OPEN DATA DOWNLOADS", size=10)
label(ax, 9.2, 2.75, "NEXT", size=12, weight="bold", va="top")
ax.text(9.2, 2.3, "FireWatch TR integration:\nalerts with 25 years of\ncontext\n\nNews confirmation\nfor more major fires",
        family=SANS, size=14, color=INK, va="top", linespacing=1.3)
pages.append(fig)

# 7 — limits, next steps & references + try it yourself -------------------------------------
fig, ax = slide(7, "Limits, next steps & references")
label(ax, 0.6, 5.95, "LIMITS", size=12, va="top")
limits = ["Detections are not fire reports: clouds, smoke and canopy hide fires.",
          "More satellites from 2012, 2018, 2023: counts are not homogeneous.",
          "Thresholds (12 h, 0.375 km) are reasoned defaults, tested at ±50%.",
          "Province = event centroid."]
for i, t in enumerate(limits):
    ax.text(0.6, 5.55 - i * 0.36, "—  " + t, family=SANS, size=12.5, color=INK, va="top")
label(ax, 0.6, 3.95, "NEXT", size=12, va="top")
ax.text(0.6, 3.6, "—  FireWatch TR integration   —  news confirmation of major fires", family=SANS, size=12.5,
        color=INK, va="top")
refs = [("NASA FIRMS", "https://firms.modaps.eosdis.nasa.gov/"),
        ("MODIS C6/C6.1 Active Fire User's Guide", "https://modis-fire.umd.edu/files/MODIS_C6_C6.1_Fire_User_Guide_1.0.pdf"),
        ("VIIRS 375 m Active Fire User's Guide v1.4", "https://viirsland.gsfc.nasa.gov/PDF/VIIRS_activefire_User_Guide.pdf"),
        ("NASA GISTEMP v4", "https://data.giss.nasa.gov/gistemp/"),
        ("OGM Ormancılık İstatistikleri 2024", "https://www.ogm.gov.tr/"),
        ("geoBoundaries ADM1 / © OpenStreetMap", "https://www.geoboundaries.org/"),
        ("Esri basemap", "https://www.esri.com/"),
        ("Anadolu Ajansı news reports", "https://www.aa.com.tr/"),
        ("FAO Unasylva 162", "https://www.fao.org/4/t9500e/t9500e02.htm"),
        ("NOAA NSSL · US NPS", "https://www.nps.gov/articles/wildland-fire-behavior.htm"),
        ("OGM harvest-season guidance", "https://www.ogm.gov.tr/tr/haberler/hasat-mevsiminde-orman-yangini-alarmi"),
        ("NASA Earthdata FIRMS FAQ", "https://www.earthdata.nasa.gov/faq/firms-faq")]
label(ax, 0.6, 3.0, "REFERENCES", size=12, va="top")
for i, (t, u) in enumerate(refs):
    col, row = divmod(i, 6)
    x, y = 0.6 + col * 3.85, 2.62 - row * 0.32
    label(ax, x, y, f"[{i + 1}]", color=MUTED, size=10, va="top")
    ax.text(x + 0.45, y, t, family=SANS, size=11, color=INK, va="top").set_url(u)
# try it yourself panel
bx, by, bw, bh = 8.6, 0.85, 4.13, 5.3
ax.add_patch(FancyBboxPatch((bx, by), bw, bh, boxstyle="round,pad=0,rounding_size=0.08", fc=PAPER2, ec=RULE))
ax.add_patch(Rectangle((bx, by + bh - 0.07), bw, 0.07, fc=ACCENT, ec="none"))
ax.text(bx + 0.3, by + bh - 0.35, "Try it yourself", family=SERIFS, size=26, color=INK, weight="bold", va="top")
q = qrcode.QRCode(border=1, error_correction=qrcode.constants.ERROR_CORRECT_M)
q.add_data(SITE); q.make(fit=True)
qr = np.array(q.make_image(fill_color=INK, back_color=PAPER2).convert("RGB"))
image(fig, qr, bx + 0.3, by + 1.6, 2.2, 2.2, frame=False)
ax.text(bx + 2.65, by + 3.6, "Scan with\nyour phone", family=SANS, size=14, color=INK2, va="top", linespacing=1.3)
link(ax, bx + 0.3, by + 1.25, "orhanizmirli.github.io/\nmodis-viirs-harmonize", SITE, size=12.5, va="top",
     linespacing=1.3)
ax.text(bx + 0.3, by + 0.45, "Works on any phone · no login · ~1.5 MB", family=SANS, size=12.5, color=INK, va="center")
pages.append(fig)

assert len(pages) == TOTAL
with PdfPages(OUT, metadata={"Title": "The Fire Almanac of Türkiye", "Author": "Team FireWatch TR"}) as pdf:
    for f in pages:
        pdf.savefig(f, facecolor=PAPER)
        plt.close(f)
print(OUT)
