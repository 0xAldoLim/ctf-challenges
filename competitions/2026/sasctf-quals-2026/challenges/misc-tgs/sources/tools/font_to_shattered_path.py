import argparse
import json
import math
import random
import sys
from pathlib import Path

import pathops
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont


class _PathPen(BasePen):
    def __init__(self, glyph_set, scale: float):
        super().__init__(glyph_set)
        self.scale = scale
        self.path = pathops.Path()

    def _moveTo(self, p):
        self.path.moveTo(*self._tx(p))

    def _lineTo(self, p):
        self.path.lineTo(*self._tx(p))

    def _curveToOne(self, p1, p2, p3):
        x1, y1 = self._tx(p1)
        x2, y2 = self._tx(p2)
        x3, y3 = self._tx(p3)
        self.path.cubicTo(x1, y1, x2, y2, x3, y3)

    def _closePath(self):
        self.path.close()

    def _endPath(self):
        pass

    def _tx(self, p):
        return (p[0] * self.scale, -p[1] * self.scale)


class FontExtractor:
    def __init__(self, font_path: str, target_size: float = 60.0):
        self.font = TTFont(font_path)
        self.cmap = self.font.getBestCmap()
        upem = self.font["head"].unitsPerEm
        self.scale = target_size / upem
        self.glyph_set = self.font.getGlyphSet()

    def extract(self, ch: str) -> pathops.Path | None:
        cp = ord(ch)
        if cp not in self.cmap:
            return None
        pen = _PathPen(self.glyph_set, self.scale)
        self.glyph_set[self.cmap[cp]].draw(pen)
        if pen.path.bounds is None:
            return None
        return pen.path


CubicCut = tuple[tuple[float, float], tuple[float, float],
                 tuple[float, float], tuple[float, float]]


def _random_cut(bounds: tuple[float, float, float, float],
                rng: random.Random) -> CubicCut:
    minx, miny, maxx, maxy = bounds
    span = max(maxx - minx, maxy - miny, 1.0)
    cx = (minx + maxx) / 2.0
    cy = (miny + maxy) / 2.0
    pad = span * 0.4
    minx -= pad
    miny -= pad
    maxx += pad
    maxy += pad
    fminx, fmaxx = minx + (maxx - minx) * 0.2, maxx - (maxx - minx) * 0.2
    fminy, fmaxy = miny + (maxy - miny) * 0.2, maxy - (maxy - miny) * 0.2

    sides = ("L", "R", "T", "B")
    opposite = {"L": "R", "R": "L", "T": "B", "B": "T"}
    s1 = rng.choice(sides)
    s2 = opposite[s1] if rng.random() < 0.75 else \
        rng.choice([s for s in sides if s != s1])

    def edge(side: str) -> tuple[float, float]:
        if side == "L":
            return (minx, rng.uniform(fminy, fmaxy))
        if side == "R":
            return (maxx, rng.uniform(fminy, fmaxy))
        if side == "T":
            return (rng.uniform(fminx, fmaxx), miny)
        return (rng.uniform(fminx, fmaxx), maxy)

    p0 = edge(s1)
    p3 = edge(s2)
    ctl_r = span * 0.15

    def ctl() -> tuple[float, float]:
        return (cx + rng.uniform(-ctl_r, ctl_r),
                cy + rng.uniform(-ctl_r, ctl_r))

    return (p0, ctl(), ctl(), p3)


def split_path_by_cut(path: pathops.Path, cut: CubicCut) -> list[pathops.Path]:
    p0, p1, p2, p3 = cut
    b = path.bounds
    if b is None:
        return [path]
    ext = max(b[2] - b[0], b[3] - b[1], 1.0) * 10.0

    dx = p3[0] - p0[0]
    dy = p3[1] - p0[1]
    L = math.hypot(dx, dy)
    if L < 1e-6:
        return [path]
    tx, ty = dx / L, dy / L
    nx, ny = -dy / L, dx / L

    q0 = (p0[0] - tx * ext, p0[1] - ty * ext)
    q3 = (p3[0] + tx * ext, p3[1] + ty * ext)

    def half_plane(sign: float) -> pathops.Path:
        h = pathops.Path()
        h.moveTo(*q0)
        h.lineTo(*p0)
        h.cubicTo(p1[0], p1[1], p2[0], p2[1], p3[0], p3[1])
        h.lineTo(*q3)
        h.lineTo(q3[0] + sign * nx * ext, q3[1] + sign * ny * ext)
        h.lineTo(q0[0] + sign * nx * ext, q0[1] + sign * ny * ext)
        h.close()
        return h

    pieces: list[pathops.Path] = []
    for sign in (+1.0, -1.0):
        frag = pathops.op(path, half_plane(sign), pathops.PathOp.INTERSECTION)
        if frag.bounds is not None and abs(frag.area) > 0.5:
            pieces.append(frag)
    return pieces


