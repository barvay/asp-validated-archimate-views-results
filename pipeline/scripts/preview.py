"""Deterministic preview of the abstract layout, imported by scripts/run.py; no LLM, not validated.

  preview.py <run dir>    RUN/1_filter.lp + RUN/2_layout.lp -> RUN/2_preview.drawio

Drawn after gate 2 so a first picture is there while the drawio agent works; nothing downstream
reads it. Grid layout: columns from left_of, rows per band from above, containers sized from their contents,
`other` boxes outside every frame next to the band they are related to. Within the left_of facts,
the columns are placed by each of STRATEGIES, and the drawing with the fewest edge crossings is kept. Edges leave and enter at ports spread
over the box sides and run through the empty gaps between rows and columns. Follows the drawing
conventions of prompts/drawio.md (ids, labels, colours, frames, notation), so it passes gate 3.
"""
import html
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import context
import pipeline

OUTPUT = "2_preview.drawio"
BANDS = ("motivation", "business", "application", "technology")
NOTATION = {
    "Composition": "startArrow=diamondThin;startFill=1;startSize=10;endArrow=none;",
    "Aggregation": "startArrow=diamondThin;startFill=0;startSize=10;endArrow=none;",
    "Assignment": "startArrow=oval;startFill=1;endArrow=block;endFill=1;",
    "Realization": "endArrow=block;endFill=0;dashed=1;dashPattern=3 3;",
    "Serving": "endArrow=open;",
    "Triggering": "endArrow=block;endFill=1;",
    "Flow": "endArrow=block;endFill=1;dashed=1;dashPattern=6 4;",
    "Influence": "endArrow=open;dashed=1;dashPattern=6 4;",
    "Specialization": "endArrow=block;endFill=0;",
}
ACCESS = {"write": "startArrow=none;endArrow=open;", "read": "startArrow=open;endArrow=none;",
          "access": "startArrow=none;endArrow=none;", "readwrite": "startArrow=open;endArrow=open;"}
NESTING_RULES = pipeline.ASP_DIR / "common/nesting.lp"  # nesting relations: drawn by nesting, no edge
LEAF_W, LEAF_H, GAP_X, GAP_Y = 160, 70, 70, 60
PAD, HEAD = 20, 30            # padding inside containers and frames, room for their label
FRAME_GAP, MARGIN, TRACK = 70, 20, 8  # TRACK: largest distance of parallel edges in one gap
# Box placement, all within the layout facts: "rank" puts a box in the leftmost column its left_of
# facts allow; "pull" moves every box towards the columns of the boxes it is related to; "untangle"
# also swaps boxes within a row while that reduces crossings. write() keeps the one with the fewest.
STRATEGIES = ("rank", "pull", "untangle")


def layer_colors() -> dict:
    """band -> (fill, stroke, dashed) from asp/gate3/colors.lp."""
    text = (pipeline.ASP_DIR / "gate3/colors.lp").read_text(encoding="utf-8")
    keys = {}
    for band, key, value in re.findall(r'layer_color\((\w+),\s*"(\w+)",\s*"([^"]+)"\)\.', text):
        keys.setdefault(band, {})[key] = value
    return {b: (k["fillColor"], k["strokeColor"], k.get("dashed", "0")) for b, k in keys.items()}


def band_frames() -> dict:
    """band -> (frame id, label, stroke, fill) from asp/gate3/bands.lp."""
    text = (pipeline.ASP_DIR / "gate3/bands.lp").read_text(encoding="utf-8")
    return {b: rest for b, *rest in
            re.findall(r'band_frame\((\w+),\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)"\)\.', text)}


def nesting_kinds() -> tuple[set, set]:
    """Relation types and specializations shown by nesting, from asp/common/nesting.lp."""
    text = NESTING_RULES.read_text(encoding="utf-8")
    return (set(re.findall(r'^nesting_type\("([^"]+)"\)', text, re.M)),
            set(re.findall(r'^nesting_specialization\("([^"]+)"\)', text, re.M)))


def facts(text: str, pred: str) -> list:
    return re.findall(rf'^\s*{pred}\("([^"]+)",\s*"?([^"\)]+)"?\)', text, re.M)


