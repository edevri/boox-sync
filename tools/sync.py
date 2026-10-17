"""Mirror Boox notebooks from a cloud folder, render changed ones to PDF, upload the PDFs.

    python3 sync.py --src gdrive:Boox/Notes --dst "gdrive:Boox/PDF"

1. rclone sync SRC -> CACHE/notes   (only changed files are downloaded)
2. render every notebook whose content hash changed since the last run -> CACHE/pdf,
   with the PDF's modified time set to when the last pen stroke was drawn, on the date in
   the notebook's name, so Drive sorts them chronologically. The time comes from the
   notebook itself, so the state file is only a cache: losing it costs one full re-render
3. rclone sync CACHE/pdf -> DST     (only changed PDFs are uploaded)

DST is mirrored: PDFs of deleted notebooks are removed there too, so give it its own folder.
SRC/DST can be any rclone remote path, or a local directory (handy for testing).
"""
import argparse, datetime, fcntl, hashlib, json, logging, os, re, subprocess, sys

from booxnote import Note
from render import render

log = logging.getLogger('boox-sync')


def rclone(*args):
    log.info('rclone %s', ' '.join(args))
    subprocess.run(['rclone', *args], check=True)


def find_notebooks(root):
    """Yield (relpath, path) for each .note file or unpacked notebook folder under root."""
    for d, dirs, files in os.walk(root):
        if os.path.isfile(os.path.join(d, 'note', 'pb', 'note_info')):
            dirs.clear()  # an unpacked notebook; don't descend into it
            yield os.path.relpath(d, root), d
            continue
        for f in files:
            if f.endswith('.note'):
                p = os.path.join(d, f)
                yield os.path.relpath(p, root), p


def fingerprint(path):
    h = hashlib.sha256()
    if os.path.isdir(path):
        for d, dirs, files in sorted(os.walk(path)):
            dirs.sort()
            for f in sorted(files):
                p = os.path.join(d, f)
                h.update(os.path.relpath(p, path).encode() + b'\0')
                with open(p, 'rb') as fh:
                    h.update(hashlib.sha256(fh.read()).digest())
    else:
        with open(path, 'rb') as fh:
            h.update(fh.read())
    return h.hexdigest()


def note_time(name, last_stroke_ms):
    """Timestamp for sorting: the YYYYMMDD / YYYY-MM-DD date in the name (so the note stays on
    the day it belongs to, even if edited later) at the time of day of the last pen stroke;
    without a date in the name, the time of the last pen stroke."""
    last = datetime.datetime.fromtimestamp(last_stroke_ms / 1000)
    m = re.search(r'(?<!\d)(20\d\d)-?(\d\d)-?(\d\d)(?!\d)', name)
    if m:
        try:
            return datetime.datetime.combine(
                datetime.date(*map(int, m.groups())), last.time()).timestamp()
        except ValueError:
            pass  # not a real date
    return last.timestamp()


def pdf_name(rel, path):
    if rel.endswith('.note'):
        return rel[:-len('.note')] + '.pdf'
    # unpacked folders are named by id; use the notebook title instead
    title = Note(path).title or os.path.basename(rel)
    safe = ''.join(c if c not in '/\\:*?"<>|' else '_' for c in title)
    return os.path.join(os.path.dirname(rel), safe + '.pdf')


def convert(notes_dir, pdf_dir, state, force=False):
    """Render new/changed notebooks, delete PDFs of removed ones. Returns number of failures."""
    seen, failures = set(), 0
    for rel, path in find_notebooks(notes_dir):
        seen.add(rel)
        fp = fingerprint(path)
        prev = state.get(rel)
        if (not force and prev and prev['fp'] == fp
                and os.path.exists(os.path.join(pdf_dir, prev['pdf']))):
            continue
        try:
            pdf = pdf_name(rel, path)
            out = os.path.join(pdf_dir, pdf)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            note = render(path, out + '.tmp')
            mtime = note_time(os.path.basename(pdf), note.last_stroke_ms)
            os.utime(out + '.tmp', (mtime, mtime))
            os.replace(out + '.tmp', out)
        except Exception:
            log.exception('failed to render %s', rel)
            failures += 1
            continue
        if prev and prev['pdf'] != pdf:
            remove_pdf(pdf_dir, prev['pdf'])
        state[rel] = {'fp': fp, 'pdf': pdf}
        log.info('rendered %s -> %s', rel, pdf)
    for rel in set(state) - seen:
        remove_pdf(pdf_dir, state.pop(rel)['pdf'])
        log.info('removed %s', rel)
    return failures


def remove_pdf(pdf_dir, pdf):
    try:
        os.remove(os.path.join(pdf_dir, pdf))
    except FileNotFoundError:
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--src', required=True, help='rclone path of the Boox notebooks, e.g. gdrive:Boox/Notes')
    ap.add_argument('--dst', required=True, help='rclone path for the PDFs (mirrored, use a dedicated folder)')
    ap.add_argument('--cache', default=os.path.expanduser('~/.cache/boox-sync'))
    ap.add_argument('--force', action='store_true', help='re-render everything')
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')

    notes_dir, pdf_dir = os.path.join(args.cache, 'notes'), os.path.join(args.cache, 'pdf')
    state_file = os.path.join(args.cache, 'state.json')
    os.makedirs(pdf_dir, exist_ok=True)

    lock = open(os.path.join(args.cache, 'lock'), 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log.info('another run is in progress, skipping')
        return 0

    state = json.load(open(state_file)) if os.path.exists(state_file) else {}
    rclone('sync', '--exclude', '*.pdf', args.src, notes_dir)  # skip PDFs the Boox exported itself
    failures = convert(notes_dir, pdf_dir, state, args.force)
    with open(state_file + '.tmp', 'w') as fh:
        json.dump(state, fh, indent=1)
    os.replace(state_file + '.tmp', state_file)
    rclone('sync', '--checksum', '--exclude', '*.tmp', pdf_dir, args.dst)  # PDF mtimes are note times, not upload times; compare content
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
