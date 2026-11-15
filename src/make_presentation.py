"""make_presentation.py: builds docs/presentation.pdf (7 slides, 16:9) with matplotlib.

    python src/make_presentation.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
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
MONO = _family([r"C:\Windows\Fonts\consola.ttf"], "DejaVu Sans Mono")
SANS = _family([r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"], "DejaVu Sans")
plt.rcParams["pdf.fonttype"] = 42

W, H = 13.333, 7.5
TOTAL = 7


def slide(n, kicker, title):
    fig = plt.figure(figsize=(W, H), facecolor=PAPER)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")
    if n > 1:
        ax.text(0.6, 6.95, f"{n:02d}  ·  {kicker.upper()}", family=MONO, size=12, color=ACCENT)
        ax.text(0.6, 6.35, title, family=[SERIF, "DejaVu Serif"], size=30, color=INK, weight="bold", va="center")
        ax.plot([0.6, W - 0.6], [5.92, 5.92], color=RULE, lw=1.2)
    ax.plot([0.6, W - 0.6], [0.55, 0.55], color=RULE, lw=0.8)
    ax.text(0.6, 0.28, "THE FIRE ALMANAC OF TÜRKIYE  ·  FIREWATCH TR", family=MONO, size=9.5, color=MUTED)
    ax.text(W - 0.6, 0.28, f"{n} / {TOTAL}", family=MONO, size=9.5, color=MUTED, ha="right")
    return fig, ax


def image(fig, path, x, y, w, h):
    """Place an image in the box (inches), keeping its aspect ratio, centred."""
    img = plt.imread(path)
    ih, iw = img.shape[:2]
    scale = min(w / iw, h / ih)
    dw, dh = iw * scale, ih * scale
    x0, y0 = x + (w - dw) / 2, y + (h - dh) / 2
    a = fig.add_axes([x0 / W, y0 / H, dw / W, dh / H]); a.imshow(img); a.axis("off")
    return x0, y0, dw, dh


def box(ax, x, y, w, h, label, head, body, size=14):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.06",
                                fc=PAPER2, ec=RULE, lw=1))
    ax.add_patch(Rectangle((x, y + h - 0.06), w, 0.06, fc=ACCENT, ec="none"))
    ax.text(x + 0.25, y + h - 0.4, label, family=MONO, size=11, color=ACCENT, va="top")
    ax.text(x + 0.25, y + h - 0.85, head, family=SERIF, size=19, color=INK, weight="bold", va="top")
    ax.text(x + 0.25, y + h - 1.45, body, family=SANS, size=size, color=INK2, va="top", linespacing=1.4)


def link(ax, x, y, label, url, size=15, **kw):
    t = ax.text(x, y, label, family=MONO, size=size, color=ACCENT, **kw)
    t.set_url(url)
    return t


pages = []

# 1 — cover ---------------------------------------------------------------
fig, ax = slide(1, "", "")
ax.add_patch(Rectangle((0.6, 1.2), 0.08, 5.4, fc=ACCENT, ec="none"))
ax.text(1.0, 6.2, "NASA SPACE APPS CHALLENGE 2026  ·  ANKARA", family=MONO, size=14, color=ACCENT, va="top")
ax.text(1.0, 5.3, "The Fire Almanac\nof Türkiye", family=SERIF, size=60, color=INK, weight="bold", va="top",
        linespacing=1.05)
ax.text(1.0, 2.95, "Harmonization of MODIS and VIIRS Hot Spots", family=SERIF, size=26, color=INK2,
        style="italic", va="top")
ax.text(1.0, 2.15, "Team FireWatch TR", family=SANS, size=20, color=INK, va="top")
ax.text(1.0, 1.55, "LIVE SITE", family=MONO, size=11, color=MUTED)
link(ax, 2.4, 1.55, SITE, SITE, size=14)
ax.text(1.0, 1.15, "REPO", family=MONO, size=11, color=MUTED)
link(ax, 2.4, 1.15, REPO, REPO, size=14)
ax.text(W - 0.9, 6.2, "2001–2025\n81 provinces\n2 sensors · 5 satellites", family=MONO, size=14,
        color=INK2, ha="right", va="top", linespacing=1.6)
pages.append(fig)

# 2 — problem ---------------------------------------------------------------
fig, ax = slide(2, "The problem", "Fires don't surprise us. Our data does.")
ax.text(0.6, 5.45,
        "FireWatch TR, our live app, shows satellite hot spots across Türkiye as they arrive from NASA FIRMS.\n"
        "To put today's fires in context we need 25 years of history, and there two satellite records disagree.",
        family=SANS, size=17, color=INK2, va="top", linespacing=1.45)
cols = [("PIXEL SIZE", "1 km vs 375 m", "MODIS (Terra, Aqua) sees\n1 km pixels; VIIRS (S-NPP,\nNOAA-20, NOAA-21) sees 375 m.\nSmall fires appear only in VIIRS."),
        ("CONFIDENCE", "0–100 vs words", "MODIS gives a number from\n0 to 100; VIIRS gives low,\nnominal or high. The two scales\ncannot be compared as they are."),
        ("DUPLICATES", "One fire, many rows", "Both sensors, several passes\na day: the same fire is\nrecorded again and again.\nCounting rows overstates fires.")]
for i, (k, h_, b) in enumerate(cols):
    box(ax, 0.6 + i * 4.1, 0.95, 3.85, 3.35, k, h_, b, size=15)
pages.append(fig)

# 3 — method ----------------------------------------------------------------
fig, ax = slide(3, "Method", "One language for two satellites")
items = [("1 · COMMON SCHEMA", "Same columns",
          "Every FIRMS row becomes lat, lon, time,\nsensor, satellite, FRP, footprint (scan ×\ntrack), day/night, confidence."),
         ("2 · CONFIDENCE", "One 0–1 score",
          "MODIS: low < 30, nominal 30–79, high ≥ 80.\nVIIRS low / nominal / high on the same\nclasses. Score = confidence / 100."),
         ("3 · FOOTPRINT + MATCHING", "Same fire = one event",
          "Two detections join when their footprints\ntouch (r_i + r_j + 0.375 km) and they are\n≤ 12 h apart. Chains merge (union-find)."),
         ("4 · TRUST SCORE", "Confirmation raises trust",
          "Mean confidence, +30% of the remaining\ndoubt if both sensors saw it, +10% for\nrepeat passes. Halves every 24 h unseen.")]
for i, (k, h_, b) in enumerate(items):
    x, y = 0.6 + (i % 2) * 6.1, 3.15 - (i // 2) * 2.45
    box(ax, x, y, 5.95, 2.3, k, h_, b, size=14.5)
pages.append(fig)

# 4 — result ----------------------------------------------------------------
fig, ax = slide(4, "Result", "988,698 detections → 448,364 fire events")
image(fig, FIG / "slide_before_after.png", 0.6, 1.35, 6.6, 4.35)
image(fig, FIG / "app_calendar.jpg", 7.45, 1.95, 5.3, 3.75)
ax.text(7.45, 1.55, "The almanac calendar on the live site", family=MONO, size=11, color=MUTED)
ax.text(0.6, 0.95, "2.2", family=SERIF, size=30, color=ACCENT, weight="bold", va="center")
ax.text(1.5, 0.95, "records per fire on average, 2001–2025, inside Türkiye's 81 provinces", family=SANS,
        size=17, color=INK, va="center")
pages.append(fig)

# 5 — validation ------------------------------------------------------------
fig, ax = slide(5, "Validation", "Does it work? We checked.")
image(fig, FIG / "slide_frp_scatter.png", 0.6, 2.05, 3.7, 3.7)
image(fig, FIG / "slide_2021_unusual.png", 4.55, 2.05, 8.2, 3.7)
rows = [("8.7%", "of fire-days were seen by both satellites: neither one alone sees the whole season."),
        ("r = 0.76", "with official OGM burnt area (log), 14 Mediterranean/Aegean provinces, Jun–Oct, 2001–2024."),
        ("≤ 6%", "change in event count when distance and time thresholds move ±50% (2021 test).")]
for i, (k, t) in enumerate(rows):
    y = 1.65 - i * 0.42
    ax.text(0.6, y, k, family=MONO, size=16, color=ACCENT, weight="bold", va="center")
    ax.text(2.2, y, t, family=SANS, size=15, color=INK, va="center")
pages.append(fig)

# 6 — users -----------------------------------------------------------------
fig, ax = slide(6, "Users", "Who needs this?")
personas = [("A FIRE MANAGER IN MUĞLA", "Crews in place",
             "Cannot position crews everywhere.\nThe almanac shows which weeks\nhave historically demanded them,\nso teams can be placed before\nthe season starts."),
            ("A FARMER'S NEIGHBOUR IN DİYARBAKIR", "October burns",
             "More fires start in October than\nin any other month. Stubble fires\ncan spread into orchards. The site\nshows when burning peaks and\nwhat to do instead."),
            ("A RESEARCHER, ANYWHERE", "Ready-made events",
             "Matching MODIS and VIIRS takes\ntime. The merged events and every\nharmonized detection are open\ndownloads (CSV, GeoJSON).")]
for i, (k, h_, b) in enumerate(personas):
    box(ax, 0.6 + i * 4.1, 2.0, 3.85, 3.6, k, h_, b, size=14.5)
ax.text(0.6, 1.55, "ALSO ON THE SITE", family=MONO, size=11, color=MUTED, va="center")
ax.text(2.75, 1.55, "Before-the-season notes and 15 sourced fire facts  ·  open data downloads",
        family=SANS, size=15, color=INK, va="center")
ax.text(0.6, 1.0, "NEXT", family=MONO, size=11, color=ACCENT, va="center", weight="bold")
ax.text(2.75, 1.0, "Integrate into the FireWatch TR app  ·  extend news confirmation of major fires",
        family=SANS, size=15, color=INK, va="center")
pages.append(fig)

# 7 — limits & references ---------------------------------------------------
fig, ax = slide(7, "Limits & sources", "Honest limits & references")
limits = ["Detections are not fire reports: clouds,\nsmoke and canopy hide fires.",
          "Record is not homogeneous: more\nsatellites from 2012, 2018, 2023.",
          "Big fires become one event, so energy\n(FRP) shows extremes better than counts.",
          "Thresholds (12 h, 0.375 km) are reasoned\ndefaults, tested at ±50%.",
          "Province = event centroid."]
ax.text(0.6, 5.55, "LIMITS", family=MONO, size=12, color=ACCENT, va="top")
for i, t in enumerate(limits):
    ax.text(0.6, 5.1 - i * 0.85, "—  " + t, family=SANS, size=14, color=INK, va="top", linespacing=1.3)
refs = [("NASA FIRMS active fire data", "https://firms.modaps.eosdis.nasa.gov/"),
        ("MODIS C6.1 Active Fire User's Guide", "https://modis-fire.umd.edu/guides.html"),
        ("VIIRS 375 m Active Fire User's Guide", "https://www.earthdata.nasa.gov/data/instruments/viirs"),
        ("NASA GISTEMP v4", "https://data.giss.nasa.gov/gistemp/"),
        ("OGM Ormancılık İstatistikleri 2024", "https://www.ogm.gov.tr/"),
        ("geoBoundaries ADM1 / © OpenStreetMap", "https://www.geoboundaries.org/"),
        ("Esri basemap", "https://www.esri.com/"),
        ("Anadolu Ajansı news reports", "https://www.aa.com.tr/"),
        ("FAO Unasylva 162 · NOAA NSSL · US NPS", "https://www.fao.org/4/t9500e/t9500e02.htm"),
        ("OGM harvest-season fire guidance", "https://www.ogm.gov.tr/tr/haberler/hasat-mevsiminde-orman-yangini-alarmi"),
        ("NASA Earthdata FIRMS FAQ", "https://www.earthdata.nasa.gov/faq/firms-faq")]
ax.text(6.9, 5.55, "REFERENCES", family=MONO, size=12, color=ACCENT, va="top")
for i, (t, u) in enumerate(refs):
    y = 5.1 - i * 0.38
    ax.text(6.9, y, f"[{i + 1}]", family=MONO, size=12, color=MUTED, va="top")
    tt = ax.text(7.45, y, t, family=SANS, size=13.5, color=INK, va="top")
    tt.set_url(u)
link(ax, 0.6, 0.85, "Full method, code and data: " + REPO.replace("https://", ""), REPO, size=11.5)
pages.append(fig)

assert len(pages) == TOTAL
with PdfPages(OUT, metadata={"Title": "The Fire Almanac of Türkiye", "Author": "Team FireWatch TR"}) as pdf:
    for f in pages:
        pdf.savefig(f, facecolor=PAPER)
        plt.close(f)
print(OUT)
