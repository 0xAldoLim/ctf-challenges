import argparse
import gzip
import json
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from font_to_shattered_path import (
    FontExtractor, cut_glyph, make_fragment_group, rotate_path,
)


def _solve_bezier_y(x: float, ox: float, oy: float, ix: float, iy: float,
                    iters: int = 8) -> float:
    t = x
    for _ in range(iters):
        bx = 3 * (1 - t) ** 2 * t * ox + 3 * (1 - t) * t ** 2 * ix + t ** 3
        dbx = 3 * (1 - t) ** 2 * ox + 6 * (1 - t) * t * (ix - ox) \
              + 3 * t ** 2 * (1 - ix)
        if abs(dbx) < 1e-6:
            break
        t -= (bx - x) / dbx
        t = max(0.0, min(1.0, t))
    return 3 * (1 - t) ** 2 * t * oy + 3 * (1 - t) * t ** 2 * iy + t ** 3


def _as_list(x: Any) -> list | None:
    if x is None:
        return None
    if isinstance(x, (list, tuple)):
        return list(x)
    return [x]


def eval_prop(prop: dict | None, frame: float):
    if prop is None:
        return None
    if prop.get("a") != 1:
        return prop.get("k")
    kfs = prop.get("k") or []
    if not kfs:
        return None
    if frame <= kfs[0].get("t", 0):
        return _as_list(kfs[0].get("s"))
    if frame >= kfs[-1].get("t", 0):
        return _as_list(kfs[-1].get("s"))
    for i in range(len(kfs) - 1):
        t0 = kfs[i].get("t", 0)
        t1 = kfs[i + 1].get("t", 0)
        if t0 <= frame <= t1 and t1 > t0:
            s0 = _as_list(kfs[i].get("s")) or []
            s1 = _as_list(kfs[i + 1].get("s")) or s0
            if kfs[i].get("h") == 1:
                return s0
            progress = (frame - t0) / (t1 - t0)
            o = kfs[i].get("o") or {}
            i_h = kfs[i + 1].get("i") or {}
            ox = (_as_list(o.get("x")) or [0.167])[0]
            oy = (_as_list(o.get("y")) or [0.167])[0]
            ix = (_as_list(i_h.get("x")) or [0.833])[0]
            iy = (_as_list(i_h.get("y")) or [0.833])[0]
            eased = _solve_bezier_y(progress, ox, oy, ix, iy)
            return [a + (b - a) * eased for a, b in zip(s0, s1)]
    return _as_list(kfs[-1].get("s"))


@dataclass
class AffineXY:
    p: tuple[float, float] = (0.0, 0.0)
    a: tuple[float, float] = (0.0, 0.0)
    s: tuple[float, float] = (100.0, 100.0)
    r: float = 0.0

    def apply(self, pt: tuple[float, float]) -> tuple[float, float]:
        x = pt[0] - self.a[0]
        y = pt[1] - self.a[1]
        x *= self.s[0] / 100.0
        y *= self.s[1] / 100.0
        rad = math.radians(self.r)
        co, si = math.cos(rad), math.sin(rad)
        x, y = x * co - y * si, x * si + y * co
        return (x + self.p[0], y + self.p[1])

    @classmethod
    def from_ks(cls, ks: dict, frame: float) -> "AffineXY":
        p = eval_prop(ks.get("p"), frame) or [0, 0]
        a = eval_prop(ks.get("a"), frame) or [0, 0]
        s = eval_prop(ks.get("s"), frame) or [100, 100]
        r = eval_prop(ks.get("r"), frame)
        if isinstance(r, list):
            r = r[0] if r else 0.0
        return cls(
            p=(float(p[0]), float(p[1])),
            a=(float(a[0]), float(a[1])),
            s=(float(s[0]), float(s[1])),
            r=float(r) if r is not None else 0.0,
        )


def layer_chain(layer: dict, layers: list[dict], frame: float) -> list[AffineXY]:
    by_ind = {l.get("ind"): l for l in layers if l.get("ind") is not None}
    out: list[AffineXY] = []
    cur: dict | None = layer
    seen: set[int] = set()
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        out.append(AffineXY.from_ks(cur.get("ks", {}), frame))
        pid = cur.get("parent")
        cur = by_ind.get(pid) if pid is not None else None
    return out


