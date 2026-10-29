"""Nyota SVG art: brand logo, shop monograms, product illustrations, hero scenes.

Pure standard library (no Django). Every function returns an inline SVG string, so a
product, shop or brand always has a good-looking image even when no photo exists.
All output is deterministic: the same inputs always give the same SVG, and every id
inside a document is derived from a hash so several SVGs can share one page.
"""
from __future__ import annotations

import colorsys
import hashlib
import math
import random
import re
from xml.sax.saxutils import escape

ART_CATEGORY_SLUGS = [
    'phones', 'computers', 'audio', 'mens-fashion', 'womens-fashion', 'footwear', 'bags',
    'home-decor', 'kitchen', 'beauty', 'groceries', 'sports', 'books', 'toys', 'jewelry',
]

_FONT = "Sora, 'Space Grotesk', system-ui, sans-serif"
_NS = 'xmlns="http://www.w3.org/2000/svg"'


# ------------------------------------------------------------------ helpers

def _hx(*parts) -> int:
    return int(hashlib.sha256('|'.join(str(p) for p in parts).encode('utf-8')).hexdigest(), 16)


def _uid(*parts) -> str:
    return 'n' + hashlib.sha1('|'.join(str(p) for p in parts).encode('utf-8')).hexdigest()[:8]


def _f(v: float) -> str:
    s = f'{v:.1f}'
    return s[:-2] if s.endswith('.0') else s


def _rgb(h: str):
    h = h.lstrip('#')
    if len(h) == 3:
        h = ''.join(ch * 2 for ch in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb) -> str:
    return '#%02x%02x%02x' % tuple(max(0, min(255, int(round(v)))) for v in rgb)


def _mix(a: str, b: str, t: float) -> str:
    ra, rb = _rgb(a), _rgb(b)
    return _hex([ra[i] + (rb[i] - ra[i]) * t for i in range(3)])


def _hsl(h: float, s: float, l: float) -> str:
    r, g, b = colorsys.hls_to_rgb(h % 1.0, l, s)
    return _hex((r * 255, g * 255, b * 255))


def _star4(cx: float, cy: float, r: float, k: float = 0.2) -> str:
    q = r * k
    return (f'M{_f(cx)} {_f(cy - r)}Q{_f(cx + q)} {_f(cy - q)} {_f(cx + r)} {_f(cy)}'
            f'Q{_f(cx + q)} {_f(cy + q)} {_f(cx)} {_f(cy + r)}'
            f'Q{_f(cx - q)} {_f(cy + q)} {_f(cx - r)} {_f(cy)}'
            f'Q{_f(cx - q)} {_f(cy - q)} {_f(cx)} {_f(cy - r)}Z')


def _label(name: str) -> str:
    return escape(str(name), {'"': '&quot;'})


# ------------------------------------------------------------------ brand logo

def _mark_parts(u: str):
    """Defs and shapes for the 64x64 brand mark. The N is cut out of the star (negative space)."""
    defs = (
        f'<linearGradient id="{u}a" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" style="stop-color:var(--accent,#8b5cf6)"/>'
        f'<stop offset="1" style="stop-color:var(--accent2,#22d3ee)"/></linearGradient>'
        f'<linearGradient id="{u}b" x1="0" y1="1" x2="1" y2="0">'
        f'<stop offset="0" style="stop-color:var(--accent2,#22d3ee)"/>'
        f'<stop offset="1" style="stop-color:var(--accent,#8b5cf6)"/></linearGradient>'
        f'<mask id="{u}m" maskUnits="userSpaceOnUse" x="0" y="0" width="64" height="64">'
        f'<rect width="64" height="64" fill="#fff"/>'
        f'<path d="M25 42V22L39 42V22" fill="none" stroke="#000" stroke-width="4.2" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="25" cy="42" r="3.6" fill="#000"/><circle cx="39" cy="22" r="3.6" fill="#000"/>'
        f'</mask>')
    star = 'M32 1Q40 24 63 32Q40 40 32 63Q24 40 1 32Q24 24 32 1Z'
    body = (
        f'<ellipse cx="32" cy="32" rx="30.5" ry="10.5" transform="rotate(-32 32 32)" fill="none" '
        f'stroke="url(#{u}b)" stroke-width="1.3" opacity=".55"/>'
        f'<path d="{star}" fill="url(#{u}a)" mask="url(#{u}m)"/>'
        f'<path d="M1.5 32A30.5 10.5 0 0 0 62.5 32" transform="rotate(-32 32 32)" fill="none" '
        f'stroke="url(#{u}b)" stroke-width="1.7" stroke-linecap="round" opacity=".95"/>'
        f'<path d="{_star4(52, 11, 6.5, 0.22)}" fill="url(#{u}b)"/>'
        f'<circle cx="8.5" cy="53" r="1.7" fill="url(#{u}b)" opacity=".8"/>'
        f'<circle cx="57" cy="52" r="1.1" fill="url(#{u}a)" opacity=".7"/>')
    return defs, body


def brand_logo_svg(mode: str = 'full', color: str = 'currentColor') -> str:
    u = _uid('brand', mode)
    defs, mark = _mark_parts(u)
    if mode == 'mark':
        return (f'<svg {_NS} viewBox="0 0 64 64" role="img" aria-label="Nyota">'
                f'<title>Nyota</title><defs>{defs}</defs>{mark}</svg>')
    stroke = escape(color, {'"': '&quot;'})
    word = (
        f'<g transform="translate(80 18)" fill="none" stroke="{stroke}" stroke-width="4.8" '
        f'stroke-linecap="round" stroke-linejoin="round">'
        f'<path d="M3 28V1M3 11C3 4 9 0 15 0C22 0 26 5 26 12V28"/>'          # n
        f'<path d="M37 0L51 28L46 40M65 0L51 28"/>'                           # y
        f'<circle cx="90" cy="14" r="13.2"/>'                                   # o
        f'<path d="M124 -8V21Q124 28 131 28H135M115 0H134"/>'                 # t
        f'<circle cx="159" cy="14" r="13.2"/><path d="M172.4 0V28"/>'          # a
        f'</g>'
        f'<circle cx="101" cy="22.2" r="3.3" fill="url(#{u}b)"/>')
    return (f'<svg {_NS} viewBox="0 0 258 64" role="img" aria-label="Nyota">'
            f'<title>Nyota</title><defs>{defs}</defs>{mark}{word}</svg>')


# ------------------------------------------------------------------ shop monogram

def shop_logo_svg(name: str, seed: str = '') -> str:
    h = _hx('shop', name, seed)
    rnd = random.Random(h)
    u = _uid('shop', name, seed)
    h1 = (h % 360) / 360.0
    h2 = (h1 + 0.07 + ((h >> 9) % 28) / 100.0) % 1.0
    c1, c2 = _hsl(h1, 0.78, 0.55), _hsl(h2, 0.80, 0.32)
    glow = _hsl(h1 + 0.02, 0.9, 0.78)
    circle = (h >> 20) % 2 == 0
    shape = ('<circle cx="128" cy="128" r="124"' if circle
             else '<rect x="4" y="4" width="248" height="248" rx="68"')
    letter = next((ch for ch in str(name) if ch.isalnum()), '*').upper()
    n = 5 + (h >> 4) % 3
    base = rnd.uniform(0, 6.283)
    pts = []
    for i in range(n):
        ang = base + i * 6.283 / n + rnd.uniform(-0.28, 0.28)
        rad = rnd.uniform(86, 108)
        pts.append((128 + rad * math.cos(ang), 128 + rad * math.sin(ang)))
    chain = ' '.join(f'{_f(x)} {_f(y)}' for x, y in pts[: n - 1])
    chords = ''
    if n >= 6:
        chords = f'<path d="M{_f(pts[0][0])} {_f(pts[0][1])}L{_f(pts[3][0])} {_f(pts[3][1])}" stroke-dasharray="2 5"/>'
    nodes = ''.join(
        f'<circle cx="{_f(x)}" cy="{_f(y)}" r="{_f(rnd.uniform(2.6, 4.6))}" fill="#fff"/>' for x, y in pts)
    bx, by = pts[rnd.randrange(n)]
    specks = ''.join(
        f'<circle cx="{_f(rnd.uniform(30, 226))}" cy="{_f(rnd.uniform(30, 226))}" r="{_f(rnd.uniform(.8, 1.6))}" '
        f'fill="#fff" opacity="{_f(rnd.uniform(.3, .7))}"/>' for _ in range(7))
    return (
        f'<svg {_NS} viewBox="0 0 256 256" role="img" aria-label="{_label(name)}">'
        f'<title>{escape(str(name))}</title><defs>'
        f'<linearGradient id="{u}a" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c1}"/>'
        f'<stop offset="1" stop-color="{c2}"/></linearGradient>'
        f'<radialGradient id="{u}r" cx=".3" cy=".25" r=".9"><stop offset="0" stop-color="{glow}" stop-opacity=".55"/>'
        f'<stop offset="1" stop-color="#000" stop-opacity=".25"/></radialGradient></defs>'
        f'{shape} fill="url(#{u}a)"/>{shape} fill="url(#{u}r)"/>'
        f'{specks}'
        f'<g fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" opacity=".6">'
        f'<path d="M{chain}"/>{chords}</g>{nodes}'
        f'<path d="{_star4(bx, by, 13, .2)}" fill="#fff"/>'
        f'<text x="128" y="128" dy=".35em" text-anchor="middle" font-family="{_FONT}" font-weight="800" '
        f'font-size="112" fill="#fff" fill-opacity=".96">{escape(letter)}</text></svg>')


# ------------------------------------------------------------------ category icons