def cut_glyph(path: pathops.Path, rng: random.Random,
              targets: tuple[int, ...] = (3, 4),
              max_tries: int = 60,
              min_balance: float = 0.15,
              good_balance: float = 0.40) -> list[pathops.Path]:
    if path.bounds is None:
        return []
    best: list[pathops.Path] = []
    best_balance = -1.0
    for _ in range(max_tries):
        try:
            after_c1 = split_path_by_cut(path, _random_cut(path.bounds, rng))
            cut2 = _random_cut(path.bounds, rng)
            after_c2: list[pathops.Path] = []
            for piece in after_c1:
                after_c2.extend(split_path_by_cut(piece, cut2))
            pieces = [p for p in after_c2 if abs(p.area) > 0.5]
            if len(pieces) not in targets:
                if not best and pieces:
                    best = pieces
                continue
            areas = sorted(abs(p.area) for p in pieces)
            balance = areas[0] / areas[-1] if areas[-1] > 0 else 0.0
            if balance < min_balance:
                continue
            if balance > best_balance:
                best = pieces
                best_balance = balance
            if balance >= good_balance:
                break
        except Exception:
            continue
    return best


def _close_eq(a, b, eps: float = 0.01) -> bool:
    return abs(a[0] - b[0]) < eps and abs(a[1] - b[1]) < eps


def _flush_sh(items: list[dict], v: list[list[float]],
              i_t: list[list[float]], o_t: list[list[float]],
              decimals: int) -> None:
    if len(v) < 2:
        return
    if _close_eq(v[-1], v[0]):
        i_t[0] = i_t[-1]
        v.pop()
        i_t.pop()
        o_t.pop()
    items.append({
        "ty": "sh",
        "ks": {"a": 0, "k": {
            "c": True,
            "v": [[round(p[0], decimals), round(p[1], decimals)] for p in v],
            "i": [[round(p[0], decimals), round(p[1], decimals)] for p in i_t],
            "o": [[round(p[0], decimals), round(p[1], decimals)] for p in o_t],
        }},
    })


def path_to_sh_items(path: pathops.Path, decimals: int = 2) -> list[dict]:
    items: list[dict] = []
    v: list[list[float]] = []
    i_t: list[list[float]] = []
    o_t: list[list[float]] = []
    last: tuple[float, float] | None = None

    for verb, pts in path.segments:
        if verb == "moveTo":
            if v:
                _flush_sh(items, v, i_t, o_t, decimals)
                v, i_t, o_t = [], [], []
            pt = pts[0]
            v = [[pt[0], pt[1]]]
            i_t = [[0.0, 0.0]]
            o_t = [[0.0, 0.0]]
            last = pt
        elif verb == "lineTo":
            pt = pts[0]
            v.append([pt[0], pt[1]])
            i_t.append([0.0, 0.0])
            o_t.append([0.0, 0.0])
            last = pt
        elif verb == "curveTo":
            c1, c2, end = pts
            if last is None:
                last = (v[-1][0], v[-1][1]) if v else (0.0, 0.0)
            o_t[-1] = [c1[0] - last[0], c1[1] - last[1]]
            v.append([end[0], end[1]])
            i_t.append([c2[0] - end[0], c2[1] - end[1]])
            o_t.append([0.0, 0.0])
            last = end
        elif verb == "qCurveTo":
            if last is None:
                last = (v[-1][0], v[-1][1]) if v else (0.0, 0.0)
            if len(pts) <= 2:
                quads = [(pts[0], pts[1])]
            else:
                ctrls = pts[:-1]
                end_pt = pts[-1]
                quads = []
                for k in range(len(ctrls) - 1):
                    c_a = ctrls[k]
                    c_b = ctrls[k + 1]
                    mid = ((c_a[0] + c_b[0]) * 0.5, (c_a[1] + c_b[1]) * 0.5)
                    quads.append((c_a, mid))
                quads.append((ctrls[-1], end_pt))
            for c, end in quads:
                c1x = last[0] + 2 / 3 * (c[0] - last[0])
                c1y = last[1] + 2 / 3 * (c[1] - last[1])
                c2x = end[0] + 2 / 3 * (c[0] - end[0])
                c2y = end[1] + 2 / 3 * (c[1] - end[1])
                o_t[-1] = [c1x - last[0], c1y - last[1]]
                v.append([end[0], end[1]])
                i_t.append([c2x - end[0], c2y - end[1]])
                o_t.append([0.0, 0.0])
                last = end
        elif verb == "closePath":
            if v:
                _flush_sh(items, v, i_t, o_t, decimals)
                v, i_t, o_t = [], [], []
            last = None
    if v:
        _flush_sh(items, v, i_t, o_t, decimals)
    return items


