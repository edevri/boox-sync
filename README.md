# boox-sync

Turns the native Boox notebooks that the Notes app syncs to Google Drive into PDFs, also on Google Drive.
Runs every minute; only notebooks whose content changed since the last run are re-rendered.
Each PDF's modified time is set to the date in the notebook's name (`20261015 Person` -> 2026-10-15),
so sorting the Drive folder by "Last modified" puts them in chronological order.
Notebooks without a date in their name use their creation time.

```
Boox Notes --(native sync)--> Drive: BOOX_SRC/*.note
                                  | rclone sync (changed files only)
                                  v
                     ~/.cache/boox-sync/notes --render changed--> ~/.cache/boox-sync/pdf
                                                                      | rclone sync
                                                                      v
                                                             Drive: BOOX_DST/*.pdf
```

`BOOX_DST` is a mirror: PDFs of notebooks you delete are removed there too. Give it its own folder.

## Setup

0. On the Boox, make the Notes app sync notebooks to Google Drive in the native `.note` format.
   In the Notes app, tap the menu icon (three horizontal lines, top right) → **Notes settings**:
   - **Export as**: `.note file (BOOX Note format)`
   - **Third-Party Account Management**: set up Google Drive sync

   (Tested on a Boox Note Air 5C; menu names may differ on other models and firmware versions.)
   Check that `.note` files appear in the Drive folder, and note that folder's URL for step 2.
1. Install rclone and connect it to Google Drive (name the remote `gdrive`):
   ```sh
   sudo apt install rclone
   rclone config create gdrive drive scope=drive   # opens a browser to sign in
   ```
   Full `drive` scope is needed: the narrower scopes can't see files the Boox uploaded.
2. Configure source and destination:
   ```sh
   cp boox-sync.env.sample boox-sync.env
   ```
   Set `BOOX_SRC` to the folder ID from the Drive URL of the Boox's sync folder
   (`https://drive.google.com/drive/u/0/folders/<ID>`), and create the PDF folder:
   `rclone mkdir "gdrive:Boox PDF"`. Check the source with `rclone lsf "<BOOX_SRC>"`.
   `boox-sync.env` is gitignored; only the sample is committed.
3. `./install.sh` copies the tools to `~/.local/share/boox-sync/`, `boox-sync.env` to
   `~/.config/boox-sync.env`, and enables the systemd user timer.
   Re-run it after any change to the code or `boox-sync.env`.
4. Watch it: `journalctl --user -u boox-sync -f`. Run once now: `systemctl --user start boox-sync`.

Force re-rendering everything (e.g. after updating the renderer):
`(. ./boox-sync.env && python3 tools/sync.py --src "$BOOX_SRC" --dst "$BOOX_DST" --force)`

## Files

- `tools/booxnote.py` reads the `.note` format (zip or unpacked folder); format notes in its docstring.
- `tools/render.py` renders a notebook to PDF with pycairo: `python3 tools/render.py in.note out.pdf`.
- `tools/sync.py` does the download / change detection / upload loop.
- `tools/pbdump.py` dumps raw protobuf; handy when the format changes: `python3 tools/pbdump.py file`.

## Limitations

Handles pen strokes (pressure-sensitive width, color), page order, and line/grid page templates.
Not yet: brush/marker/pencil pen styles, partially erased strokes, text boxes, inserted images,
geometric shapes, notes on top of imported PDFs.