_ICONS = {
    'phones': '<rect x="19" y="6" width="26" height="52" rx="6"/><path d="M28 12h8"/><circle cx="32" cy="51" r="1.6"/>',
    'computers': '<rect x="11" y="14" width="42" height="29" rx="3"/><path d="M4 50h56l-5-7H9z"/>',
    'audio': '<path d="M12 40V32a20 20 0 0 1 40 0v8"/><rect x="8" y="38" width="10" height="16" rx="4"/><rect x="46" y="38" width="10" height="16" rx="4"/>',
    'mens-fashion': '<path d="M22 8 8 18l6 10 6-4v32h24V24l6 4 6-10L42 8c-2 6-8 8-10 8s-8-2-10-8z"/>',
    'womens-fashion': '<path d="M25 6l-2 15L10 58h44L41 21 39 6"/><path d="M23 21h18"/>',
    'footwear': '<path d="M6 46V28c8 0 12-6 14-12 4 10 12 14 22 16 10 2 16 4 16 14z"/><path d="M6 52h52"/>',
    'bags': '<path d="M12 22h40l4 36H8z"/><path d="M22 22v-4a10 10 0 0 1 20 0v4"/>',
    'home-decor': '<path d="M20 8h24l8 22H12z"/><path d="M32 30v22M22 56h20"/>',
    'kitchen': '<path d="M10 24h44v22a8 8 0 0 1-8 8H18a8 8 0 0 1-8-8z"/><path d="M6 24h52M26 15h12M4 33h6M54 33h6"/>',
    'beauty': '<rect x="22" y="34" width="20" height="22" rx="2"/><rect x="24" y="24" width="16" height="10"/><path d="M26 24V12l6-6 6 6v12"/>',
    'groceries': '<path d="M8 28h48l-6 26H14z"/><path d="M20 28l8-14M44 28l-8-14M20 38v8M32 38v8M44 38v8"/>',
    'sports': '<circle cx="32" cy="32" r="24"/><path d="M32 18l10 7-4 12H26l-4-12z"/><path d="M32 8v10M42 25l12-3M38 37l8 10M26 37l-8 10M22 25L10 22"/>',
    'books': '<path d="M12 8h34a6 6 0 0 1 6 6v38H18a6 6 0 0 0-6 6z"/><path d="M12 8v50M24 20h20M24 28h14"/>',
    'toys': '<rect x="8" y="34" width="22" height="22" rx="3"/><rect x="34" y="34" width="22" height="22" rx="3"/><rect x="21" y="8" width="22" height="22" rx="3"/>',
    'jewelry': '<circle cx="32" cy="40" r="16"/><path d="M24 14l4-6h8l4 6-8 10zM24 14h16"/>',
}
_ICON_GIFT = ('<rect x="8" y="24" width="48" height="12"/><path d="M12 36v22h40V36M32 24v34'
              'M32 24c-8-14-20-8-14-2s14 2 14 2zM32 24c8-14 20-8 14-2s-14 2-14 2z"/>')


def category_icon_svg(slug: str, color: str = 'currentColor') -> str:
    inner = _ICONS.get(slug, _ICON_GIFT)
    return (f'<svg {_NS} viewBox="0 0 64 64" fill="none" stroke="{escape(color, {chr(34): "&quot;"})}" '
            f'stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{inner}</svg>')


# ------------------------------------------------------------------ product art

_BASES = ['#7c5cff', '#14b8a6', '#ff6b6b', '#f59e0b', '#38bdf8', '#f43f5e',
          '#10b981', '#6366f1', '#d946ef', '#fb923c', '#84cc16', '#0ea5e9']
_INK = '#171c33'
_INK2 = '#2a3152'


def _palette(name: str, seed: str) -> dict:
    h = _hx('pal', name, seed)
    i = h % len(_BASES)
    j = ((h >> 8) % (len(_BASES) - 1) + i + 1) % len(_BASES)
    a, k = _BASES[i], _BASES[j]
    return dict(a=a, d=_mix(a, '#0b1020', .38), l=_mix(a, '#ffffff', .42),
                t=_mix(a, '#ffffff', .90), t2=_mix(a, '#ffffff', .70),
                k=k, kd=_mix(k, '#0b1020', .3))


def _cols(c):
    return c['a'], c['d'], c['l'], c['k'], c['kd'], c['t2']


def _has(n: str, *words) -> bool:
    return re.search(r'\b(?:' + '|'.join(words) + r')', n) is not None


def _kind(name: str, slug: str) -> str:
    n = str(name).lower()
    if slug == 'phones':
        return 'tablet' if _has(n, 'tablet', 'ipad', 'tab\\b') else 'phone'
    if slug == 'computers':
        if _has(n, 'keyboard'):
            return 'keyboard'
        if _has(n, 'monitor', 'screen', 'display', 'tv\\b', 'desktop'):
            return 'monitor'
        return 'laptop'
    if slug == 'audio':
        if _has(n, 'speaker', 'soundbar', 'boombox'):
            return 'speaker'
        if _has(n, 'earbud', 'airpod', 'buds', 'earphone'):
            return 'earbuds'
        return 'headphones'
    if slug == 'mens-fashion':
        if _has(n, 'trouser', 'jean', 'pant', 'short', 'chino'):
            return 'trousers'
        if _has(n, 'jacket', 'hoodie', 'coat', 'sweater', 'blazer', 'jumper'):
            return 'jacket'
        return 'shirt'
    if slug == 'womens-fashion':
        if _has(n, 'bag', 'purse', 'clutch', 'tote'):
            return 'handbag'
        if _has(n, 'top', 'blouse', 'tee', 't-shirt', 'shirt'):
            return 'shirt'
        return 'dress'
    if slug == 'footwear':
        if _has(n, 'boot'):
            return 'boots'
        if _has(n, 'sandal', 'slipper', 'flip', 'slide'):
            return 'sandals'
        return 'sneakers'
    if slug == 'bags':
        if _has(n, 'suitcase', 'luggage', 'trolley'):
            return 'suitcase'
        if _has(n, 'hand', 'tote', 'purse', 'clutch', 'sling'):
            return 'handbag'
        return 'backpack'
    if slug == 'home-decor':
        if _has(n, 'lamp', 'light', 'lantern'):
            return 'lamp'
        if _has(n, 'vase', 'flower', 'plant'):
            return 'vase'
        return 'cushion'
    if slug == 'kitchen':
        if _has(n, 'kettle'):
            return 'kettle'
        if _has(n, 'blender', 'mixer', 'juicer'):
            return 'blender'
        if _has(n, 'mug', 'cup'):
            return 'mug'
        return 'pot'
    if slug == 'beauty':
        if _has(n, 'perfume', 'fragrance', 'cologne', 'spray', 'eau'):
            return 'perfume'
        if _has(n, 'lip', 'gloss'):
            return 'lipstick'
        return 'cream'
    if slug == 'groceries':
        if _has(n, 'coffee'):
            return 'coffee'
        if _has(n, 'tea\\b', 'chai'):
            return 'tea'
        if _has(n, 'flour', 'unga', 'rice', 'sugar', 'maize', 'beans', 'wheat', 'grain'):
            return 'sack'
        return 'basket'
    if slug == 'sports':
        if _has(n, 'dumbbell', 'weight', 'kettlebell', 'gym'):
            return 'dumbbell'
        if _has(n, 'yoga', 'mat\\b'):
            return 'yoga'
        if _has(n, 'basketball'):
            return 'basketball'
        return 'ball'
    if slug == 'books':
        return 'notebook' if _has(n, 'notebook', 'journal', 'diary', 'planner') else 'book'
    if slug == 'toys':
        return 'teddy' if _has(n, 'teddy', 'bear', 'plush', 'doll') else 'blocks'
    if slug == 'jewelry':
        if _has(n, 'watch'):
            return 'watch'
        if _has(n, 'necklace', 'chain', 'pendant'):
            return 'necklace'
        return 'ring'
    return 'gift'


def _g(u): return f'url(#{u}g)'
def _m(u): return f'url(#{u}m)'


