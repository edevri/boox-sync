import sys, struct
def varint(b, i):
    r = s = 0
    while True:
        c = b[i]; i += 1; r |= (c & 0x7f) << s; s += 7
        if c < 0x80: return r, i
def parse(b):
    i, out = 0, []
    while i < len(b):
        k, i = varint(b, i); f, t = k >> 3, k & 7
        if t == 0: v, i = varint(b, i)
        elif t == 1: v = struct.unpack('<d', b[i:i+8])[0]; i += 8
        elif t == 5: v = struct.unpack('<f', b[i:i+4])[0]; i += 4
        elif t == 2:
            n, i = varint(b, i); v = b[i:i+n]; i += n
        else: raise ValueError(t)
        out.append((f, t, v))
    return out
def show(b, ind=0, maxs=200):
    for f, t, v in parse(b):
        if t == 2:
            try:
                sub = parse(v)
                if sub and all(x[0] > 0 for x in sub) and not all(32 <= c < 127 for c in v):
                    print(' '*ind + f'{f}: {{'); show(v, ind+2, maxs); print(' '*ind + '}'); continue
            except Exception: pass
            s = v.decode('utf8', 'replace')
            print(' '*ind + f'{f}: {s[:maxs]!r}' + (f' ...({len(v)})' if len(v) > maxs else ''))
        else: print(' '*ind + f'{f}: {v}')
if __name__ == '__main__':
    show(open(sys.argv[1], 'rb').read(), maxs=int(sys.argv[2]) if len(sys.argv) > 2 else 200)
