# Touchline · A little fair play

A local football judging prototype with a hand-drawn English/Arabic web interface.
No account, Gemini key, Node.js, or database is needed. Nothing is sent to a cloud AI service.

**Start with “Just looking? Try a sample” if you have no footage.** The sample is invented,
unsigned, and visibly labelled. It tests the interface, not AI football accuracy.

## 1. Start the app

Install **Python 3.11 or 3.12 (64-bit)** from https://www.python.org/downloads/.
Newer versions are not supported by the pinned ML packages. Unzip the project and open
Terminal / PowerShell in its folder.

```sh
python -m venv .venv
```

Activate it:

```sh
# macOS / Linux
source .venv/bin/activate
```

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, skip activation and use `.venv\Scripts\python.exe`
in place of `python` in the following commands; no security-policy change is necessary.

```sh
python -m pip install -r requirements.txt
python -m football.cli serve
```

Open **http://127.0.0.1:8777**. Press Ctrl+C in the terminal to stop.
To use a different port: `python -m football.cli serve --port 8778`.

## 2. Enable real video analysis (optional)

Stop the server, then run these commands in the activated environment:

```sh
python -m pip install -r requirements-judge.txt
python -m football.cli download-model
python -m football.cli serve
```

The first installation downloads several hundred MB of CPU ML dependencies and the official
pretrained YOLO26n weights. This needs internet and may take several minutes. No GPU is
required. After installation, video processing is local and does not need internet.
The provided CPU-wheel pins target Windows/Linux x86-64. On Apple Silicon, use the same
listed versions of torch and torchvision **without `+cpu`**, remove the extra index line,
and install the modified judge requirements. Native macOS wheels run on CPU here too.

On minimal Linux systems, OpenCV may report a missing `libGL.so.1`. Install your distribution's
OpenGL runtime (for example `libgl1` on Ubuntu), then retry. No display window is opened.

## 3. Judge a clip

1. Name both teams and enter 1–11 players per team, one name per line.
2. Upload MP4 or WebM: **up to 120 seconds, 100 MB, 4K / 120 fps**. 720p/1080p is preferable.
   The browser must also support its codec; use H.264 MP4 or VP8/VP9 WebM when playback fails.
3. If the clip has no visible goals, choose **No goals visible? Possession only** on the
   calibration screen. This estimates possession and explicitly leaves goals unassessed.
   Otherwise mark **three points for each goal**: first endpoint, second endpoint, then
   a point behind the boundary. “Goal for Team A” means that crossing awards **A** a point.
   Use the scrubber to find a clear frame. Keyboard alternative: focus the overlay, arrow keys
   move a cursor, Shift+arrow moves faster, Enter places a point, Escape undoes it.
4. Click **Find the players & ball**. Wait for CPU detection; speed depends on your hardware.
5. Inspect track thumbnails and scrub the annotated clip. Assign known tracks to players.
   A player can have multiple non-overlapping tracks. Simultaneous tracks cannot share an identity.
6. Click **Judge this match**. The app signs and verifies the report and automatically replaces
   the match's score. View goal timestamps, possession, unknown time, and MVP. Download the report.
7. **Adjust & re-score** corrects markings/mappings and replaces the result. Identical or
   already-imported reports are rejected, so goals are not added twice.

Audio is retained in the original upload but is not analyzed for football. No speech transcript
is generated. Team assignments are manual; shirt colours/numbers are not automatically read.

## No footage yet?

You can use the entire sample results screen now. Real uploads, calibration, tracking, and
report verification are implemented, but **football accuracy has not been validated against manually labelled footage**.
We do not include someone else's gameplay, a fake detection demo, or a trained football-specific model.

This baseline needs a **stationary camera** and visible ball/goal boundaries. Moving-camera
footage is outside its supported scope. Markings do not follow camera motion. A broadcast highlight
or partially visible pitch may be unsuitable. A bad angle can look like a goal in 2D while the ball
actually misses the physical goal.

## Separate Python judge / report import

After detection and track assignment, choose **Export Python judge config**. It contains the
current match ID, team roster, normalized goal geometry, and track mappings. Keep it unchanged
when using the same clip. Run the standalone judge:

```sh
python -m football.cli judge --video /path/to/clip.mp4 --config touchline-judge-config.json --output signed-report.json
```

Then expand **Have a report from the Python judge?** and import `signed-report.json` into the
same match. The current match is remembered in this browser. Re-running identical inference
and scoring normally produces the same report ID; an already-applied report is rejected.

Both judge and server must share their signing secret. On the same installation they use
`.runtime/signing.key` automatically. On different computers, privately copy that file into the
other installation's `.runtime` folder before starting it, or set the same
`FOOTBALL_SIGNING_SECRET` environment variable on both. Restart the server after changing it.
Never include the key in a shared source archive. A bare public hash is **not** used as proof
of origin: reports use HMAC-SHA256 over canonical JSON.

An imported report without linked local media can update the score but has no local playback.
Keep the original clip with the report. Refreshing the page retains the match and its last
verified report. Jobs, media links, calibration drafts, and track mappings must be rebuilt after
refresh/restart; uploaded files remain on disk until you remove them with the server stopped.