def _phone(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    pal = [l, k, '#ffffff']
    apps = ''.join(f'<rect x="{238 + i % 3 * 44}" y="{176 + i // 3 * 50}" width="34" height="34" rx="10" '
                   f'fill="{pal[i % 3]}" opacity=".92"/>' for i in range(9))
    return (f'<rect x="206" y="104" width="188" height="372" rx="40" fill="{_INK}"/>'
            f'<rect x="212" y="110" width="176" height="360" rx="35" fill="{_INK2}"/>'
            f'<rect x="220" y="118" width="160" height="344" rx="29" fill="{_g(u)}"/>'
            f'<circle cx="300" cy="258" r="96" fill="{k}" opacity=".28"/>'
            f'<rect x="276" y="128" width="48" height="12" rx="6" fill="#0c1020"/>{apps}'
            f'<rect x="232" y="338" width="136" height="76" rx="18" fill="#fff" opacity=".24"/>'
            f'<rect x="242" y="352" width="64" height="8" rx="4" fill="#fff" opacity=".75"/>'
            f'<rect x="242" y="368" width="96" height="6" rx="3" fill="#fff" opacity=".45"/>'
            f'<rect x="236" y="426" width="128" height="26" rx="13" fill="#fff" opacity=".22"/>'
            f'<path d="M222 150 380 118V200L222 262Z" fill="#fff" opacity=".08"/>'
            f'<rect x="394" y="190" width="4" height="56" rx="2" fill="#0c1020"/>')


def _tablet(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    bars = ''.join(f'<rect x="{176 + i * 42}" y="{352 - h}" width="28" height="{h}" rx="8" fill="#fff" opacity=".82"/>'
                   for i, h in enumerate((50, 86, 64, 120, 98, 140)))
    return (f'<rect x="108" y="126" width="384" height="300" rx="34" fill="{_INK}"/>'
            f'<rect x="116" y="134" width="368" height="284" rx="28" fill="{_INK2}"/>'
            f'<rect x="126" y="144" width="348" height="264" rx="20" fill="{_g(u)}"/>'
            f'<circle cx="400" cy="200" r="70" fill="{k}" opacity=".3"/>'
            f'<rect x="152" y="166" width="110" height="10" rx="5" fill="#fff" opacity=".85"/>{bars}'
            f'<circle cx="300" cy="139" r="2.6" fill="#0c1020"/>'
            f'<path d="M126 220 330 144H474V176L126 330Z" fill="#fff" opacity=".07"/>')


def _laptop(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    return (f'<rect x="146" y="142" width="308" height="214" rx="16" fill="{_INK}"/>'
            f'<rect x="156" y="152" width="288" height="194" rx="8" fill="{_g(u)}"/>'
            f'<circle cx="372" cy="214" r="62" fill="{k}" opacity=".3"/>'
            f'<rect x="178" y="176" width="86" height="9" rx="4.5" fill="#fff" opacity=".85"/>'
            f'<rect x="178" y="196" width="132" height="7" rx="3.5" fill="#fff" opacity=".5"/>'
            f'<rect x="178" y="212" width="104" height="7" rx="3.5" fill="#fff" opacity=".4"/>'
            f'<path d="M180 318 222 280 252 304 304 250 338 290 420 238" fill="none" stroke="#fff" '
            f'stroke-width="5" stroke-linecap="round" stroke-linejoin="round" opacity=".8"/>'
            f'<path d="M100 356H500L526 404Q528 414 516 414H84Q72 414 74 404Z" fill="{_m(u)}"/>'
            f'<rect x="262" y="360" width="76" height="9" rx="4.5" fill="#94a3b8"/>')


def _monitor(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    bars = ''.join(f'<rect x="{150 + i * 46}" y="{330 - h}" width="30" height="{h}" rx="8" fill="#fff" opacity=".82"/>'
                   for i, h in enumerate((44, 80, 60, 116, 92, 140, 104)))
    return (f'<rect x="100" y="112" width="400" height="268" rx="20" fill="{_INK}"/>'
            f'<rect x="110" y="122" width="380" height="238" rx="10" fill="{_g(u)}"/>'
            f'<circle cx="420" cy="180" r="56" fill="{k}" opacity=".35"/>{bars}'
            f'<path d="M284 380H316L326 436H274Z" fill="#cbd5e1"/>'
            f'<rect x="208" y="432" width="184" height="18" rx="9" fill="{_m(u)}"/>'
            f'<path d="M110 122 340 122 110 280Z" fill="#fff" opacity=".07"/>')


def _keyboard(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    keys = []
    for r in range(3):
        for j in range(11):
            col = k if (r == 0 and j in (0, 10)) else '#ffffff'
            keys.append(f'<rect x="{96 + j * 37}" y="{262 + r * 38}" width="29" height="29" rx="7" fill="{col}"/>')
    keys.append(f'<rect x="96" y="376" width="62" height="29" rx="7" fill="#ffffff"/>')
    keys.append(f'<rect x="172" y="376" width="240" height="29" rx="9" fill="#ffffff"/>')
    keys.append(f'<rect x="426" y="376" width="78" height="29" rx="7" fill="#ffffff"/>')
    return (f'<rect x="70" y="236" width="460" height="196" rx="28" fill="{_m(u)}"/>'
            f'<rect x="80" y="246" width="440" height="176" rx="22" fill="{t2}" opacity=".55"/>'
            + ''.join(keys) +
            f'<path d="M96 291H504M96 329H504" stroke="#cbd5e1" stroke-width="2" opacity=".0"/>')


def _headphones(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    cup = lambda x, cx: (  # noqa: E731
        f'<rect x="{x}" y="292" width="86" height="158" rx="42" fill="{_g(u)}"/>'
        f'<circle cx="{cx}" cy="371" r="23" fill="{k}"/><circle cx="{cx}" cy="371" r="9" fill="#fff" opacity=".85"/>')
    return (f'<path d="M142 336C134 120 466 120 458 336" fill="none" stroke="{d}" stroke-width="34" stroke-linecap="round"/>'
            f'<path d="M142 336C134 120 466 120 458 336" fill="none" stroke="{a}" stroke-width="22" stroke-linecap="round"/>'
            f'<path d="M168 250C190 160 410 160 432 250" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" opacity=".35"/>'
            f'{cup(102, 145)}{cup(412, 455)}'
            f'<rect x="178" y="312" width="30" height="118" rx="15" fill="{_INK2}"/>'
            f'<rect x="392" y="312" width="30" height="118" rx="15" fill="{_INK2}"/>')


def _speaker(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    rings = ''.join(f'<circle cx="300" cy="336" r="{r}" fill="none" stroke="#fff" stroke-width="2" opacity=".25"/>'
                    for r in (50, 60, 70))
    return (f'<rect x="178" y="104" width="244" height="368" rx="44" fill="{_g(u)}"/>'
            f'<rect x="190" y="116" width="220" height="344" rx="34" fill="{_INK}" opacity=".18"/>'
            f'<circle cx="300" cy="336" r="84" fill="{_INK}"/><circle cx="300" cy="336" r="62" fill="{_INK2}"/>'
            f'<circle cx="300" cy="336" r="30" fill="{k}"/><circle cx="300" cy="336" r="10" fill="#fff" opacity=".85"/>'
            f'{rings}<circle cx="300" cy="200" r="42" fill="{_INK}"/><circle cx="300" cy="200" r="28" fill="{_INK2}"/>'
            f'<circle cx="300" cy="200" r="10" fill="{t2}"/>'
            f'<circle cx="300" cy="140" r="5" fill="#fff" opacity=".8"/>')


def _earbuds(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    bud = ('<ellipse cx="0" cy="0" rx="38" ry="42" fill="#f8fafc"/>'
           '<ellipse cx="-6" cy="-4" rx="20" ry="24" fill="#e2e8f0"/>'
           '<circle cx="-6" cy="-4" r="9" fill="#94a3b8"/>'
           '<rect x="8" y="22" width="22" height="86" rx="11" fill="#f8fafc"/>')
    return (f'<rect x="176" y="296" width="248" height="158" rx="70" fill="{_g(u)}"/>'
            f'<path d="M176 360H424" stroke="#fff" stroke-width="3" opacity=".35"/>'
            f'<circle cx="300" cy="392" r="7" fill="{k}"/><circle cx="300" cy="392" r="14" fill="{k}" opacity=".25"/>'
            f'<g transform="translate(232 196) rotate(-12)">{bud}</g>'
            f'<g transform="translate(368 196) scale(-1 1) rotate(-12)">{bud}</g>')


def _shirt(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    return (f'<path d="M206 126 116 184 158 252 204 226V446Q300 464 396 446V226L442 252 484 184 394 126Q300 190 206 126Z" fill="{_g(u)}"/>'
            f'<path d="M240 124Q300 206 360 124" fill="none" stroke="{d}" stroke-width="15" stroke-linecap="round"/>'
            f'<path d="M204 226 158 252M396 226 442 252" stroke="{d}" stroke-width="6" opacity=".4"/>'
            f'<path d="M204 226V446M396 226V446" stroke="#fff" stroke-width="3" opacity=".12"/>'
            f'<path d="{_star4(300, 316, 66, .22)}" fill="{k}"/>'
            f'<circle cx="300" cy="316" r="9" fill="#fff" opacity=".9"/>'
            f'<path d="M206 126 116 184" stroke="#fff" stroke-width="3" opacity=".25"/>')


def _trousers(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    return (f'<path d="M212 112H388L408 462H318L300 262 282 462H192Z" fill="{_g(u)}"/>'
            f'<rect x="212" y="112" width="176" height="34" rx="6" fill="{d}"/>'
            f'<path d="M300 146V262" stroke="{d}" stroke-width="4"/>'
            f'<path d="M238 112V146M362 112V146" stroke="#fff" stroke-width="7" opacity=".4"/>'
            f'<path d="M222 178Q256 196 270 166M378 178Q344 196 330 166" fill="none" stroke="{d}" stroke-width="4"/>'
            f'<path d="M198 420H292M308 420H402" stroke="#fff" stroke-width="3" opacity=".2"/>'
            f'<circle cx="300" cy="132" r="9" fill="{k}"/>')


def _jacket(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    return (f'<path d="M198 148 114 202 128 410H178L194 276V458H406V276L422 410H472L486 202 402 148Q300 208 198 148Z" fill="{_g(u)}"/>'
            f'<path d="M222 138Q300 54 378 138Q300 196 222 138Z" fill="{d}"/>'
            f'<path d="M300 176V458" stroke="#fff" stroke-width="5" stroke-dasharray="3 6" opacity=".7"/>'
            f'<path d="M262 160V232M338 160V232" stroke="{k}" stroke-width="6" stroke-linecap="round"/>'
            f'<path d="M226 360H272M328 360H374" stroke="{d}" stroke-width="7" stroke-linecap="round" opacity=".6"/>'
            f'<path d="M194 276H128M406 276H472" stroke="{d}" stroke-width="6" opacity=".35"/>')


def _dress(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    return (f'<path d="M252 96 246 214 168 462Q300 486 432 462L354 214 348 96 322 112Q300 142 278 112Z" fill="{_g(u)}"/>'
            f'<path d="M246 214H354L360 244H240Z" fill="{k}"/>'
            f'<path d="M278 112Q300 142 322 112" fill="none" stroke="{d}" stroke-width="8" stroke-linecap="round"/>'
            f'<path d="M270 262 226 450M300 262V470M330 262 374 450" stroke="#fff" stroke-width="4" opacity=".18"/>'
            f'<path d="{_star4(300, 354, 22, .2)}" fill="#fff" opacity=".9"/>')


def _handbag(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    return (f'<path d="M214 252C208 110 392 110 386 252" fill="none" stroke="{d}" stroke-width="18" stroke-linecap="round"/>'
            f'<path d="M142 244H458L486 454Q300 480 114 454Z" fill="{_g(u)}"/>'
            f'<path d="M142 244H458L448 316Q300 366 152 316Z" fill="{d}" opacity=".5"/>'
            f'<path d="M142 244H458L448 316Q300 366 152 316Z" fill="none" stroke="#fff" stroke-width="3" opacity=".25"/>'
            f'<circle cx="300" cy="330" r="22" fill="{k}"/><circle cx="300" cy="330" r="9" fill="#fff" opacity=".85"/>')


def _backpack(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    return (f'<path d="M248 150C248 92 352 92 352 150" fill="none" stroke="{d}" stroke-width="16" stroke-linecap="round"/>'
            f'<rect x="162" y="142" width="276" height="330" rx="92" fill="{_g(u)}"/>'
            f'<rect x="196" y="332" width="208" height="120" rx="34" fill="{d}" opacity=".55"/>'
            f'<path d="M206 372H394" stroke="{k}" stroke-width="7" stroke-linecap="round"/>'
            f'<rect x="284" y="360" width="32" height="26" rx="8" fill="{k}"/>'
            f'<path d="M206 232H394" stroke="#fff" stroke-width="4" opacity=".35"/>'
            f'<circle cx="300" cy="278" r="14" fill="{k}"/>'
            f'<path d="M164 300Q140 340 168 400M436 300Q460 340 432 400" fill="none" stroke="{d}" stroke-width="12" stroke-linecap="round"/>')


def _suitcase(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    ribs = ''.join(f'<rect x="{196 + i * 52}" y="156" width="10" height="278" rx="5" fill="#fff" opacity=".18"/>' for i in range(5))
    return (f'<rect x="252" y="96" width="96" height="62" rx="14" fill="none" stroke="{d}" stroke-width="14"/>'
            f'<rect x="136" y="148" width="328" height="300" rx="34" fill="{_g(u)}"/>{ribs}'
            f'<rect x="136" y="236" width="328" height="14" fill="{d}" opacity=".35"/>'
            f'<rect x="276" y="224" width="48" height="38" rx="10" fill="{k}"/>'
            f'<circle cx="188" cy="470" r="17" fill="{_INK}"/><circle cx="412" cy="470" r="17" fill="{_INK}"/>')


def _sneakers(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    laces = ''.join(f'<path d="M{216 + i * 24} {282 + i * 8}l16 -14" stroke="#fff" stroke-width="7" stroke-linecap="round"/>' for i in range(4))
    return (f'<path d="M96 420H512Q526 420 526 436V446Q526 464 504 464H112Q92 464 92 440Z" fill="#f8fafc"/>'
            f'<path d="M96 440H526" stroke="#cbd5e1" stroke-width="4"/>'
            f'<path d="M104 420V304Q104 272 136 272H182Q214 340 296 346L408 352Q500 362 514 420Z" fill="{_g(u)}"/>'
            f'<path d="M104 372H504" stroke="#fff" stroke-width="3" opacity="0"/>'
            f'<path d="M394 352Q472 356 514 420H430Q420 380 394 352Z" fill="{d}" opacity=".6"/>'
            f'<path d="M132 408Q300 372 470 400" fill="none" stroke="{k}" stroke-width="12" stroke-linecap="round"/>'
            f'<path d="M104 304Q120 292 150 300L182 272" fill="none" stroke="{d}" stroke-width="12" stroke-linecap="round"/>{laces}'
            f'<path d="M104 330H138" stroke="#fff" stroke-width="5" opacity=".5"/>')


def _boots(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    laces = ''.join(f'<path d="M{190 + (i % 2) * 6} {170 + i * 26}h66" stroke="{k}" stroke-width="7" stroke-linecap="round"/>' for i in range(6))
    return (f'<path d="M150 116H306L312 292Q334 346 432 354Q512 362 520 420V440H150Z" fill="{_g(u)}"/>'
            f'<rect x="146" y="104" width="164" height="30" rx="10" fill="{d}"/>{laces}'
            f'<path d="M142 424H530Q540 424 540 440V452Q540 468 518 468H150Q132 468 132 448V434Z" fill="{_INK}"/>'
            f'<path d="M142 424H532" stroke="{k}" stroke-width="6"/>'
            f'<path d="M196 394Q300 372 430 392" fill="none" stroke="{d}" stroke-width="10" stroke-linecap="round" opacity=".6"/>')


def _sandals(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    return (f'<path d="M214 466Q168 320 218 170Q296 80 388 164Q432 304 388 456Q304 500 214 466Z" fill="{_INK2}"/>'
            f'<path d="M222 452Q184 320 226 184Q296 106 378 176Q414 304 376 442Q300 478 222 452Z" fill="{t2}"/>'
            f'<path d="M206 262Q300 214 400 262V316Q300 270 206 316Z" fill="{_g(u)}"/>'
            f'<path d="M212 352Q300 306 392 352V402Q300 356 212 402Z" fill="{_g(u)}"/>'
            f'<circle cx="300" cy="288" r="11" fill="{k}"/><circle cx="300" cy="378" r="11" fill="{k}"/>'
            f'<path d="M250 150Q300 120 350 150" fill="none" stroke="#fff" stroke-width="5" opacity=".5" stroke-linecap="round"/>')


def _lamp(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    return (f'<circle cx="300" cy="260" r="200" fill="#fde68a" opacity=".28"/>'
            f'<circle cx="300" cy="280" r="130" fill="#fef3c7" opacity=".4"/>'
            f'<path d="M222 130H378L436 296H164Z" fill="{_g(u)}"/>'
            f'<path d="M164 296H436L426 312H174Z" fill="{d}"/>'
            f'<path d="M222 130 252 296M300 130V296M378 130 348 296" stroke="#fff" stroke-width="3" opacity=".2"/>'
            f'<rect x="292" y="312" width="16" height="130" rx="8" fill="{_m(u)}"/>'
            f'<ellipse cx="300" cy="452" rx="84" ry="16" fill="{d}"/><ellipse cx="300" cy="444" rx="84" ry="16" fill="{_m(u)}"/>'
            f'<circle cx="300" cy="306" r="9" fill="#fef9c3"/>')


def _vase(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    flowers = ''.join(
        f'<path d="M300 200Q{x1} 150 {x2} {y2}" fill="none" stroke="#16a34a" stroke-width="5" stroke-linecap="round"/>'
        f'<circle cx="{x2}" cy="{y2}" r="24" fill="{col}"/><circle cx="{x2}" cy="{y2}" r="9" fill="#fde68a"/>'
        for x1, x2, y2, col in ((260, 224, 98, k), (300, 300, 74, '#fb7185'), (340, 378, 106, l)))
    return (f'{flowers}'
            f'<path d="M264 190H336L330 232C424 290 442 410 336 462H264C158 410 176 290 270 232Z" fill="{_g(u)}"/>'
            f'<ellipse cx="300" cy="190" rx="38" ry="9" fill="{d}"/>'
            f'<path d="M206 338Q300 372 394 338" fill="none" stroke="#fff" stroke-width="4" opacity=".35"/>'
            f'<path d="{_star4(300, 396, 26, .22)}" fill="{k}"/>')


def _cushion(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    return (f'<path d="M146 150Q300 112 454 150Q480 300 454 450Q300 488 146 450Q120 300 146 150Z" fill="{_g(u)}"/>'
            f'<path d="M168 174Q300 144 432 174M168 426Q300 456 432 426" fill="none" stroke="#fff" stroke-width="3" stroke-dasharray="6 7" opacity=".4"/>'
            f'<path d="M146 150 300 300 454 150M146 450 300 300 454 450" fill="none" stroke="{d}" stroke-width="3" opacity=".25"/>'
            f'<circle cx="300" cy="300" r="14" fill="{d}"/>'
            f'<path d="{_star4(300, 214, 30, .22)}" fill="{k}"/><path d="{_star4(300, 386, 30, .22)}" fill="{k}"/>')


def _pot(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    return (f'<path d="M232 140Q216 96 252 86M300 130Q286 80 322 66M368 140Q354 98 388 90" fill="none" stroke="#fff" stroke-width="8" stroke-linecap="round" opacity=".6"/>'
            f'<rect x="108" y="288" width="46" height="26" rx="13" fill="{_INK2}"/><rect x="446" y="288" width="46" height="26" rx="13" fill="{_INK2}"/>'
            f'<path d="M144 270H456V412Q456 464 404 464H196Q144 464 144 412Z" fill="{_g(u)}"/>'
            f'<path d="M132 270Q300 200 468 270Z" fill="{_m(u)}"/>'
            f'<rect x="276" y="188" width="48" height="22" rx="11" fill="{k}"/>'
            f'<path d="M164 342H436" stroke="#fff" stroke-width="4" opacity=".3"/>'
            f'<path d="M164 390H436" stroke="{k}" stroke-width="10" opacity=".7"/>')


def _kettle(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    return (f'<path d="M206 316C98 306 100 440 196 430" fill="none" stroke="{_INK2}" stroke-width="20" stroke-linecap="round"/>'
            f'<path d="M388 330 486 236 508 258 424 372Z" fill="{_m(u)}"/>'
            f'<path d="M206 468H394C440 380 424 290 380 258H220C176 290 160 380 206 468Z" fill="{_g(u)}"/>'
            f'<rect x="216" y="236" width="168" height="28" rx="14" fill="{_m(u)}"/>'
            f'<rect x="276" y="198" width="48" height="40" rx="20" fill="{_INK2}"/>'
            f'<path d="M214 392Q300 420 386 392" fill="none" stroke="#fff" stroke-width="4" opacity=".35"/>'
            f'<circle cx="300" cy="340" r="16" fill="{k}"/>')


def _blender(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    return (f'<rect x="196" y="332" width="208" height="140" rx="26" fill="{_g(u)}"/>'
            f'<circle cx="300" cy="402" r="26" fill="{_INK}"/><circle cx="300" cy="402" r="12" fill="{k}"/>'
            f'<rect x="216" y="352" width="168" height="8" rx="4" fill="#fff" opacity=".35"/>'
            f'<path d="M214 100H386L364 336H236Z" fill="#e0f2fe" opacity=".55"/>'
            f'<path d="M232 220H368L364 336H236Z" fill="{k}" opacity=".85"/>'
            f'<path d="M232 220Q266 206 300 220T368 220" fill="none" stroke="#fff" stroke-width="4" opacity=".6"/>'
            f'<path d="M214 100H386L364 336H236Z" fill="none" stroke="#fff" stroke-width="5" opacity=".7"/>'
            f'<rect x="206" y="84" width="188" height="26" rx="13" fill="{_INK2}"/>'
            f'<rect x="286" y="56" width="28" height="32" rx="10" fill="{_INK2}"/>'
            f'<path d="M252 292 348 310M252 310 348 292" stroke="#cbd5e1" stroke-width="7" stroke-linecap="round"/>')


def _mug(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    return (f'<path d="M262 148Q240 110 272 90M312 156Q292 112 322 86M360 148Q342 112 368 98" fill="none" stroke="#fff" stroke-width="8" stroke-linecap="round" opacity=".65"/>'
            f'<path d="M386 250C490 238 492 380 380 376" fill="none" stroke="{d}" stroke-width="30" stroke-linecap="round"/>'
            f'<path d="M386 250C490 238 492 380 380 376" fill="none" stroke="{a}" stroke-width="16" stroke-linecap="round"/>'
            f'<path d="M180 190H398V400Q398 460 338 460H240Q180 460 180 400Z" fill="{_g(u)}"/>'
            f'<ellipse cx="289" cy="190" rx="109" ry="22" fill="{d}"/><ellipse cx="289" cy="192" rx="98" ry="16" fill="#4a2c1d"/>'
            f'<path d="{_star4(289, 322, 44, .22)}" fill="#fff" opacity=".92"/>')


def _perfume(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    return (f'<path d="M92 110l10 18 18 10-18 10-10 18-10-18-18-10 18-10z" fill="{k}" opacity=".0"/>'
            f'<rect x="196" y="236" width="208" height="224" rx="34" fill="{_g(u)}" opacity=".95"/>'
            f'<rect x="212" y="252" width="176" height="192" rx="24" fill="#fff" opacity=".16"/>'
            f'<rect x="236" y="300" width="128" height="96" rx="12" fill="#fff" opacity=".92"/>'
            f'<path d="{_star4(300, 348, 28, .22)}" fill="{k}"/>'
            f'<rect x="270" y="194" width="60" height="50" rx="8" fill="{_m(u)}"/>'
            f'<rect x="250" y="120" width="100" height="84" rx="16" fill="{_INK2}"/>'
            f'<rect x="250" y="120" width="100" height="22" rx="11" fill="{k}"/>'
            f'<path d="M214 262Q214 252 224 252" stroke="#fff" stroke-width="5" opacity=".6" stroke-linecap="round" fill="none"/>')


def _cream(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    return (f'<rect x="148" y="290" width="304" height="162" rx="26" fill="{_g(u)}"/>'
            f'<rect x="136" y="228" width="328" height="72" rx="20" fill="{_m(u)}"/>'
            f'<path d="M136 262H464" stroke="#94a3b8" stroke-width="3" opacity=".6"/>'
            f'<rect x="190" y="326" width="220" height="90" rx="14" fill="#fff" opacity=".92"/>'
            f'<path d="{_star4(240, 371, 24, .22)}" fill="{k}"/>'
            f'<rect x="276" y="352" width="104" height="9" rx="4.5" fill="{a}"/><rect x="276" y="372" width="72" height="7" rx="3.5" fill="{a}" opacity=".5"/>'
            f'<path d="M430 160c26-26 62-14 54 18-30 10-52 2-54-18z" fill="#22c55e"/><path d="M430 160 480 176" stroke="#15803d" stroke-width="3"/>')


def _lipstick(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    return (f'<rect x="234" y="330" width="132" height="132" rx="14" fill="{_INK}"/>'
            f'<rect x="234" y="330" width="132" height="22" fill="#fbbf24"/>'
            f'<rect x="246" y="264" width="108" height="74" rx="8" fill="{_m(u)}"/>'
            f'<path d="M262 266V150L300 106 338 150V266Z" fill="{_g(u)}"/>'
            f'<path d="M262 150 300 106 338 150 300 138Z" fill="#fff" opacity=".28"/>'
            f'<path d="M222 400V430" stroke="#fff" stroke-width="5" opacity="0"/>'
            f'<path d="M256 380H344" stroke="#fbbf24" stroke-width="4" opacity=".6"/>')


def _coffee(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    beans = ''.join(f'<ellipse cx="{x}" cy="{y}" rx="22" ry="14" transform="rotate({r} {x} {y})" fill="#5b3a29"/>'
                    f'<path d="M{x - 17} {y}Q{x} {y - 8} {x + 17} {y}" transform="rotate({r} {x} {y})" fill="none" stroke="#2b1d16" stroke-width="2.4"/>'
                    for x, y, r in ((142, 470, -20), (456, 474, 24), (400, 488, -8)))
    return (f'<path d="M190 138H410L430 462Q300 486 170 462Z" fill="#3b2a20"/>'
            f'<path d="M190 138H410L416 200Q300 222 184 200Z" fill="#2b1d16"/>'
            f'<rect x="182" y="118" width="236" height="32" rx="6" fill="#2b1d16"/>'
            f'<path d="M190 138H410" stroke="#fff" stroke-width="3" opacity=".25"/>'
            f'<rect x="224" y="238" width="152" height="178" rx="16" fill="{a}"/>'
            f'<rect x="236" y="250" width="128" height="154" rx="10" fill="#fff" opacity=".94"/>'
            f'<ellipse cx="300" cy="320" rx="30" ry="20" transform="rotate(-30 300 320)" fill="#5b3a29"/>'
            f'<path d="M274 336Q300 312 326 304" fill="none" stroke="#fff" stroke-width="4"/>'
            f'<rect x="258" y="364" width="84" height="8" rx="4" fill="{a}"/><rect x="272" y="380" width="56" height="6" rx="3" fill="{a}" opacity=".5"/>'
            f'{beans}')


def _tea(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    return (f'<rect x="190" y="178" width="220" height="282" rx="30" fill="{_g(u)}"/>'
            f'<rect x="182" y="146" width="236" height="46" rx="16" fill="{d}"/>'
            f'<rect x="182" y="146" width="236" height="14" rx="7" fill="#fff" opacity=".22"/>'
            f'<rect x="190" y="262" width="220" height="130" fill="#fff" opacity=".92"/>'
            f'<path d="M300 372C250 340 252 290 300 276C348 290 350 340 300 372Z" fill="#22c55e"/>'
            f'<path d="M300 372V290M300 330 276 312M300 338 326 320" stroke="#15803d" stroke-width="4" stroke-linecap="round"/>'
            f'<path d="M262 120Q250 90 274 70M326 124Q312 94 336 78" fill="none" stroke="#fff" stroke-width="7" stroke-linecap="round" opacity=".6"/>'
            f'<rect x="212" y="410" width="176" height="8" rx="4" fill="#fff" opacity=".3"/>')


def _sack(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    return (f'<path d="M194 172Q168 300 156 448Q300 484 444 448Q432 300 406 172Q300 204 194 172Z" fill="#e2c28a"/>'
            f'<path d="M194 172Q168 300 156 448Q232 468 300 470Q232 330 214 178Z" fill="#c89f5e" opacity=".5"/>'
            f'<path d="M190 172Q300 90 410 172Q300 214 190 172Z" fill="#d6b074"/>'
            f'<rect x="194" y="170" width="212" height="14" rx="7" fill="{k}"/>'
            f'<rect x="232" y="250" width="136" height="154" rx="20" fill="#fff" opacity=".92"/>'
            f'<path d="M300 388V290" stroke="{a}" stroke-width="5" stroke-linecap="round"/>'
            f'<path d="M300 300q-22-8-24-30 22 6 24 30zM300 300q22-8 24-30-22 6-24 30zM300 330q-22-8-24-30 22 6 24 30zM300 330q22-8 24-30-22 6-24 30zM300 360q-22-8-24-30 22 6 24 30zM300 360q22-8 24-30-22 6-24 30z" fill="{a}"/>'
            f'<path d="M214 176Q300 150 386 176" fill="none" stroke="#fff" stroke-width="3" opacity=".4"/>')


def _basket(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    weave = ''.join(f'<path d="M{150 + i * 8} {350 + i * 22}H{450 - i * 8}" stroke="#9a6128" stroke-width="5" opacity=".7"/>' for i in range(5))
    vert = ''.join(f'<path d="M{190 + j * 44} 342V462" stroke="#9a6128" stroke-width="3" opacity=".4"/>' for j in range(6))
    grapes = ''.join(f'<circle cx="{x}" cy="{y}" r="15" fill="#7c3aed"/>' for x, y in
                     ((404, 270), (432, 270), (390, 296), (418, 296), (446, 296), (404, 322), (432, 322), (418, 346)))
    return (f'<path d="M378 232Q474 252 448 336Q448 290 380 290Z" fill="#facc15"/>'
            f'<circle cx="236" cy="282" r="56" fill="#ef4444"/><path d="M236 226Q248 206 268 204" fill="none" stroke="#7c4a24" stroke-width="6" stroke-linecap="round"/>'
            f'<path d="M244 226q12-24 34-14-6 22-34 14z" fill="#22c55e"/>'
            f'<circle cx="326" cy="262" r="52" fill="#fb923c"/><circle cx="312" cy="248" r="10" fill="#fff" opacity=".25"/>'
            f'{grapes}'
            f'<path d="M142 328H458L428 462Q300 482 172 462Z" fill="#c98a4b"/>{weave}{vert}'
            f'<rect x="130" y="314" width="340" height="28" rx="14" fill="#b2763a"/>'
            f'<path d="M222 150Q300 70 378 150" fill="none" stroke="#9a6128" stroke-width="10" stroke-linecap="round" opacity="0"/>')


def _ball(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    return (f'<defs><clipPath id="{u}c"><circle cx="300" cy="290" r="170"/></clipPath>'
            f'<radialGradient id="{u}o" cx=".35" cy=".3" r=".8"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#cbd5e1"/></radialGradient></defs>'
            f'<circle cx="300" cy="290" r="170" fill="url(#{u}o)"/>'
            f'<g clip-path="url(#{u}c)" fill="{_INK}">'
            f'<path d="M300 222 365 270 340 346H260L235 270Z"/>'
            f'<path d="M300 100 340 130 330 160 300 150 270 160 260 130Z"/>'
            f'<path d="M430 210 466 258 452 296 420 288 410 250Z"/><path d="M170 210 134 258 148 296 180 288 190 250Z"/>'
            f'<path d="M380 400 430 380 452 420 420 458 380 446Z"/><path d="M220 400 170 380 148 420 180 458 220 446Z"/>'
            f'<path d="M300 470 340 450 360 480 300 500 240 480 260 450Z"/></g>'
            f'<g clip-path="url(#{u}c)" fill="none" stroke="{_INK}" stroke-width="5" stroke-linecap="round">'
            f'<path d="M300 222V160M365 270 410 250M340 346 380 400M260 346 220 400M235 270 190 250"/></g>'
            f'<circle cx="300" cy="290" r="170" fill="none" stroke="{k}" stroke-width="6" opacity=".55"/>'
            f'<ellipse cx="248" cy="196" rx="52" ry="30" transform="rotate(-30 248 196)" fill="#fff" opacity=".5"/>')


def _basketball(c, u):
    return (f'<defs><radialGradient id="{u}o" cx=".35" cy=".3" r=".85"><stop offset="0" stop-color="#fdba74"/>'
            f'<stop offset="1" stop-color="#c2410c"/></radialGradient></defs>'
            f'<circle cx="300" cy="290" r="170" fill="url(#{u}o)"/>'
            f'<g fill="none" stroke="{_INK}" stroke-width="7" stroke-linecap="round">'
            f'<path d="M130 290H470M300 120V460"/><path d="M178 172C250 236 250 344 178 408"/>'
            f'<path d="M422 172C350 236 350 344 422 408"/></g>'
            f'<ellipse cx="248" cy="196" rx="48" ry="26" transform="rotate(-30 248 196)" fill="#fff" opacity=".28"/>')


def _dumbbell(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    return (f'<g transform="rotate(-24 300 300)">'
            f'<rect x="150" y="288" width="300" height="26" rx="13" fill="{_m(u)}"/>'
            f'<path d="M196 288V314M404 288V314" stroke="#64748b" stroke-width="3"/>'
            f'<rect x="132" y="200" width="46" height="202" rx="14" fill="{_g(u)}"/><rect x="92" y="226" width="36" height="150" rx="12" fill="{d}"/>'
            f'<rect x="422" y="200" width="46" height="202" rx="14" fill="{_g(u)}"/><rect x="472" y="226" width="36" height="150" rx="12" fill="{d}"/>'
            f'<rect x="142" y="226" width="26" height="8" rx="4" fill="#fff" opacity=".45"/><rect x="432" y="226" width="26" height="8" rx="4" fill="#fff" opacity=".45"/>'
            f'<circle cx="155" cy="301" r="9" fill="{k}"/><circle cx="445" cy="301" r="9" fill="{k}"/></g>')


def _yoga(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    spiral = ''.join(f'<ellipse cx="196" cy="320" rx="{rx}" ry="{ry}" fill="none" stroke="{col}" stroke-width="5"/>'
                     for rx, ry, col in ((50, 102, d), (38, 80, a), (26, 58, d), (14, 34, a)))
    return (f'<path d="M196 218H420Q470 218 470 320Q470 422 420 422H196Z" fill="{_g(u)}"/>'
            f'<ellipse cx="420" cy="320" rx="50" ry="102" fill="{d}"/>'
            f'<ellipse cx="420" cy="320" rx="50" ry="102" fill="none" stroke="#fff" stroke-width="3" opacity=".25"/>'
            f'<ellipse cx="196" cy="320" rx="50" ry="102" fill="{a}"/>{spiral}'
            f'<rect x="288" y="214" width="34" height="212" rx="10" fill="{k}"/>'
            f'<path d="M228 250H410M228 390H410" stroke="#fff" stroke-width="4" opacity=".25"/>')


def _book(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    pages = ''.join(f'<path d="M430 {120 + i * 22}H446" stroke="#cbd5e1" stroke-width="3"/>' for i in range(15))
    return (f'<rect x="446" y="116" width="2" height="2" fill="none"/>'
            f'<path d="M432 112H452V452H432Z" fill="#f8fafc"/>{pages}'
            f'<rect x="170" y="104" width="266" height="356" rx="12" fill="{_g(u)}"/>'
            f'<rect x="170" y="104" width="34" height="356" rx="12" fill="{d}"/>'
            f'<path d="M204 104V460" stroke="#fff" stroke-width="3" opacity=".25"/>'
            f'<path d="{_star4(320, 218, 52, .22)}" fill="{k}"/><circle cx="320" cy="218" r="9" fill="#fff"/>'
            f'<rect x="236" y="320" width="164" height="14" rx="7" fill="#fff" opacity=".92"/>'
            f'<rect x="262" y="348" width="112" height="9" rx="4.5" fill="#fff" opacity=".6"/>'
            f'<rect x="170" y="420" width="266" height="8" fill="{k}" opacity=".9"/>')


def _notebook(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    rings = ''.join(f'<rect x="164" y="{138 + i * 36}" width="40" height="12" rx="6" fill="{_m(u)}"/>' for i in range(9))
    lines = ''.join(f'<path d="M244 {214 + i * 30}H410" stroke="#fff" stroke-width="3" opacity=".25"/>' for i in range(6))
    return (f'<rect x="180" y="110" width="272" height="352" rx="20" fill="{_g(u)}"/>'
            f'<rect x="248" y="150" width="150" height="34" rx="10" fill="#fff" opacity=".9"/>'
            f'<path d="{_star4(330, 164, 12, .22)}" fill="{k}"/>{lines}{rings}'
            f'<rect x="402" y="110" width="22" height="352" fill="{k}" opacity=".9"/>'
            f'<path d="M372 462V500L384 490 396 500V462Z" fill="{k}"/>')


def _teddy(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    br, brd, brl = '#b9793f', '#8a5a2b', '#e8c9a0'
    return (f'<circle cx="228" cy="150" r="36" fill="{br}"/><circle cx="228" cy="150" r="20" fill="{brl}"/>'
            f'<circle cx="372" cy="150" r="36" fill="{br}"/><circle cx="372" cy="150" r="20" fill="{brl}"/>'
            f'<ellipse cx="204" cy="352" rx="40" ry="70" transform="rotate(30 204 352)" fill="{br}"/>'
            f'<ellipse cx="396" cy="352" rx="40" ry="70" transform="rotate(-30 396 352)" fill="{br}"/>'
            f'<ellipse cx="238" cy="452" rx="52" ry="40" fill="{br}"/><ellipse cx="362" cy="452" rx="52" ry="40" fill="{br}"/>'
            f'<ellipse cx="238" cy="456" rx="30" ry="22" fill="{brl}"/><ellipse cx="362" cy="456" rx="30" ry="22" fill="{brl}"/>'
            f'<ellipse cx="300" cy="364" rx="106" ry="112" fill="{br}"/><ellipse cx="300" cy="380" rx="66" ry="76" fill="{brl}"/>'
            f'<circle cx="300" cy="212" r="84" fill="{br}"/><ellipse cx="300" cy="238" rx="38" ry="30" fill="{brl}"/>'
            f'<ellipse cx="300" cy="224" rx="14" ry="10" fill="{_INK}"/><path d="M300 234V248M284 252Q300 264 316 252" fill="none" stroke="{_INK}" stroke-width="4" stroke-linecap="round"/>'
            f'<circle cx="268" cy="196" r="9" fill="{_INK}"/><circle cx="332" cy="196" r="9" fill="{_INK}"/>'
            f'<circle cx="265" cy="193" r="3" fill="#fff"/><circle cx="329" cy="193" r="3" fill="#fff"/>'
            f'<path d="M300 290 252 272V316Z M300 290 348 272V316Z" fill="{k}"/><circle cx="300" cy="292" r="12" fill="{kd}"/>')


def _cube(cx, cy, s, top, left, right):
    w, h = s * .866, s * .5
    return (f'<path d="M{_f(cx)} {_f(cy - s)}L{_f(cx + w)} {_f(cy - s + h)}L{_f(cx)} {_f(cy - s + 2 * h)}L{_f(cx - w)} {_f(cy - s + h)}Z" fill="{top}"/>'
            f'<path d="M{_f(cx - w)} {_f(cy - s + h)}L{_f(cx)} {_f(cy - s + 2 * h)}V{_f(cy + s * .5 + h)}L{_f(cx - w)} {_f(cy + h * 0 + s * .5)}Z" fill="{left}"/>'
            f'<path d="M{_f(cx + w)} {_f(cy - s + h)}L{_f(cx)} {_f(cy - s + 2 * h)}V{_f(cy + s * .5 + h)}L{_f(cx + w)} {_f(cy + s * .5)}Z" fill="{right}"/>')


def _blocks(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    out = (_cube(210, 430, 90, l, a, d) + _cube(390, 430, 90, '#fde68a', '#f59e0b', '#b45309')
           + _cube(300, 330, 90, _mix(k, '#fff', .35), k, kd))
    return out + f'<path d="{_star4(300, 216, 20, .22)}" fill="#fff" opacity=".0"/>'


def _ring(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    return (f'<defs><linearGradient id="{u}y" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fde68a"/>'
            f'<stop offset=".5" stop-color="#f59e0b"/><stop offset="1" stop-color="#b45309"/></linearGradient></defs>'
            f'<circle cx="300" cy="352" r="104" fill="none" stroke="url(#{u}y)" stroke-width="30"/>'
            f'<circle cx="300" cy="352" r="104" fill="none" stroke="#fff" stroke-width="3" opacity=".35" stroke-dasharray="40 600" transform="rotate(-120 300 352)"/>'
            f'<path d="M262 216L282 180H318L338 216 300 262Z" fill="{k}"/>'
            f'<path d="M262 216H338M282 180 300 216 318 180" fill="none" stroke="#fff" stroke-width="3" opacity=".65"/>'
            f'<path d="M262 216 300 262 338 216" fill="{kd}" opacity=".6"/>'
            f'<path d="M244 232L262 216M356 232L338 216" stroke="url(#{u}y)" stroke-width="10" stroke-linecap="round"/>'
            f'<path d="{_star4(386, 150, 16, .22)}" fill="#fff"/><path d="{_star4(220, 170, 10, .22)}" fill="#fff" opacity=".8"/>')


def _watch(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    ticks = ''.join(
        f'<path d="M300 {204 + (0 if i % 3 == 0 else 6)}V{216 + (0 if i % 3 == 0 else 4)}" transform="rotate({i * 30} 300 300)" stroke="#fff" stroke-width="{4 if i % 3 == 0 else 2.4}" stroke-linecap="round"/>'
        for i in range(12))
    return (f'<rect x="240" y="70" width="120" height="150" rx="26" fill="{_g(u)}"/><rect x="240" y="380" width="120" height="150" rx="26" fill="{_g(u)}"/>'
            f'<g fill="{_INK}" opacity=".35"><circle cx="300" cy="104" r="4"/><circle cx="300" cy="130" r="4"/><circle cx="300" cy="156" r="4"/>'
            f'<circle cx="300" cy="450" r="4"/><circle cx="300" cy="476" r="4"/><circle cx="300" cy="502" r="4"/></g>'
            f'<rect x="404" y="278" width="20" height="44" rx="8" fill="{_m(u)}"/>'
            f'<circle cx="300" cy="300" r="114" fill="{_m(u)}"/><circle cx="300" cy="300" r="100" fill="{_INK}"/>'
            f'<circle cx="300" cy="300" r="94" fill="{_INK2}"/>{ticks}'
            f'<path d="M300 300V238M300 300L344 322" stroke="#fff" stroke-width="7" stroke-linecap="round"/>'
            f'<path d="M300 300L262 352" stroke="{k}" stroke-width="3.5" stroke-linecap="round"/><circle cx="300" cy="300" r="8" fill="{k}"/>')


def _necklace(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    beads = ''
    for i in range(1, 22):
        t = i / 22.0
        x = (1 - t) ** 2 * 120 + 2 * t * (1 - t) * 300 + t ** 2 * 480
        y = (1 - t) ** 2 * 130 + 2 * t * (1 - t) * 520 + t ** 2 * 130
        beads += f'<circle cx="{_f(x)}" cy="{_f(y)}" r="{4 if i % 3 else 6.5}" fill="{"#fbbf24" if i % 3 else k}"/>'
    return (f'<path d="M120 130Q300 520 480 130" fill="none" stroke="#fbbf24" stroke-width="3" opacity=".55"/>{beads}'
            f'<path d="M300 322C262 372 268 430 300 462C332 430 338 372 300 322Z" fill="{_g(u)}"/>'
            f'<path d="M300 322C262 372 268 430 300 462C332 430 338 372 300 322Z" fill="none" stroke="#fbbf24" stroke-width="7"/>'
            f'<path d="M286 392Q292 364 306 354" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" opacity=".6"/>'
            f'<path d="{_star4(420, 380, 18, .22)}" fill="#fff"/><path d="{_star4(190, 320, 11, .22)}" fill="#fff" opacity=".8"/>')


def _gift(c, u):
    a, d, l, k, kd, t2 = _cols(c)
    return (f'<rect x="164" y="270" width="272" height="190" rx="14" fill="{_g(u)}"/>'
            f'<rect x="148" y="214" width="304" height="66" rx="14" fill="{d}"/>'
            f'<rect x="272" y="214" width="56" height="246" fill="{k}"/>'
            f'<path d="M300 214C232 110 148 150 206 204C240 222 280 218 300 214ZM300 214C368 110 452 150 394 204C360 222 320 218 300 214Z" fill="{k}"/>'
            f'<path d="M300 214C250 150 214 168 232 194" fill="none" stroke="#fff" stroke-width="3" opacity=".4"/>'
            f'<circle cx="300" cy="214" r="18" fill="{kd}"/>'
            f'<path d="{_star4(222, 380, 16, .22)}" fill="#fff" opacity=".8"/>')


_DRAW = {
    'phone': _phone, 'tablet': _tablet, 'laptop': _laptop, 'monitor': _monitor, 'keyboard': _keyboard,
    'headphones': _headphones, 'speaker': _speaker, 'earbuds': _earbuds,
    'shirt': _shirt, 'trousers': _trousers, 'jacket': _jacket, 'dress': _dress, 'handbag': _handbag,
    'sneakers': _sneakers, 'boots': _boots, 'sandals': _sandals,
    'backpack': _backpack, 'suitcase': _suitcase,
    'lamp': _lamp, 'vase': _vase, 'cushion': _cushion,
    'pot': _pot, 'kettle': _kettle, 'blender': _blender, 'mug': _mug,
    'perfume': _perfume, 'cream': _cream, 'lipstick': _lipstick,
    'coffee': _coffee, 'tea': _tea, 'sack': _sack, 'basket': _basket,
    'ball': _ball, 'basketball': _basketball, 'dumbbell': _dumbbell, 'yoga': _yoga,
    'book': _book, 'notebook': _notebook, 'teddy': _teddy, 'blocks': _blocks,
    'ring': _ring, 'watch': _watch, 'necklace': _necklace, 'gift': _gift,
}
_NO_SHADOW = {'necklace', 'watch'}
_SPOTS = [(86, 104), (512, 92), (524, 424), (78, 452), (462, 528), (104, 292), (528, 262), (140, 540), (300, 52)]


def product_svg(name: str, category_slug: str, seed: str = '') -> str:
    c = _palette(name, seed)
    u = _uid('prod', name, category_slug, seed)
    kind = _kind(name, category_slug)
    rnd = random.Random(_hx('spark', name, seed))
    sparks = ''.join(
        f'<path d="{_star4(x, y, rnd.uniform(9, 19), .2)}" fill="{c["k"]}" opacity="{_f(rnd.uniform(.55, .9))}"/>'
        for x, y in rnd.sample(_SPOTS, 4))
    dots = ''.join(
        f'<circle cx="{_f(rnd.uniform(40, 560))}" cy="{_f(rnd.uniform(40, 560))}" r="{_f(rnd.uniform(1.6, 3.2))}" fill="#fff" opacity=".8"/>'
        for _ in range(5))
    shadow = '' if kind in _NO_SHADOW else f'<ellipse cx="300" cy="476" rx="176" ry="17" fill="url(#{u}s)"/>'
    defs = (
        f'<linearGradient id="{u}bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c["t"]}"/>'
        f'<stop offset="1" stop-color="{c["t2"]}"/></linearGradient>'
        f'<linearGradient id="{u}g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c["l"]}"/>'
        f'<stop offset=".5" stop-color="{c["a"]}"/><stop offset="1" stop-color="{c["d"]}"/></linearGradient>'
        f'<linearGradient id="{u}m" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f1f5f9"/>'
        f'<stop offset="1" stop-color="#94a3b8"/></linearGradient>'
        f'<radialGradient id="{u}s"><stop offset="0" stop-color="#0b1020" stop-opacity=".3"/>'
        f'<stop offset="1" stop-color="#0b1020" stop-opacity="0"/></radialGradient>')
    return (f'<svg {_NS} viewBox="0 0 600 600" role="img" aria-label="{_label(name)}">'
            f'<title>{escape(str(name))}</title><defs>{defs}</defs>'
            f'<rect width="600" height="600" fill="url(#{u}bg)"/>'
            f'<circle cx="300" cy="290" r="214" fill="#fff" opacity=".38"/>'
            f'<circle cx="300" cy="290" r="252" fill="none" stroke="#fff" stroke-width="2" opacity=".55"/>'
            f'{sparks}{dots}{shadow}{_DRAW[kind](c, u)}</svg>')


# ------------------------------------------------------------------ hero scenes

def _sky_stars(rnd, n, ymax, twinkle=36, w=1600):
    out = []
    for i in range(n):
        x, y = rnd.uniform(0, w), rnd.uniform(0, ymax) ** 1.0
        r = rnd.choice((.7, .9, 1.2, 1.6, 2.2))
        op = rnd.uniform(.35, .95)
        anim = ''
        if i < twinkle:
            anim = (f'<animate attributeName="opacity" values="{_f(op * .25)};{_f(op)};{_f(op * .25)}" '
                    f'dur="{_f(rnd.uniform(2.4, 6))}s" begin="{_f(rnd.uniform(0, 4))}s" repeatCount="indefinite"/>')
        out.append(f'<circle cx="{_f(x)}" cy="{_f(y)}" r="{r}" fill="#fff" opacity="{_f(op)}">{anim}</circle>'
                   if anim else f'<circle cx="{_f(x)}" cy="{_f(y)}" r="{r}" fill="#fff" opacity="{_f(op)}"/>')
    for _ in range(6):
        x, y, r = rnd.uniform(40, w - 40), rnd.uniform(20, ymax * .8), rnd.uniform(7, 15)
        out.append(f'<path d="{_star4(x, y, r, .16)}" fill="#fff" opacity=".85"/>')
    return ''.join(out)


def _stall(x, ground, w, col, col2, lit):
    h = 120
    top = ground - h
    n = 6
    sw = w / n
    flaps = ''.join(
        f'<path d="M{_f(x + i * sw)} {top + 38}h{_f(sw)}q{_f(-sw / 2)} 22 {_f(-sw)} 0z" fill="{col if i % 2 else col2}"/>'
        for i in range(n))
    roof = f'<path d="M{_f(x - 10)} {top + 38}L{_f(x + w * .15)} {top}H{_f(x + w * .85)}L{_f(x + w + 10)} {top + 38}Z" fill="{col2}"/>'
    glow = (f'<rect x="{_f(x + 8)}" y="{top + 44}" width="{_f(w - 16)}" height="{h - 44}" fill="{lit}" opacity=".28"/>'
            f'<circle cx="{_f(x + w / 2)}" cy="{top + 60}" r="26" fill="{lit}" opacity=".35"/>')
    posts = (f'<rect x="{_f(x)}" y="{top + 38}" width="6" height="{h - 38}" fill="#0a0e24"/>'
             f'<rect x="{_f(x + w - 6)}" y="{top + 38}" width="6" height="{h - 38}" fill="#0a0e24"/>'
             f'<rect x="{_f(x)}" y="{ground - 36}" width="{_f(w)}" height="36" fill="#0a0e24"/>')
    return glow + posts + roof + flaps


def _acacia(x, ground, s, col):
    return (f'<path d="M{_f(x - 5 * s)} {ground}Q{_f(x - 2 * s)} {_f(ground - 60 * s)} {_f(x - 28 * s)} {_f(ground - 100 * s)}'
            f'L{_f(x - 20 * s)} {_f(ground - 104 * s)}Q{_f(x + 4 * s)} {_f(ground - 70 * s)} {_f(x + 4 * s)} {_f(ground - 100 * s)}'
            f'Q{_f(x + 8 * s)} {_f(ground - 56 * s)} {_f(x + 5 * s)} {ground}Z" fill="{col}"/>'
            f'<ellipse cx="{_f(x - 10 * s)}" cy="{_f(ground - 112 * s)}" rx="{_f(78 * s)}" ry="{_f(18 * s)}" fill="{col}"/>'
            f'<ellipse cx="{_f(x + 36 * s)}" cy="{_f(ground - 100 * s)}" rx="{_f(52 * s)}" ry="{_f(14 * s)}" fill="{col}"/>'
            f'<ellipse cx="{_f(x - 54 * s)}" cy="{_f(ground - 98 * s)}" rx="{_f(40 * s)}" ry="{_f(12 * s)}" fill="{col}"/>')


def _ridge(rnd, base, amp, step, col, w=1600, h=700):
    pts, x = [], 0
    y = base
    while x <= w + step:
        y = base + rnd.uniform(-amp, amp)
        pts.append((x, y))
        x += step
    d = f'M0 {h}L' + 'L'.join(f'{_f(px)} {_f(py)}' for px, py in pts) + f'L{w + step} {h}Z'
    return f'<path d="{d}" fill="{col}"/>'


def _city(rnd, ground, col, col_win, lit_colors, windows=True, x0=0, hmin=90, hmax=360):
    out, x = [], x0
    while x < 1600:
        bw = rnd.randrange(50, 130, 10)
        bh = rnd.randrange(hmin, hmax, 10)
        out.append(f'<rect x="{x}" y="{ground - bh}" width="{bw}" height="{bh + 4}" fill="{col}"/>')
        if rnd.random() < .3:
            out.append(f'<rect x="{x + bw // 2 - 2}" y="{ground - bh - 26}" width="4" height="26" fill="{col}"/>')
        if windows:
            for wy in range(ground - bh + 14, ground - 12, 20):
                for wx in range(x + 10, x + bw - 12, 16):
                    if rnd.random() < .26:
                        out.append(f'<rect x="{wx}" y="{wy}" width="7" height="9" rx="1" fill="{rnd.choice(lit_colors)}" opacity="{_f(rnd.uniform(.5, .95))}"/>')
        x += bw + rnd.randrange(0, 12, 4)
    return ''.join(out)


def hero_svg(variant: int = 0) -> str:
    v = int(variant) % 4
    rnd = random.Random(_hx('hero', v))
    u = _uid('hero', v)
    W, H = 1600, 700
    head = f'<svg {_NS} viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Night sky over a marketplace">'
    if v == 0:  # market night, violet
        defs = (f'<linearGradient id="{u}s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0b1030"/>'
                f'<stop offset=".55" stop-color="#2a1b66"/><stop offset="1" stop-color="#7a3a9a"/></linearGradient>'
                f'<radialGradient id="{u}g" cx=".78" cy=".22" r=".5"><stop offset="0" stop-color="#c4b5fd" stop-opacity=".55"/>'
                f'<stop offset="1" stop-color="#c4b5fd" stop-opacity="0"/></radialGradient>'
                f'<filter id="{u}b" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="40"/></filter>')
        scene = (f'<rect width="{W}" height="{H}" fill="url(#{u}s)"/><rect width="{W}" height="{H}" fill="url(#{u}g)"/>'
                 f'<path d="M-100 330C300 210 520 420 860 280S1400 180 1700 300V150C1300 90 900 220 560 130S100 120 -100 200Z" fill="#22d3ee" opacity=".16" filter="url(#{u}b)"/>'
                 + _sky_stars(rnd, 170, 420)
                 + f'<circle cx="1260" cy="150" r="58" fill="#f5f3ff"/><circle cx="1284" cy="136" r="52" fill="#3a2478"/>'
                 f'<circle cx="1260" cy="150" r="90" fill="#ddd6fe" opacity=".12"/>'
                 + _ridge(rnd, 520, 26, 120, '#1c1450')
                 + _acacia(220, 620, 1.5, '#0d1030') + _acacia(1420, 626, 1.2, '#0d1030')
                 + _stall(380, 640, 190, '#f472b6', '#7c3aed', '#fcd34d')
                 + _stall(600, 640, 220, '#22d3ee', '#4f46e5', '#fde68a')
                 + _stall(860, 640, 180, '#fbbf24', '#be185d', '#fca5a5')
                 + _stall(1080, 640, 200, '#a78bfa', '#0e7490', '#fcd34d')
                 + f'<rect x="0" y="632" width="{W}" height="70" fill="#080b22"/>'
)
        lan = ''.join(f'<path d="M{x} 590V{y}" stroke="#0a0e24" stroke-width="2"/><circle cx="{x}" cy="{y}" r="6" fill="#fcd34d"><animate attributeName="opacity" values=".55;1;.55" dur="{2 + i % 3}s" repeatCount="indefinite"/></circle>'
                      for i, (x, y) in enumerate(((330, 548), (570, 552), (826, 548), (1056, 552), (1300, 548))))
        scene += lan
    elif v == 1:  # aurora over mountains, teal/green
        defs = (f'<linearGradient id="{u}s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#04101f"/>'
                f'<stop offset=".6" stop-color="#0b3a4a"/><stop offset="1" stop-color="#14706a"/></linearGradient>'
                f'<linearGradient id="{u}a" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#34d399"/>'
                f'<stop offset=".5" stop-color="#22d3ee"/><stop offset="1" stop-color="#a78bfa"/></linearGradient>'
                f'<filter id="{u}b" x="-30%" y="-60%" width="160%" height="220%"><feGaussianBlur stdDeviation="26"/></filter>')
        scene = (f'<rect width="{W}" height="{H}" fill="url(#{u}s)"/>'
                 + _sky_stars(rnd, 200, 400)
                 + f'<path d="M-60 300C260 120 520 380 820 210S1360 90 1680 250V400C1340 300 1020 440 760 330S220 420 -60 380Z" fill="url(#{u}a)" opacity=".5" filter="url(#{u}b)"/>'
                 f'<path d="M-60 240C280 60 540 300 840 150S1380 40 1680 180" fill="none" stroke="url(#{u}a)" stroke-width="14" opacity=".55" filter="url(#{u}b)"/>'
                 f'<path d="M0 560 330 330 470 420 700 250 940 470 1180 320 1600 560Z" fill="#0a2b3a"/>'
                 f'<path d="M700 250 650 330 700 316 740 346 780 322Z" fill="#e0f2fe" opacity=".85"/>'
                 f'<path d="M330 330 296 380 330 370 356 392Z" fill="#e0f2fe" opacity=".7"/>'
                 + _ridge(rnd, 560, 30, 100, '#07202c')
                 + _ridge(rnd, 630, 18, 80, '#04141d')
                 + _acacia(300, 660, 1.3, '#020b11') + _acacia(1260, 666, 1.6, '#020b11'))
    elif v == 2:  # sunset savannah
        defs = (f'<linearGradient id="{u}s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1a1040"/>'
                f'<stop offset=".35" stop-color="#5a1f6e"/><stop offset=".62" stop-color="#d9437a"/>'
                f'<stop offset=".82" stop-color="#ff9a56"/><stop offset="1" stop-color="#ffd27a"/></linearGradient>'
                f'<radialGradient id="{u}g" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#fff4c2"/>'
                f'<stop offset=".35" stop-color="#ffd27a" stop-opacity=".7"/><stop offset="1" stop-color="#ff9a56" stop-opacity="0"/></radialGradient>')
        birds = ''.join(f'<path d="M{x} {y}q10 -10 20 0q10 -10 20 0" fill="none" stroke="#2a1038" stroke-width="2.6" stroke-linecap="round"/>'
                        for x, y in ((420, 250), (470, 226), (520, 262), (1150, 200)))
        scene = (f'<rect width="{W}" height="{H}" fill="url(#{u}s)"/>'
                 + _sky_stars(rnd, 90, 200, twinkle=24)
                 + f'<circle cx="800" cy="470" r="270" fill="url(#{u}g)"/><circle cx="800" cy="480" r="86" fill="#fff0b8"/>'
                 + birds
                 + _ridge(rnd, 560, 14, 140, '#8a2a5e')
                 + _ridge(rnd, 600, 12, 120, '#3b1550')
                 + _acacia(300, 640, 1.9, '#1a0a26') + _acacia(1180, 646, 1.5, '#1a0a26') + _acacia(1450, 650, .9, '#1a0a26')
                 + f'<rect x="0" y="640" width="{W}" height="60" fill="#12071c"/>')
    else:  # city night, cyan/blue
        defs = (f'<linearGradient id="{u}s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#050a1e"/>'
                f'<stop offset=".6" stop-color="#0d2a5c"/><stop offset="1" stop-color="#1c6aa8"/></linearGradient>'
                f'<linearGradient id="{u}m" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
                f'<stop offset="1" stop-color="#bae6fd"/></linearGradient>')
        meteors = ''.join(
            f'<path d="M{x} {y}l{-dx} {-dx * .5}" stroke="url(#{u}m)" stroke-width="2.4" stroke-linecap="round" transform="rotate(0)"/>'
            for x, y, dx in ((1150, 90, 150), (420, 150, 110), (900, 40, 80)))
        scene = (f'<rect width="{W}" height="{H}" fill="url(#{u}s)"/>'
                 + _sky_stars(rnd, 190, 380)
                 + meteors
                 + f'<circle cx="360" cy="130" r="52" fill="#e0f2fe"/><circle cx="378" cy="120" r="46" fill="#0a1f4d"/>'
                 + _city(rnd, 640, '#0b2150', '#0b2150', ['#7dd3fc'], windows=False, hmin=160, hmax=420)
                 + _city(random.Random(_hx('hero3b')), 700, '#050d24', '#050d24', ['#fde68a', '#7dd3fc', '#fff'], hmin=90, hmax=300)
                 + f'<rect x="0" y="690" width="{W}" height="10" fill="#050d24"/>')
    return f'{head}<defs>{defs}</defs>{scene}</svg>'