def apply_group_chain(pt: tuple[float, float], group_path: list[dict],
                      frame: float) -> tuple[float, float]:
    for grp in reversed(group_path):
        tr_item = next((i for i in grp.get("it", []) if i.get("ty") == "tr"), None)
        if tr_item is not None:
            pt = AffineXY.from_ks(tr_item, frame).apply(pt)
    return pt


def to_world(pt: tuple[float, float], group_path: list[dict],
             layer: dict, layers: list[dict], frame: float) -> tuple[float, float]:
    pt = apply_group_chain(pt, group_path, frame)
    for tr in layer_chain(layer, layers, frame):
        pt = tr.apply(pt)
    return pt


@dataclass
class StrokeTarget:
    layer: dict
    group_path: list[dict]
    paths: list[dict]
    stroke: dict

    def active(self, frame: float) -> bool:
        return self.layer.get("ip", 0) <= frame < self.layer.get("op", 0)

    def color(self, frame: float) -> list[float] | None:
        c = eval_prop(self.stroke.get("c"), frame)
        if not c:
            return None
        if len(c) == 3:
            return [c[0], c[1], c[2], 1.0]
        return [c[0], c[1], c[2], c[3]]

    def width(self, frame: float) -> float:
        w = eval_prop(self.stroke.get("w"), frame)
        if isinstance(w, list):
            w = w[0] if w else None
        return float(w) if w is not None else 1.0


def find_stroke_targets(layers: list[dict]) -> list[StrokeTarget]:
    out: list[StrokeTarget] = []
    for layer in layers:
        if layer.get("ty") != 4:
            continue
        for shape in layer.get("shapes", []):
            _walk_for_strokes(shape, [], layer, out)
    return out


def _walk_for_strokes(item: dict, stack: list[dict], layer: dict,
                      out: list[StrokeTarget]) -> None:
    if item.get("ty") != "gr":
        return
    new_stack = stack + [item]
    sibling_paths: list[dict] = []
    for sub in item.get("it", []):
        ty = sub.get("ty")
        if ty == "sh":
            sibling_paths.append(sub)
        elif ty == "st" and sibling_paths:
            out.append(StrokeTarget(layer, new_stack, list(sibling_paths), sub))
        elif ty == "gr":
            _walk_for_strokes(sub, new_stack, layer, out)


def sample_path_vertex(sh: dict, frame: float, rng: random.Random
                       ) -> tuple[float, float] | None:
    ks = sh.get("ks", {})
    if ks.get("a") == 1:
        kfs = ks.get("k") or []
        if not kfs:
            return None
        chosen = kfs[0]
        for kf in kfs:
            if kf.get("t", 0) <= frame:
                chosen = kf
            else:
                break
        s = chosen.get("s")
        path_obj = s[0] if isinstance(s, list) and s else s
    else:
        path_obj = ks.get("k")
    if not isinstance(path_obj, dict):
        return None
    verts = path_obj.get("v") or []
    if not verts:
        return None
    v = rng.choice(verts)
    return (float(v[0]), float(v[1]))


def build_fragment_layer(frag, world_xy: tuple[float, float],
                         scale_pct: float, rot_deg: float,
                         color: list[float], frame: int, ind: int) -> dict:
    minx, miny, maxx, maxy = frag.bounds
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    frag = rotate_path(frag, rot_deg, cx, cy)
    group = make_fragment_group(frag, list(color), fill_opacity=100, name=f"f{ind}")
    return {
        "ddd": 0, "ty": 4, "nm": f"f{ind}", "sr": 1,
        "ks": {
            "a": {"a": 0, "k": [round(cx, 2), round(cy, 2), 0]},
            "p": {"a": 0, "k": [round(world_xy[0], 2), round(world_xy[1], 2), 0]},
            "s": {"a": 0, "k": [round(scale_pct, 2), round(scale_pct, 2), 100]},
            "r": {"a": 0, "k": 0},
            "o": {"a": 0, "k": 100},
        },
        "ao": 0, "ip": frame, "op": frame + 1, "st": 0, "bm": 0, "ind": ind,
        "shapes": [group],
    }