## Local data and packaging

`.runtime/` contains originals (with audio), thumbnails, model settings/weights, signing key,
and applied report history. It is private, ignored, and excluded from the source ZIP.
The server binds only to `127.0.0.1`; this prototype has no multi-user authentication.
Do not expose it to the internet. Start a fresh match to reset the UI; historical reports
remain in `.runtime/applied.json`. To remove all local history/uploads, stop the server and
remove `.runtime/` (this also removes weights and changes the signing key).

Create a clean downloadable source package:

```sh
python tools/package.py
```

Share `dist/touchline-source.zip`, **not** the working folder or `.runtime`.

## How the judge works

- **Detection:** YOLO26n person/sports-ball classes, ByteTrack IDs, CPU, up to about 15 samples/s.
- **Possession:** nearest feet within a height-scaled image-distance threshold, stable for
  0.2 s. Close competing players, missing detections, unassigned tracks, and long time gaps
  remain unknown. This is a proxy for possession, not a physical contact model.
- **Candidate goals:** a visible ball centre moves across a calibrated boundary segment toward
  the marked inside point. No crossings are bridged over missing-ball frames or gaps >0.3 s.
  Counting rearms only after the ball is back outside for 0.5 s and a 2 s cooldown has elapsed.
- **Results:** team possession sums named players. Equal maximum player times share MVP;
  zero attributed possession means insufficient evidence. Unknown time is always displayed.
- **Identity:** occlusion and re-entry may change IDs; the host must verify mappings. The app
  does not silently claim that two track IDs belong to one person.

Video timing uses reported frame rate; variable-frame-rate footage may have approximate event times.

The model/rules interface is frame observations → scoring results → signed report. Football
rules live separately in `football/rules.py`. Future speech games can add their own processors
and rule modules while keeping the host flow and report-verification design.

## API (local only)

Interactive schema: http://127.0.0.1:8777/api/docs

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health`, `GET /api/sample` | Installation readiness; illustrative preview |
| `POST /api/videos` | Multipart `video` upload; returns ID, media URL, dimensions, duration |
| `POST /api/jobs` | JSON `{match, video_id}`; queues detection |
| `GET /api/jobs/{id}` | Status/progress/failure message |
| `GET /api/jobs/{id}/tracks` | Timestamped observations, thumbnails, track IDs |
| `POST /api/jobs/{id}/score` | JSON `{calibration, mappings}`; signs/verifies/applies result |
| `GET /api/jobs/{id}/result` | Signed envelope `{payload, signature}` |
| `POST /api/reports/import` | JSON `{match_id, report}`; verifies and replaces current result |
| `GET /api/matches/{id}/result` | Last applied signed envelope, including after restart |

Only one video detection job runs at a time. No database or job queue service is needed.
The report includes `schema_version: 1`, game, report ID, match/players, video SHA-256 and
metadata, calibration, mappings, model details, rule version, events, possession, MVP, and warnings.

## Tests and remaining validation

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests use generated video and synthetic track observations. They cover upload/decode/duration
errors, scoring, missing/ambiguous balls, track gaps, ties, signed imports, tampering, duplicate
application, replacement scores, persistence, and failed jobs. They do **not** measure real
football model accuracy. See `VALIDATION.md` for executed checks and the future footage test.

A full Cycle 3 entry still requires two original games plus the presentation, report, AI chat
PDF, and real gameplay demo. This package addresses football only. No competition submission
or publication is performed.

## العربية · البدء السريع

1. ثبّت Python 3.11 أو 3.12 وافتح الطرفية في مجلد المشروع.
2. أنشئ بيئة: `python -m venv .venv` ثم فعّلها كما هو موضح أعلاه.
3. ثبّت التطبيق: `python -m pip install -r requirements.txt`.
4. شغّل: `python -m football.cli serve` وافتح http://127.0.0.1:8777.
5. اختر **العربية** أعلى الصفحة. يمكنك تجربة المثال دون فيديو أو نموذج.
6. للتحليل الحقيقي، أوقف الخادم ثم نفّذ `python -m pip install -r requirements-judge.txt`
   وبعده `python -m football.cli download-model` وأعد تشغيل الخادم.
7. ارفع فيديو قصيرًا بكاميرا ثابتة، حدّد خطّي المرمى واتجاه التسجيل، اكتشف اللاعبين
   والكرة، ثم اربط المسارات بالأسماء واضغط **احكم هذه المباراة**.

لا يلزم مفتاح API. التثبيت الأول يحتاج الإنترنت، أما المعالجة فمحلية. النتيجة تقديرية
ولم تُختبر دقتها على مباراة حقيقية. المثال توضيحي وليس حكمًا حقيقيًا. احمِ مجلد `.runtime`
ولا تشاركه؛ فهو يحتوي على الفيديوهات ومفتاح توقيع التقارير.

## License

Project source: **AGPL-3.0-or-later**, see `LICENSE`. Bundled Caveat font: SIL Open Font License,
see `static/fonts/Caveat-OFL.txt`. Third-party model/software notices are in `THIRD_PARTY_NOTICES.md`.
