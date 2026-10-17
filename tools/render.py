"""Render a Boox notebook to PDF: python3 render.py in.note out.pdf"""
import sys
import cairo
from booxnote import Note

SCALE = 72 / 300  # Boox pixels -> PDF points
MAX_PRESSURE = 4095


def draw_template(ctx, note):
    (vx, vy, vw, vh), rects = note.template
    ctx.save()
    ctx.scale(note.width / vw, note.height / vh)
    ctx.translate(-vx, -vy)
    ctx.set_source_rgb(.8, .8, .8)
    for x, y, w, h in rects:
        ctx.rectangle(x, y, w, h)
    ctx.fill()
    ctx.restore()


def draw_stroke(ctx, st):
    pts = st['points']
    if not pts:
        return
    a = st['color']
    ctx.set_source_rgb(((a >> 16) & 255) / 255, ((a >> 8) & 255) / 255, (a & 255) / 255)
    w = st['width']
    if len(pts) == 1:
        x, y, _ = pts[0]
        ctx.arc(x, y, w / 2, 0, 6.2832)
        ctx.fill()
        return
    for (x0, y0, p0), (x1, y1, p1) in zip(pts, pts[1:]):
        ctx.set_line_width(w * (0.35 + 0.65 * (p0 + p1) / 2 / MAX_PRESSURE))
        ctx.move_to(x0, y0)
        ctx.line_to(x1, y1)
        ctx.stroke()


def render(src, dst):
    note = Note(src)
    surf = cairo.PDFSurface(dst, note.width * SCALE, note.height * SCALE)
    surf.set_metadata(cairo.PDF_METADATA_TITLE, note.title)
    ctx = cairo.Context(surf)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    for strokes in note.pages:
        ctx.save()
        ctx.scale(SCALE, SCALE)
        if note.template:
            draw_template(ctx, note)
        for st in strokes:
            draw_stroke(ctx, st)
        ctx.restore()
        ctx.show_page()
    surf.finish()
    return note


if __name__ == '__main__':
    render(sys.argv[1], sys.argv[2])