def reparent_layer(child: dict, parent: dict) -> None:
    pk = parent["ks"]
    ck = child["ks"]
    pa = pk["a"]["k"]
    pp = pk["p"]["k"]
    p_s = float(pk["s"]["k"][0])
    pr = pk["r"]["k"]
    p_r = float(pr[0] if isinstance(pr, list) else pr)
    ca = ck["a"]["k"]
    cp = ck["p"]["k"]
    c_s = float(ck["s"]["k"][0])
    cr = ck["r"]["k"]
    c_r = float(cr[0] if isinstance(cr, list) else cr)

    rp_rad = math.radians(p_r)
    rc_rad = math.radians(c_r)
    cos_p, sin_p = math.cos(rp_rad), math.sin(rp_rad)
    cos_c, sin_c = math.cos(rc_rad), math.sin(rc_rad)

    scaled_ac_x = c_s / 100.0 * ca[0]
    scaled_ac_y = c_s / 100.0 * ca[1]
    rot_ac_x = cos_c * scaled_ac_x - sin_c * scaled_ac_y
    rot_ac_y = sin_c * scaled_ac_x + cos_c * scaled_ac_y

    delta_x = cp[0] - rot_ac_x - pp[0]
    delta_y = cp[1] - rot_ac_y - pp[1]

    inv_scale = 100.0 / p_s if p_s != 0 else 0.0
    rot_delta_x = cos_p * delta_x + sin_p * delta_y
    rot_delta_y = -sin_p * delta_x + cos_p * delta_y

    local_x = pa[0] + rot_delta_x * inv_scale
    local_y = pa[1] + rot_delta_y * inv_scale
    new_scale = c_s * 100.0 / p_s if p_s != 0 else 0.0
    new_rot = c_r - p_r

    ck["a"] = {"a": 0, "k": [0, 0, 0]}
    ck["p"] = {"a": 0, "k": [round(local_x, 4), round(local_y, 4), 0]}
    ck["s"] = {"a": 0, "k": [round(new_scale, 4), round(new_scale, 4), 100]}
    ck["r"] = {"a": 0, "k": round(new_rot, 4)}
    child["parent"] = parent["ind"]


def random_parents_within_glyph(frags: list[dict], rng: random.Random) -> int:
    n = len(frags)
    if n < 2:
        return 0
    n_pairs = n // 2
    pool = list(frags)
    rng.shuffle(pool)
    parents = pool[:n_pairs]
    children = pool[n_pairs:2 * n_pairs]
    for p, c in zip(parents, children):
        reparent_layer(c, p)
    return n_pairs


def merge_and_scramble(originals: list[dict],
                       fragments_with_host_idx: list[tuple[dict, int]],
                       rng: random.Random) -> list[dict]:
    n = len(originals)
    slots: list[list[dict]] = [[] for _ in range(n + 1)]
    items = list(fragments_with_host_idx)
    rng.shuffle(items)
    for frag, host_idx in items:
        allowed = list(range(host_idx + 1, n + 1))
        if not allowed:
            slots[n].append(frag)
            continue
        min_count = min(len(slots[s]) for s in allowed)
        candidates = [s for s in allowed if len(slots[s]) == min_count]
        chosen = rng.choice(candidates)
        slots[chosen].append(frag)
    for s in slots:
        rng.shuffle(s)
    out: list[dict] = []
    for i in range(n):
        out.extend(slots[i])
        out.append(originals[i])
    out.extend(slots[n])
    return out


def scrub_names(layers: list[dict]) -> None:
    counter = [0]

    def fresh() -> str:
        counter[0] += 1
        return f"p{counter[0]}"

    def walk(item):
        if not isinstance(item, dict):
            return
        if item.get("ty") == "gr":
            item["nm"] = fresh()
            for sub in item.get("it", []) or []:
                walk(sub)

    for layer in layers:
        layer["nm"] = fresh()
        for shape in layer.get("shapes", []) or []:
            walk(shape)


