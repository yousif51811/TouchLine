# Touchline — 40-minute team brief

## Goal

Deliver a presentable **Family Game Day** prototype with three working game choices:
football, **Souq Shopping Relay**, and **Matchday Mic**. Keep the existing hand-drawn
English/Arabic interface and one local Python server. No paid API key or custom training.

**Priority:** an understandable, working demo within 40 minutes. Avoid new accounts,
cloud hosting, live football streaming, automatic shirt recognition, or additional games.

## The two quickest games

### 1. Souq Shopping Relay — team competition

- Two teams alternate players for six turns total; 20 seconds per turn.
- A shared basket starts empty. Say all accepted items in order, then add one unused item.
- Use a visible eight-item word bank. English: apple, banana, orange, dates, bread, milk,
  rice, water. Arabic: تفاح، موز، برتقال، تمر، خبز، حليب، أرز، ماء.
- Score **1 point** for repeating the previous list correctly and **1 point** for adding
  exactly one valid, unused item. Add to the basket only when both checks pass.
- An incorrect turn scores only the checks it passed; the basket otherwise stays unchanged.
- Highest team total wins. Equal totals are a draw. No complex elimination/tie-break system.
- This is spoken sequence memory, distinct from the brief's prohibited heritage guessing example.

### 2. Matchday Mic — individual competition

- Each player gets one 20-second sports commentary turn.
- The card shows three required words in order and one forbidden word.
- Example: **pass → shoot → goal**; forbidden: **foul**.
  Arabic equivalent: **تمريرة ← تسديدة ← هدف**; forbidden: **خطأ**.
- Score **1 point per required word** (3 maximum), **1 for all three in order**, and
  **1 for avoiding the forbidden word**: 5 maximum. A silent recording earns no points.
- Cycle through a small fixed deck. Highest individual total wins; ties share first place.

## Shared speech implementation

- Browser microphone recording with upload fallback for WAV/MP3/M4A/WebM/OGG.
- Maximum 20 seconds, 10 MB per turn. Explain microphone permission failures.
- Local pretrained multilingual Whisper tiny, through faster-whisper on CPU/int8.
  One explicit model download; no API key. English/Arabic transcription accuracy needs testing.
- Show transcript, rule-by-rule points, current turn, totals, and final winner.
- Empty/unclear audio means **retry needed**, with no score or turn advancement.
- Normalize case, punctuation, and Arabic diacritics/alef variants. Use explicit word-bank
  aliases, not open-ended semantic judging. Keep scoring deterministic and explainable.
- Apply each turn once on the server. Prevent duplicate submissions. Do not silently turn
  typed text or example transcripts into claimed AI evidence.

## Work split — teammates can start now

| Owner | Deliverable | What to include |
| --- | --- | --- |
| App implementer (this chat) | Three-game app, speech pipeline, scoring, tests, README, GitHub upload | Keep football working; add game selector and shared voice-round flow. Source goes under `src/`. |
| Teammate A | 30-slide presentation, exported as PDF | Problem; family audience; three games; UX; video/speech AI; architecture; examples; tests; limitations; results; team contributions. Use actual screenshots after integration. |
| Teammate B | 6-page technical report, exported as PDF | Problem; design; implementation; rules; validation; limitations. Explain that goal detection is unvalidated on real goals and speech recognition may make errors. |
| Teammate C | Real demo recordings and final submission checks | Record one successful speech turn for each new game, a failed rule, and a retry. Capture football track assignment using the provided clip. Keep video near two minutes where possible. |
| All members | One combined AI-chat PDF | Save all AI conversations and describe AI contributions transparently. Students must understand and demonstrate their solution. |

**Avoid editing the app files in parallel without coordination.** Teammates can prepare
slides/report/video assets independently while this chat integrates the app.

## Integration contract

Current local project root contains `football/`, `static/`, `tests/`. GitHub layout will put
these under `src/`; the repository-root README will start with `cd src`.

- Preserve existing football APIs and signed report verification.
- New game IDs: `souq_relay`, `matchday_mic`.
- Add `speech_games/` for the audio transcriber, game rules, sessions, and FastAPI router.
- API: create a game session; upload current-turn audio; retrieve the session/scoreboard.
  The server owns the expected turn, basket, active player, and scoring.
- Each accepted turn returns transcript, player/team, points, reasons, and updated session.
- The frontend shows a three-card game chooser; football opens its existing flow. Speech
  games share one record/upload → analyze → transcript/results → next-turn screen.
- Local recordings, model weights, private reports, signing keys, and user footage stay out
  of GitHub and source ZIPs.

## Forty-minute schedule

- **0–5 min:** lock these rules, write this brief, begin speech dependency/model installation.
- **5–20 min:** implement both rule sets and one shared audio/session API; build the game selector.
- **20–30 min:** connect recording/upload, transcript, scores, turns, and English/Arabic labels.
- **30–40 min:** run checks, exercise real/synthetic audio honestly, fix blockers, update README,
  and upload code under `src/` in https://github.com/yousif51811/TouchLine.

If local speech installation or model access fails, keep sample mode visibly labelled and
report the real-AI limitation. Never substitute invented transcripts for successful analysis.

## Definition of done

- Three selectable games; no broken placeholder cards.
- Both new games can accept short audio and update scores from the returned transcript.
- Correct, incorrect, silent, repeated, and final-turn cases are covered.
- Microphone denial has an upload fallback; failed analysis preserves the turn.
- English/Arabic layouts remain usable on desktop and narrow screens.
- Simple install/start/model-download instructions, no API key required.
- Existing football tests still pass. The supplied football clip demonstrates tracking and
  possession only; it has no visible goals and cannot prove real goal detection.

## Competition checklist (separate from the app)

- Cycle 3: football plus two original games, including team and individual competition.
- Three PDFs: **30-slide presentation**, **6-page report**, **all AI chats**; each ≤10 MB.
- Downloadable prototype link with README, plus accessible demo-video link.
- For YouTube, use **Unlisted** and test links while signed out.
- Deadline in the supplied guide: **29 October 2026, 6:00 PM UAE time**.
- No submission or sharing-permission changes are performed automatically by this chat.