def rotate_path(path: pathops.Path, angle_deg: float,
                cx: float, cy: float) -> pathops.Path:
    if angle_deg == 0 or path.bounds is None:
        return path
    rad = math.radians(angle_deg)
    co, si = math.cos(rad), math.sin(rad)

    def tx(pt):
        x = pt[0] - cx
        y = pt[1] - cy
        return (co * x - si * y + cx, si * x + co * y + cy)

    out = pathops.Path()
    last = (0.0, 0.0)
    move_start = (0.0, 0.0)
    for verb, pts in path.segments:
        if verb == "moveTo":
            p = tx(pts[0])
            out.moveTo(*p)
            last = p
            move_start = p
        elif verb == "lineTo":
            p = tx(pts[0])
            out.lineTo(*p)
            last = p
        elif verb == "curveTo":
            a = tx(pts[0])
            b = tx(pts[1])
            c = tx(pts[2])
            out.cubicTo(a[0], a[1], b[0], b[1], c[0], c[1])
            last = c
        elif verb == "qCurveTo":
            tpts = [tx(p) for p in pts]
            if len(tpts) <= 2:
                quads = [(tpts[0], tpts[1])]
            else:
                ctrls = tpts[:-1]
                end_pt = tpts[-1]
                quads = []
                for k in range(len(ctrls) - 1):
                    ca, cb = ctrls[k], ctrls[k + 1]
                    mid = ((ca[0] + cb[0]) * 0.5, (ca[1] + cb[1]) * 0.5)
                    quads.append((ca, mid))
                quads.append((ctrls[-1], end_pt))
            for ctrl, end in quads:
                c1x = last[0] + 2 / 3 * (ctrl[0] - last[0])
                c1y = last[1] + 2 / 3 * (ctrl[1] - last[1])
                c2x = end[0] + 2 / 3 * (ctrl[0] - end[0])
                c2y = end[1] + 2 / 3 * (ctrl[1] - end[1])
                out.cubicTo(c1x, c1y, c2x, c2y, end[0], end[1])
                last = end
        elif verb == "closePath":
            out.close()
            last = move_start
    return out


def tr_static(p=(0, 0), a=(0, 0), s=(100, 100), r=0, o=100) -> dict:
    return {
        "ty": "tr",
        "p": {"a": 0, "k": list(p)},
        "a": {"a": 0, "k": list(a)},
        "s": {"a": 0, "k": list(s)},
        "r": {"a": 0, "k": r},
        "o": {"a": 0, "k": o},
        "sk": {"a": 0, "k": 0},
        "sa": {"a": 0, "k": 0},
    }


def make_fragment_group(frag: pathops.Path, fill_color,
                        *, fill_opacity: int = 100, fill_rule: int = 2,
                        transform: dict | None = None,
                        name: str = "frag") -> dict:
    if transform is None:
        transform = tr_static()
    sh_items = path_to_sh_items(frag)
    return {
        "ty": "gr",
        "hd": False,
        "np": len(sh_items) + 2,
        "nm": name,
        "it": sh_items + [
            {"ty": "fl", "hd": False, "r": fill_rule,
             "c": {"a": 0, "k": list(fill_color)},
             "o": {"a": 0, "k": fill_opacity}},
            transform,
        ],
    }


