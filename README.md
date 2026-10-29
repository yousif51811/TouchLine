# Touchline — Family Game Day

Three family games in a hand-drawn English/Arabic web app. One local Python server;
no account, paid API key, Node.js, or database.

| Game | Play | AI / scoring |
| --- | --- | --- |
| **Football** | Upload a short match clip, mark goal boundaries, name player tracks | Local YOLO26n + ByteTrack; estimated goals, possession and MVP. Possession-only mode for clips without visible goals. |
| **Souq Shopping Relay** | Teams repeat a growing shopping list and add one unused item | Local speech recognition; check list order and valid additions. Six alternating turns, two points per turn. |
| **Matchday Mic** | Say three sports words in order while avoiding a forbidden word | Local speech recognition; five points maximum per player. Twenty-second turns. |

**Team handoff:** read [project.md](project.md) for the game rules, teammate work split,
40-minute delivery scope, and competition deliverables.

## Quick start

Install **Python 3.11 or 3.12, 64-bit**. Open a terminal in this folder.
From the repository root, first run `cd src`.

```sh
python -m venv .venv
```

Activate the environment:

```sh
# macOS / Linux
source .venv/bin/activate
```

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

If activation is blocked on Windows, use `.venv\Scripts\python.exe` instead of `python`
in the commands below. No security-policy change is necessary.

```sh
python -m pip install -r requirements.txt
python -m football.cli serve
```

Open **http://127.0.0.1:8777**. Choose a game. The football sample works without models.
Ctrl+C stops the server. The `?` button in the app also contains setup instructions.

## Enable the two voice games

Stop the server, then run in the activated environment:

```sh
python -m pip install -r requirements-speech.txt
python -m football.cli download-speech-model
python -m football.cli serve
```

The pretrained multilingual Whisper tiny model downloads once. Later audio processing runs
locally on CPU. No API key is needed. Speak in the language selected when creating the game.

1. Choose **Souq Shopping Relay** or **Matchday Mic**.
2. Enter players and select English or Arabic as the spoken language.
3. Record a turn in the browser, or upload WAV/MP3/M4A/WebM/OGG audio.
4. Click **Judge this turn**. The transcript, scoring checks, and updated totals appear.
5. The next player is selected automatically. Final totals determine the winner; ties are shared.

Limits: **20 seconds / 10 MB per turn**. Denied microphone access has an upload fallback.
Silent/unclear recordings do not advance the turn. Recognition can be wrong: inspect the
transcript before making accuracy claims. The prototype does not offer transcript correction,
semantic story grading, or cloud fallback. Game notes can be downloaded as JSON.

### Souq Shopping Relay

Say only item names from the visible bank, in the existing basket's order, then add one unused
item. One point for repeating the prefix correctly; one for a valid new addition. The basket
grows only when both checks pass. Six turns alternate teams, cycling through their players.

English bank: apple, banana, orange, dates, bread, milk, rice, water.
Arabic bank: تفاح، موز، برتقال، تمر، خبز، حليب، أرز، ماء.

### Matchday Mic

Each player gets one turn. Say the three card words in order and avoid the forbidden word.
One point per required word, one for all three in order, one for avoiding the forbidden word.
Example: **pass → shoot → goal**, forbidden **foul**. English/Arabic decks are included.

## Enable football analysis

```sh
python -m pip install -r requirements-judge.txt
python -m football.cli download-model
python -m football.cli serve
```

The supplied CPU-wheel pins target Windows/Linux x86-64. On Apple Silicon, use the listed
PyTorch/torchvision versions without the `+cpu` suffix and remove the extra-index line from
`requirements-judge.txt`. Only Linux execution has been tested.

Upload MP4/WebM up to **two minutes / 100 MB**. Use a stationary camera. Mark each visible
goal boundary and its inside direction; or choose **Possession only** if goals are not visible.
Detect players, inspect thumbnails, assign track names, and judge. Signed reports update the
score automatically and replace previous results rather than adding goals twice.

See [football guide](src/FOOTBALL.md) for calibration, standalone Python judging, signed report
imports, report keys, supported footage, and detailed API notes.

**Important:** football goals are 2D image-based estimates. The provided passing clip has no
visible goals; it tested tracking/possession, not goal accuracy. Much of that clip remained
unknown. An illustrative sample is clearly labelled and is never accepted as a real AI report.

## Project structure

```text
src/
  football/       local server, football detector/rules, signatures, CLI
speech_games/   local transcriber, two game rule sets, turn/session API
static/         hand-drawn HTML/CSS/JS interface and bundled font
examples/       illustrative football report and CLI config
 tests/         scoring, upload, report, speech-game and session tests
 tools/         source-only packaging utility
```

Speech API: `GET /api/speech/health`; `POST /api/speech/sessions` with game ID, language,
players, and team names; `GET /api/speech/sessions/{id}`; multipart
`POST /api/speech/sessions/{id}/audio` with audio, turn index, and submission ID.
The server owns turns, scores, basket state, and duplicate protection. Interactive schemas
for all games are at http://127.0.0.1:8777/api/docs.

## Tests, data and sharing

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
python tools/package.py
```

The source-only ZIP is written to `dist/touchline-source.zip`. It excludes model weights,
recordings, user footage, signing keys, and local results. **Do not share `.runtime/` or `.venv/`.**
`.runtime/` stores uploads/audio, model files, speech-session histories and the football signing
key. The app binds only to 127.0.0.1. It has no internet-facing authentication or hosting.

Speech sessions are persisted locally. Football jobs/media links require re-upload after
restart; the last verified football report remains available. See [validation record](src/VALIDATION.md)
for executed checks and accuracy limits. User footage is not included in this repository.

The competition also requires a presentation, technical report, AI-chat PDF, accessible
prototype, and a real demo. This application is not an automatic submission or proof of
complete competition compliance.

## العربية — البدء السريع

- ثبّت Python 3.11 أو 3.12 وافتح الطرفية داخل مجلد التطبيق (`src` في GitHub).
- أنشئ البيئة بـ `python -m venv .venv` ثم فعّلها كما هو موضح أعلاه.
- نفّذ `python -m pip install -r requirements.txt` ثم `python -m football.cli serve`.
- افتح http://127.0.0.1:8777 واختر **العربية** ثم إحدى الألعاب الثلاث.
- للألعاب الصوتية: ثبّت `requirements-speech.txt` وشغّل `python -m football.cli download-speech-model` مرة واحدة.
- لتحليل كرة القدم: ثبّت `requirements-judge.txt` وشغّل `python -m football.cli download-model`.
- لا يلزم مفتاح API. نزّل النماذج مرة واحدة، ثم تتم المعالجة محليًا. راجع النصوص
  والأدلة لأن التعرف على الصوت وتقدير الأهداف والاستحواذ قد يخطئان.

## License

New application code under `src/`: **AGPL-3.0-or-later**, see [src/LICENSE](src/LICENSE). The repository’s existing root license is retained for its original contents.
Caveat font: SIL Open Font License. Dependencies retain their own licenses; see
[third-party notices](src/THIRD_PARTY_NOTICES.md).

## Render deployment

Create a Python Web Service using this repository. Root directory: `src`.
Build command: `bash render-build.sh`.
Start command: `python -m football.cli serve --host 0.0.0.0 --port $PORT`.
Set `PYTHON_VERSION=3.12.10`; health check path: `/api/health`.
The build installs both AI pipelines and downloads their models. Allow extra build time
and sufficient RAM for CPU inference. Local data is ephemeral without a persistent disk.
The root `render.yaml` can also be used as a Blueprint. It generates a stable signing secret.