def embed(args) -> int:
    rng = random.Random(args.seed)
    src = Path(args.src)
    dst = Path(args.dst)
    if not src.exists():
        print(f"source not found: {src}", file=sys.stderr)
        return 1

    with gzip.open(src, "rb") as f:
        data = json.load(f)

    ip = int(data.get("ip", 0))
    op = int(data.get("op", 60))
    fr = data.get("fr", 60)
    layers: list[dict] = data.setdefault("layers", [])

    existing_inds = [l.get("ind", 0) for l in layers] or [0]
    next_ind = max(existing_inds) + 1

    extractor = FontExtractor(args.font, target_size=args.glyph_size)
    targets = find_stroke_targets(layers)

    print(f"sticker: ip={ip} op={op} fr={fr} layers={len(layers)} "
          f"stroked_groups={len(targets)}")
    print(f"font={Path(args.font).name} glyph_size={args.glyph_size}px "
          f"seed={args.seed}")
    print(f"flag={args.flag!r} start_frame={args.start_frame}")
    print()

    report: list[tuple[int, str, int, int, int, list[str]]] = []
    skipped: list[str] = []
    original_layers = list(layers)
    pending_fragments: list[tuple[dict, int]] = []

    for ci, ch in enumerate(args.flag):
        frame = args.start_frame + ci
        if not (ip <= frame < op):
            print(f"WARN: char {ci} {ch!r}: frame {frame} outside [{ip}, {op}), skip")
            skipped.append(ch)
            continue
        glyph = extractor.extract(ch)
        if glyph is None or glyph.bounds is None:
            print(f"WARN: char {ci} {ch!r}: no glyph in font, skip")
            skipped.append(ch)
            continue
        fragments = cut_glyph(glyph, rng)
        if not fragments:
            print(f"WARN: char {ci} {ch!r}: failed to fragment, skip")
            skipped.append(ch)
            continue
        active = [t for t in targets if t.active(frame)]
        if not active:
            print(f"WARN: char {ci} {ch!r}: no stroked groups active at frame {frame}")
            skipped.append(ch)
            continue
        n_use = min(len(fragments), len(active))
        hosts = rng.sample(active, n_use)
        used_frags = fragments[:n_use]

        host_notes: list[str] = []
        glyph_layers: list[dict] = []
        for frag, host in zip(used_frags, hosts):
            path = rng.choice(host.paths)
            local = sample_path_vertex(path, frame, rng)
            if local is None:
                host_notes.append("no-vert")
                continue
            world = to_world(local, host.group_path, host.layer, layers, frame)
            stroke_w = host.width(frame)
            scale_pct = rng.uniform(0.01, 0.3)
            rot = rng.uniform(0, 360)
            color = host.color(frame) or [0.0, 0.0, 0.0, 1.0]
            frag_layer = build_fragment_layer(
                frag, world, scale_pct, rot, color, frame, next_ind,
            )
            next_ind += 1
            try:
                host_orig_idx = original_layers.index(host.layer)
            except ValueError:
                host_orig_idx = 0
            pending_fragments.append((frag_layer, host_orig_idx))
            glyph_layers.append(frag_layer)
            hl_name = host.layer.get("nm", "?")
            host_notes.append(
                f"{hl_name!s}@({world[0]:.0f},{world[1]:.0f}) "
                f"w={stroke_w:.1f} s={scale_pct:.3f}"
            )
        n_pairs = random_parents_within_glyph(glyph_layers, rng)
        report.append((ci, ch, frame, len(used_frags), n_pairs, host_notes))

    layers[:] = merge_and_scramble(original_layers, pending_fragments, rng)
    data["layers"] = layers

    scrub_names(layers)

    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    with gzip.open(dst, "wb", compresslevel=9) as f:
        f.write(raw)

    print("--- per-character report ---")
    for ci, ch, frame, n_frags, n_pairs, notes in report:
        print(f"  [{ci:2}] {ch!r:>4} frame={frame:3} "
              f"fragments={n_frags} reparented_pairs={n_pairs}")
        for note in notes:
            print(f"        - {note}")
    if skipped:
        print(f"\nskipped: {skipped}")

    src_sz = src.stat().st_size
    dst_sz = dst.stat().st_size
    raw_sz = len(raw)
    print(f"\nsrc={src_sz} dst={dst_sz} (delta {dst_sz - src_sz:+d}) raw_json={raw_sz}")
    if dst_sz > 64 * 1024:
        print(f"WARNING: result is {dst_sz} bytes (> 64 KiB Telegram sticker limit)",
              file=sys.stderr)
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--flag", default="SAS{placeholder}")
    p.add_argument("--start-frame", type=int, default=5)
    p.add_argument("--src", default="stickerpack/11.tgs")
    p.add_argument("--dst", default="11.tgs")
    p.add_argument("--font",
                   default=str(Path(__file__).resolve().parent.parent
                               / "Roboto-Regular.ttf"))
    p.add_argument("--glyph-size", type=float, default=60.0)
    p.add_argument("--seed", type=int, default=67)
    return embed(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
