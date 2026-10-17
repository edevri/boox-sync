"""Reader for Onyx Boox .note notebooks.

A notebook is a tree (zipped as a .note file, or unpacked as a folder) of:
  note/pb/note_info          protobuf: title, page order (field 20, JSON), page width (22)
  shape/<page>#<id>#<ts>.zip  zip of protobuf: one message per stroke (field 1)
  point/<page>/<page>#<id>#points
                             binary, big-endian: stroke point blocks + index at the end
  note/templateRes/*.svg     page background (lined paper etc.)
"""
import io, json, os, re, struct, zipfile
from pbdump import parse

PAGE_HEIGHT = 2480.0


def fields(msg):
    d = {}
    for f, t, v in parse(msg):
        d.setdefault(f, []).append(v)
    return d


def s(v):
    return v.decode('utf8') if isinstance(v, bytes) else v


class Tree:
    """Uniform read access to a .note zip or an unpacked notebook folder."""

    def __init__(self, path):
        if os.path.isdir(path):
            self.files = {os.path.relpath(os.path.join(d, f), path).replace(os.sep, '/'): os.path.join(d, f)
                          for d, _, fs in os.walk(path) for f in fs}
            self._read = lambda n: open(self.files[n], 'rb').read()
        else:
            z = zipfile.ZipFile(path)
            self.files = {n: n for n in z.namelist() if not n.endswith('/')}
            self._read = z.read
        info = [n for n in self.files if n.endswith('note/pb/note_info')]
        if not info:
            raise ValueError(f'{path}: no note/pb/note_info, not a Boox notebook')
        self.root = info[0][:-len('note/pb/note_info')]

    def names(self, prefix):
        return [n[len(self.root):] for n in self.files if n.startswith(self.root + prefix)]

    def read(self, name):
        return self._read(self.root + name)


def read_points(data):
    """Return {stroke_id: [(x, y, pressure), ...]} from a #points file."""
    (index_off,) = struct.unpack('>I', data[-4:])
    out, i = {}, index_off
    while i < len(data) - 4:
        sid = data[i:i+36].decode()
        off, length = struct.unpack('>II', data[i+36:i+44])
        i += 44
        out[sid] = [(x, y, p) for x, y, _tilt, p, _t
                    in struct.iter_unpack('>ffHHI', data[off+4:off+length])]
    return out


def read_template(tree):
    """Rect-only SVG templates (lined/grid paper) -> ((vx, vy, vw, vh), [(x, y, w, h)])."""
    svgs = [n for n in tree.names('note/templateRes/') if n.endswith('.svg')]
    if not svgs:
        return None
    svg = tree.read(svgs[0]).decode('utf8', 'replace')
    vb = re.search(r'viewBox="([^"]+)"', svg)
    if not vb:
        return None
    rects = [tuple(map(float, r)) for r in re.findall(
        r'<rect x="([\d.]+)" y="([\d.]+)"[^>]*width="([\d.]+)" height="([\d.]+)"', svg)]
    return tuple(map(float, vb.group(1).split())), rects


class Note:
    def __init__(self, path):
        tree = Tree(path)
        info = fields(fields(tree.read('note/pb/note_info'))[1][0])
        self.title = s(info.get(6, [b''])[0])
        self.created_ms = info.get(2, [0])[0]
        self.page_ids = json.loads(s(info[20][0]))['pageNameList']
        self.width = info.get(22, [1860.0])[0]
        self.height = PAGE_HEIGHT
        self.template = read_template(tree)

        points = {}
        for n in tree.names('point/'):
            if n.endswith('#points'):
                points.update(read_points(tree.read(n)))
        shapes = {}
        for n in tree.names('shape/'):
            if n.endswith('.zip'):
                page = n.split('/')[-1].split('#')[0]
                inner = zipfile.ZipFile(io.BytesIO(tree.read(n)))
                for m in inner.namelist():
                    for raw in fields(inner.read(m)).get(1, []):
                        shapes.setdefault(page, []).append(fields(raw))

        self.pages = []
        for pid in self.page_ids:
            strokes = []
            for sh in sorted(shapes.get(pid, []), key=lambda f: f.get(2, [0])[0]):
                sid = s(sh[1][0])
                strokes.append(dict(
                    id=sid,
                    color=sh.get(4, [0xFF000000])[0] & 0xFFFFFFFF,
                    width=sh.get(5, [3.0])[0],
                    pen=sh.get(12, [0])[0],
                    points=points.get(sid, [])))
            self.pages.append(strokes)