def longest_path(nodes: list, edges: set) -> dict:
    """Rank = longest chain of predecessors; an edge closing a cycle is ignored."""
    pred = {n: [a for a, b in edges if b == n and a in nodes] for n in nodes}
    rank, busy = {}, set()

    def r(n):
        if n not in rank:
            if n in busy:
                return -1
            busy.add(n)
            rank[n] = max((r(p) + 1 for p in pred[n]), default=0)
        return rank[n]
    for n in nodes:
        r(n)
    return rank


def starts(widths: dict, gap: int) -> dict:
    """Start offset of each track, in key order, gap apart."""
    out, x = {}, 0
    for k, w in widths.items():
        out[k], x = x, x + w + gap
    return out


def preview(run: Path, strategy: str = "untangle") -> str:
    """The preview diagram of the run as draw.io XML, with the box placement strategy of STRATEGIES."""
    m = context.load_model()
    colors, frame_table = layer_colors(), band_frames()
    elements, relations = context.kept(run)
    lay = (run / "2_layout.lp").read_text(encoding="utf-8")
    band = dict(facts(lay, "band"))
    parent = dict(facts(lay, "inside"))
    lt, ab = facts(lay, "left_of"), facts(lay, "above")
    children = {}
    for e in elements:
        children.setdefault(parent.get(e), []).append(e)
    edges = [(rid, *m["relations"][rid]) for rid in relations]
    types, specs = nesting_kinds()
    edges = [(rid, rt, s, t) for rid, rt, s, t in edges
             if not ((rt in types or set(m["spec"].get(rid, [])) & specs) and parent.get(t) == s)]

    def anc(e):  # e, its container, ... up to a top-level box
        out = [e]
        while out[-1] in parent:
            out.append(parent[out[-1]])
        return out

    def frame(e):  # band frame of a box: its band, or for `other` the band of its contents or container
        if band.get(e) in BANDS:
            return band[e]
        for c in children.get(e, []):
            if f := frame(c):
                return f
        return frame(parent[e]) if e in parent else None

    def lift(pairs, sibs):  # a fact between descendants of two siblings holds for the siblings
        s, out = set(sibs), set()
        for a, b in pairs:
            x = next((x for x in anc(a) if x in s), None)
            y = next((y for y in anc(b) if y in s), None)
            if x and y and x != y:
                out.add((x, y))
        return out

    def subtree(e):
        return [d for d in elements if e in anc(d)]

    neighbours = {}
    for _, _, s, t in edges:
        neighbours.setdefault(s, []).append(t)
        neighbours.setdefault(t, []).append(s)

    # Top-level groups, top to bottom: the band frames, and slots ("free", i) before frame i for the
    # `other` boxes outside every frame, next to the frames of their neighbours, within their above facts.
    roots = children.get(None, [])
    frames = [b for b in BANDS if any(frame(e) == b for e in roots)]
    group = {e: frame(e) for e in roots if frame(e)}
    roots_ab = lift(ab, roots)
    loose = [e for e in roots if e not in group]
    for e in sorted(loose, key=longest_path(loose, roots_ab).get):
        lo = max([frames.index(group[a]) + 1 for a, b in roots_ab if b == e and group.get(a) in frames]
                 + [group[a][1] for a, b in roots_ab if b == e and isinstance(group.get(a), tuple)], default=0)
        hi = min([frames.index(group[b]) for a, b in roots_ab if a == e and group.get(b) in frames],
                 default=len(frames))
        ks = [frames.index(frame(n)) for x in subtree(e) for n in neighbours.get(x, []) if frame(n) in frames]
        want = int(sum(ks) / len(ks) + 1) if ks else len(frames)
        group[e] = ("free", min(max(want, lo), max(lo, hi)))
    order = [g for i in range(len(frames) + 1)
             for g in ([("free", i)] if ("free", i) in group.values() else []) + frames[i:i + 1]]

    def grid(sibs, grp):
        """Column and row of each sibling; the siblings of one group share the rows."""
        lts = lift(lt, sibs)
        col = longest_path(sibs, lts)
        last = max(col.values(), default=0)

        def bounds(e):  # the columns e may take with its left_of neighbours where they are
            return (max([col[a] + 1 for a, b in lts if b == e], default=0),
                    min([col[b] - 1 for a, b in lts if a == e], default=last))
        def bary(e):  # mean column of the boxes e is related to, None without any
            cs = [col[x] for d in subtree(e) for n in neighbours.get(d, []) for x in anc(n) if x in col and x != e]
            return sum(cs) / len(cs) if cs else None
        free = [e for e in sibs if not any(e in p for p in lts)]
        for _ in range(4):  # towards the barycentre of the boxes it is related to (rank: free boxes only)
            for e in (free if strategy == "rank" else sibs):
                if (b := bary(e)) is not None:
                    lo, hi = bounds(e)
                    col[e] = min(max(round(b), lo), hi)
        abs_ = {(a, b) for a, b in lift(ab, sibs) if grp(a) == grp(b)}  # across groups: the band order
        rmin = longest_path(sibs, abs_)
        row, taken = {}, set()
        for e in sorted(sibs, key=lambda e: (rmin[e], col[e], sibs.index(e))):
            r = max([rmin[e]] + [row[a] + 1 for a, b in abs_ if b == e and a in row])
            while (grp(e), r, col[e]) in taken:
                r += 1
            row[e] = r
            taken.add((grp(e), r, col[e]))
        if strategy == "untangle":
            untangle(sibs, col, row, grp, lts)
        return col, row

    def untangle(sibs, col, row, grp, lts):
        """Fewer crossings: swap two boxes of one row, or move a box to an empty cell of its row, as
        long as it lowers the crossings (and then the length) of the edges drawn as straight lines
        between the box centres, and every left_of still holds."""
        s = set(sibs)
        links = {(x, y) for a, b in neighbours.items() for n in b
                 for x in [next((x for x in anc(a) if x in s), None)]
                 for y in [next((y for y in anc(n) if y in s), None)] if x and y and x < y}

        def y(e):
            return (order.index(grp(e)) if grp(e) in order else 0, row[e])

        def cost():
            pts = {e: (col[e], y(e)[0] * 100 + y(e)[1]) for e in sibs}
            segs = []  # the router's shape: out of the box into the gap next to it, across, in
            for i, (a, b) in enumerate(links):
                (xa, ya), (xb, yb) = sorted((pts[a], pts[b]), key=lambda p: p[1])
                g = ya + 0.5 + 0.01 * i  # one track per edge in the gap
                segs += [(i, (xa, ya), (xa, g)), (i, (xa, g), (xb, g)), (i, (xb, g), (xb, yb))]

            def o(p, q, r):
                return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
            cross = sum(i != j and o(c, d, a) * o(c, d, b) < 0 and o(a, b, c) * o(a, b, d) < 0
                        for k, (i, a, b) in enumerate(segs) for j, c, d in segs[k + 1:])
            return cross, sum(abs(pts[a][0] - pts[b][0]) for a, b in links)

        def legal():
            return all(col[a] < col[b] for a, b in lts)
        cells = {(grp(e), row[e], col[e]): e for e in sibs}
        width = range(max(col.values(), default=0) + 1)
        best = cost()
        for _ in range(6):
            better = False
            for e in sibs:
                for c in width:
                    if c == col[e]:
                        continue
                    k, other = (grp(e), row[e], col[e]), cells.get((grp(e), row[e], c))
                    col[e], was = c, col[e]
                    if other:
                        col[other] = was
                    now = cost() if legal() else None
                    if now is not None and now < best:
                        best, better = now, True
                        del cells[k]
                        cells[grp(e), row[e], c] = e
                        if other:
                            cells[k] = other
                    else:
                        col[e] = was
                        if other:
                            col[other] = c
            if not better:
                break

    size, offset = {}, {}  # offset: position of a box in its container's content area

    def tracks(items, col, row, grp):  # column widths (by column) and row heights (by group, row)
        cw, rh = {}, {}
        for k in items:
            cw[col[k]] = max(cw.get(col[k], 0), size[k][0])
            rh[grp(k), row[k]] = max(rh.get((grp(k), row[k]), 0), size[k][1])
        return dict(sorted(cw.items())), rh

    def measure(e):
        kids = children.get(e, [])
        if not kids:
            size[e] = (LEAF_W, LEAF_H)
            return
        for k in kids:
            measure(k)
        col, row = grid(kids, lambda _: 0)
        cw, rh = tracks(kids, col, row, lambda _: 0)
        cx, ry = starts(cw, GAP_X), starts(dict(sorted(rh.items())), GAP_Y)
        for k in kids:
            offset[k] = (cx[col[k]] + (cw[col[k]] - size[k][0]) // 2, ry[0, row[k]])
        size[e] = (max(LEAF_W, sum(cw.values()) + GAP_X * (len(cw) - 1) + 2 * PAD),
                   sum(rh.values()) + GAP_Y * (len(rh) - 1) + 2 * PAD + HEAD)

    for e in roots:
        measure(e)
    col, row = grid(roots, group.get)
    cw, rh = tracks(roots, col, row, group.get)
    cx = {c: x + MARGIN + PAD for c, x in starts(cw, GAP_X).items()}
    width = sum(cw.values()) + GAP_X * (len(cw) - 1) + 2 * PAD

    cells, pos = [], {}
    rows = []  # (group, row, top, bottom, group top, group bottom), top to bottom
    y = MARGIN
    for g in order:
        framed = g in BANDS
        keys = sorted(r for gg, r in rh if gg == g)
        top = y + (HEAD + PAD if framed else 0)
        ry = starts({r: rh[g, r] for r in keys}, GAP_Y)
        bottom = top + sum(rh[g, r] for r in keys) + GAP_Y * (len(keys) - 1) + (PAD if framed else 0)
        rows += [(g, r, top + ry[r], top + ry[r] + rh[g, r], y, bottom) for r in keys]
        if framed:
            fid, label, stroke, fill = frame_table[g]
            cells.append(vertex(fid, label, MARGIN, y, width, bottom - y,
                                "rounded=0;whiteSpace=wrap;html=1;verticalAlign=top;align=left;spacingLeft=8;"
                                f"fontStyle=1;fontColor=#666666;fillColor={fill};strokeColor={stroke};strokeWidth=2;"))
        for e in roots:
            if group[e] == g:
                pos[e] = (cx[col[e]] + (cw[col[e]] - size[e][0]) // 2, top + ry[row[e]])
        y = bottom + FRAME_GAP

    def place(e):
        for k in children.get(e, []):
            pos[k] = (pos[e][0] + PAD + offset[k][0], pos[e][1] + HEAD + PAD + offset[k][1])
            place(k)
    for e in roots:
        place(e)

    for e in sorted(elements, key=lambda e: len(anc(e))):  # containers first, contents on top
        etype, name = m["elements"][e]
        fill, stroke, dashed = colors[band.get(e, "other")]
        extra = "verticalAlign=top;" if children.get(e) else ""
        cells.append(vertex(e, f"{html.escape(name)}<br><i>{etype}</i>", *pos[e], *size[e],
                            f"rounded=1;whiteSpace=wrap;html=1;{extra}fillColor={fill};strokeColor={stroke};dashed={dashed};"))
    rix = {e: next(i for i, r in enumerate(rows) if r[:2] == (group[e], row[e])) for e in roots}
    cells += route(edges, m, pos, size, lambda e: anc(e)[-1], rows, rix, col, cx, cw)
    return ('<mxfile host="preview"><diagram name="preview"><mxGraphModel><root>'
            '<mxCell id="0"/><mxCell id="1" parent="0"/>\n' + "\n".join(cells)
            + '\n</root></mxGraphModel></diagram></mxfile>\n')


def route(edges, m, pos, size, root, rows, rix, col, cx, cw) -> list:
    """Edge cells: sides, spread ports, waypoints through the gaps between rows and columns. Edges
    sharing a gap run on parallel tracks spread over the gap."""
    def centre(e):
        return pos[e][0] + size[e][0] / 2, pos[e][1] + size[e][1] / 2

    def gap_below(i, inside=False):
        """(lo, hi, key) of the empty strip under row i: to the next row of its group, else (inside:
        to its frame's bottom edge) to the next group."""
        g, _, _, bottom, _, gbottom = rows[i]
        if i + 1 < len(rows) and rows[i + 1][0] == g:
            return bottom, rows[i + 1][2], ("h", i)
        if inside:
            return bottom, max(gbottom, bottom + PAD), ("in", i)
        nxt = next((r[4] for r in rows[i + 1:] if r[0] != g), gbottom + FRAME_GAP)
        return gbottom, nxt, ("between", g)

    def gap_above(i):
        g, _, _, _, gtop, _ = rows[i]
        if i > 0 and rows[i - 1][0] == g:
            return gap_below(i - 1)
        prev = next((r for r in reversed(rows[:i]) if r[0] != g), None)
        return (prev[5] if prev else gtop - FRAME_GAP), gtop, ("between", prev[0] if prev else "top")

    present = sorted(cw)

    def col_gap(c, left):  # the empty strip left or right of column c
        i = present.index(c)
        if left:
            return cx[c] - GAP_X, cx[c], ("v", i)
        return cx[c] + cw[c], cx[c] + cw[c] + GAP_X, ("v", i + 1)

    occupied = {(rix[e], col[e]) for e in rix}

    plan = []  # (rid, type, source, target, (exit side, entry side) or None, legs)
    for rid, rtype, s, t in edges:
        S, T = root(s), root(t)
        if S == T:  # within one container: left to draw.io
            plan.append((rid, rtype, s, t, None, []))
            continue
        rs, rt = rix[S], rix[T]
        if rs == rt:
            if abs(col[S] - col[T]) > 1:  # under the boxes in between
                plan.append((rid, rtype, s, t, ("bottom", "bottom"), [("y", gap_below(rs, inside=True))]))
            else:
                plan.append((rid, rtype, s, t, ("right", "left") if col[S] < col[T] else ("left", "right"), []))
            continue
        down = rs < rt
        gs = gap_below(rs) if down else gap_above(rs)
        gt = gap_above(rt) if down else gap_below(rt)
        between = range(min(rs, rt) + 1, max(rs, rt))

        def clear(c):
            return not any((i, c) in occupied for i in between)
        if gs[2] == gt[2] or clear(col[T]):  # across in the source's gap, then straight to the target
            legs = [("y", gs)]
        elif clear(col[S]):  # straight from the source, across in the target's gap
            legs = [("y", gt)]
        else:  # along a column gap next to the target's column, on the source's side
            legs = [("y", gs), ("x", col_gap(col[T], col[S] <= col[T])), ("y", gt)]
        plan.append((rid, rtype, s, t, ("bottom", "top") if down else ("top", "bottom"), legs))

    ports = {}  # (box, side) -> [(position of the other end along the side, rid, end)]
    for rid, _, s, t, sides, _ in plan:
        if sides:
            for e, other, side, end in ((s, t, sides[0], "exit"), (t, s, sides[1], "entry")):
                ox, oy = centre(other)
                ports.setdefault((e, side), []).append((oy if side in ("left", "right") else ox, rid, end))
    frac = {}
    for (e, side), lst in ports.items():
        for i, (_, rid, end) in enumerate(sorted(lst)):
            frac[rid, end] = (side, (i + 1) / (len(lst) + 1))

    users = {}  # gap key -> edges running in it
    for rid, *_, legs in plan:
        for _, (_, _, key) in legs:
            users.setdefault(key, []).append(rid)

    def track(rid, gap):  # the edge's line in the gap: evenly spaced, centred, at most TRACK apart
        lo, hi, key = gap
        n, k = len(users[key]), users[key].index(rid)
        return (lo + hi) / 2 + (k - (n - 1) / 2) * min(TRACK, (hi - lo) / (n + 1))

    def point(e, side, f):
        x, y = pos[e]
        w, h = size[e]
        rel = {"top": (f, 0), "bottom": (f, 1), "left": (0, f), "right": (1, f)}[side]
        return rel, (x + rel[0] * w, y + rel[1] * h)

    cells = []
    for rid, rtype, s, t, sides, legs in plan:
        if rtype == "Access":
            note = ACCESS[(m["access"].get(rid) or ["write"])[0]] + "dashed=1;dashPattern=1 4;"
        elif rtype == "Association":
            note = "endArrow=openAsync;" if rid in m["directed"] else "endArrow=none;"
        else:
            note = NOTATION.get(rtype, "")
        label = (m["spec"].get(rid) or [rtype])[0]
        if not sides:
            cells.append(edge_cell(rid, label, "edgeStyle=orthogonalEdgeStyle;rounded=0;" + note, s, t, []))
            continue
        (ex, ey), (sx, sy) = point(s, *frac[rid, "exit"])
        (nx, ny), (tx, ty) = point(t, *frac[rid, "entry"])
        pts, x = [], sx
        if sides[0] in ("left", "right") and abs(sy - ty) > 1:  # side by side: elbow in the gap between
            pts = [((sx + tx) / 2, sy), ((sx + tx) / 2, ty)]
        for i, (axis, gap) in enumerate(legs):
            if axis == "y":  # horizontal run; an "x" leg is the vertical run between two of them
                v = track(rid, gap)
                nxt = tx if i == len(legs) - 1 else track(rid, legs[i + 1][1])
                pts += [(x, v), (nxt, v)]
                x = nxt
        style = (f"rounded=0;exitX={ex:.3f};exitY={ey};entryX={nx:.3f};entryY={ny};"
                 f"exitPerimeter=0;entryPerimeter=0;{note}")
        cells.append(edge_cell(rid, label, style, s, t, pts))
    return cells


def edge_cell(rid, label, style, s, t, pts) -> str:
    arr = ('<Array as="points">' + "".join(f'<mxPoint x="{x:.0f}" y="{y:.0f}"/>' for x, y in pts) + "</Array>"
           if pts else "")
    return (f'<mxCell id="{rid}" value="{html.escape(label)}" style="html=1;fontSize=10;labelBackgroundColor=#ffffff;'
            f'{style}" edge="1" parent="1" source="{s}" target="{t}"><mxGeometry relative="1" as="geometry">{arr}'
            f'</mxGeometry></mxCell>')


def vertex(i, label, x, y, w, h, style) -> str:
    return (f'<mxCell id="{i}" value="{html.escape(label)}" style="{style}" vertex="1" parent="1">'
            f'<mxGeometry x="{x:.0f}" y="{y:.0f}" width="{w}" height="{h}" as="geometry"/></mxCell>')


def crossings(xml: str) -> tuple[int, float]:
    """Crossings of the edges of a preview diagram (as routed, between their ports and waypoints),
    and their total length."""
    root = ET.fromstring(xml)
    box = {c.get("id"): [float(c.find("mxGeometry").get(k)) for k in ("x", "y", "width", "height")]
           for c in root.iter("mxCell") if c.get("vertex")}
    lines = []
    for c in root.iter("mxCell"):
        if c.get("edge"):
            st = dict(kv.split("=", 1) for kv in c.get("style").split(";") if "=" in kv)
            ends = []
            for b, kx, ky in ((box[c.get("source")], "exitX", "exitY"), (box[c.get("target")], "entryX", "entryY")):
                fx, fy = float(st.get(kx, 0.5)), float(st.get(ky, 0.5))
                ends.append((b[0] + fx * b[2], b[1] + fy * b[3]))
            pts = [(float(q.get("x")), float(q.get("y"))) for q in c.iter("mxPoint")]
            lines.append([ends[0], *pts, ends[1]])
    segs = [(i, l[k], l[k + 1]) for i, l in enumerate(lines) for k in range(len(l) - 1)]

    def o(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    n = sum(i != j and o(c, d, a) * o(c, d, b) < 0 and o(a, b, c) * o(a, b, d) < 0
            for k, (i, a, b) in enumerate(segs) for j, c, d in segs[k + 1:])
    return n, sum(abs(b[0] - a[0]) + abs(b[1] - a[1]) for _, a, b in segs)


def best(run: Path) -> str:
    """The preview with the fewest crossings (then the shortest edges) of all STRATEGIES."""
    return min((preview(run, s) for s in STRATEGIES), key=crossings)


def write(run: Path) -> Path:
    """Write RUN/2_preview.drawio and return its path."""
    out = run / OUTPUT
    out.write_text(best(run), encoding="utf-8")
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print(write(Path(sys.argv[1])))