def path_anchor_centroid(path: pathops.Path) -> tuple[float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for verb, pts in path.segments:
        if verb in ("moveTo", "lineTo"):
            xs.append(pts[0][0])
            ys.append(pts[0][1])
        elif verb == "curveTo":
            xs.append(pts[2][0])
            ys.append(pts[2][1])
        elif verb == "qCurveTo":
            xs.append(pts[-1][0])
            ys.append(pts[-1][1])
    if not xs:
        b = path.bounds or (0, 0, 0, 0)
        return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def hsl_rgb(h: float, s: float = 0.75, l: float = 0.55) -> list[float]:
    h = (h % 360) / 360.0

    def f(t: float) -> float:
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    if s == 0:
        return [l, l, l]
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    return [f(h + 1 / 3), f(h), f(h - 1 / 3)]


def outline_group(glyph: pathops.Path, color=(0.55, 0.55, 0.6),
                  width: float = 1.0, opacity: int = 45) -> dict:
    sh_items = path_to_sh_items(glyph)
    return {
        "ty": "gr",
        "hd": False,
        "np": len(sh_items) + 2,
        "nm": "outline",
        "it": sh_items + [
            {"ty": "st", "hd": False,
             "c": {"a": 0, "k": list(color) + [1]},
             "o": {"a": 0, "k": opacity},
             "w": {"a": 0, "k": width},
             "lc": 2, "lj": 2, "ml": 4},
            tr_static(),
        ],
    }


def char_layer(extractor: FontExtractor, ch: str, rng: random.Random, *,
               frame: int, ind: int, canvas: int = 512,
               fill_fraction: float = 0.6, explode: float = 1.0) -> dict | None:
    glyph = extractor.extract(ch)
    if glyph is None or glyph.bounds is None:
        return None

    minx, miny, maxx, maxy = glyph.bounds
    gw = maxx - minx
    gh = maxy - miny
    bx = (minx + maxx) / 2.0
    by = (miny + maxy) / 2.0

    fragments = cut_glyph(glyph, rng)
    if not fragments:
        return None

    shapes: list[dict] = [outline_group(glyph)]
    n = len(fragments)
    for i, frag in enumerate(fragments):
        cx, cy = path_anchor_centroid(frag)
        dx = cx - bx
        dy = cy - by
        d = math.hypot(dx, dy)
        if d < 0.5:
            ang = i * 2 * math.pi / max(n, 1)
            ux, uy = math.cos(ang), math.sin(ang)
        else:
            ux, uy = dx / d, dy / d
        disp = (round(ux * explode, 2), round(uy * explode, 2))
        color = hsl_rgb(i * 360.0 / n + 25.0)
        shapes.append(make_fragment_group(
            frag, list(color) + [1],
            fill_opacity=85,
            transform=tr_static(p=disp),
        ))

    layer_scale = (canvas * fill_fraction) / max(gw, gh, 1.0)

    return {
        "ddd": 0, "ty": 4, "nm": f"{ch!r}@{frame}", "sr": 1,
        "ks": {
            "a": {"a": 0, "k": [round(bx, 2), round(by, 2), 0]},
            "p": {"a": 0, "k": [canvas / 2, canvas / 2, 0]},
            "s": {"a": 0, "k": [round(layer_scale * 100, 2),
                                round(layer_scale * 100, 2), 100]},
            "r": {"a": 0, "k": 0},
            "o": {"a": 0, "k": 100},
        },
        "ao": 0, "ip": frame, "op": frame + 1, "st": 0, "bm": 0, "ind": ind,
        "shapes": shapes,
    }


def build_doc(text: str, *, font: str, glyph_size: float,
              seed: int, canvas: int, fill_fraction: float, explode: float,
              fps: int) -> dict:
    rng = random.Random(seed)
    extractor = FontExtractor(font, target_size=glyph_size)

    layers: list[dict] = []
    skipped: list[str] = []
    for i, ch in enumerate(text):
        layer = char_layer(extractor, ch, rng,
                           frame=i, ind=i + 1, canvas=canvas,
                           fill_fraction=fill_fraction, explode=explode)
        if layer is None:
            skipped.append(ch)
            continue
        layers.append(layer)

    if skipped:
        print(f"WARN skipped: {skipped}", file=sys.stderr)

    return {
        "v": "5.7.2",
        "fr": fps,
        "ip": 0,
        "op": len(layers),
        "w": canvas,
        "h": canvas,
        "nm": "shattered glyphs",
        "ddd": 0,
        "assets": [],
        "layers": layers,
    }


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--text", default="flag{testflag}")
    p.add_argument("--out", default="sources/AnimatedSticker_shattered.json")
    p.add_argument("--font",
                   default=str(Path(__file__).resolve().parent.parent
                               / "Roboto-Regular.ttf"))
    p.add_argument("--glyph-size", type=float, default=60.0)
    p.add_argument("--canvas", type=int, default=512)
    p.add_argument("--fill-fraction", type=float, default=0.6)
    p.add_argument("--explode", type=float, default=4.0)
    p.add_argument("--fps", type=int, default=4)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args(argv)

    doc = build_doc(
        args.text, font=args.font, glyph_size=args.glyph_size,
        seed=args.seed, canvas=args.canvas,
        fill_fraction=args.fill_fraction, explode=args.explode, fps=args.fps,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes, "
          f"{len(doc['layers'])} char layers @ {doc['fr']} fps, "
          f"frames 0..{doc['op']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
