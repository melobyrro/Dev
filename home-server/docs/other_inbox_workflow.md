# Other-Inbox → Other Workflow

1. **Hardlink sweep** (`/home/byrro/scripts/hardlink_other_sweep.sh` via cron every 5 min) mirrors `/mnt/ByrroServer/ByrroMedia/downloads/{prowlarr,other}` into `/mnt/ByrroServer/ByrroMedia/Other_Inbox`. It never moves files out of the inbox—`filebot_other.sh` owns that work.
2. **Filebot run** (`/home/byrro/scripts/filebot_other.sh`, every 15 min, also triggered via `input_button.filebot_other_run`) runs the RedNoah `fn:amc` script against `/media/Other_Inbox`. Success moves recognized media into `/mnt/ByrroServer/ByrroMedia/Other`. Items that are intentionally skipped are listed in `/mnt/ByrroServer/docker-data/filebot/amc.txt`.
3. **New fallback**: `filebot_other.sh` now calls `/home/byrro/scripts/filebot_other_fallback.sh` whenever Filebot exits non‑zero or leftovers remain in the inbox. The fallback hardlinks every remaining file/directory from `/mnt/ByrroServer/ByrroMedia/Other_Inbox` into `/mnt/ByrroServer/ByrroMedia/Other`, so Plex always sees the release even if Filebot skipped or failed to process it.

## Verification

- Watch `/mnt/ByrroServer/docker-data/homeassistant/config/filebot_other_status.json` (HA dashboard card or curl) for new fields:
  - `fallback_recent_log` shows the most recent fallback actions in table form.
  - `fallback_log_raw` contains the tail of `/home/byrro/logs/filebot_other_fallback.log`.
  - `fallback_used_recently` flips to `true` when the fallback helper has run this cycle.
- The fallback writes `/home/byrro/logs/filebot_other_fallback.log`, which also surfaces via the status automation (`filebot_other_status.py`).
- Remove entries from `/mnt/ByrroServer/docker-data/filebot/amc.txt` when you decide Filebot should own a release again.

With the fallback in place, every file that remains in `Other_Inbox` is guaranteed to appear, via hardlink, in `/mnt/ByrroServer/ByrroMedia/Other`, keeping Plex streaming-ready even while the automated match/rename logic is still improving.
