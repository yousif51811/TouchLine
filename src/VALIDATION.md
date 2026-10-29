# Validation record

## Executed on 29 October 2026

Environment: Linux x86-64, Python 3.12.14, CPU-only PyTorch 2.7.0, Ultralytics 8.4.63.

- **26 automated tests pass.** These exercise scoring, goal boundaries/directions/rearming,
  missing/ambiguous ball observations, track identity gaps, possession ties, invalid mappings,
  video decoding/duration/100 MB limits, asynchronous job failures, report signatures,
  tampering, mismatched matches, duplicate application, replacement scores, persisted reports,
  local-origin checks, and possession-only mode.
- Python compilation and JavaScript syntax checks pass.
- Downloaded official YOLO26n weights using the documented setup command.
- Ran the actual CPU detector/ByteTrack CLI on a three-second **synthetic empty-pitch clip**.
  It completed and produced a signed report; signature verified independently. This was a
  pipeline smoke test, not a football-accuracy test.
- Used the browser UI to upload the user-provided `demovid.mp4` (9.8 seconds, 1280×720,
  25 fps), run detection, assign three player tracks using their thumbnails, and automatically
  apply a signed result. No goals were visible, so possession-only mode was selected.
- That real clip produced **three player tracks**, 12.5 analyzed samples/s, approximately
  **53.9% ball coverage**, **1.92 s attributed possession**, and **7.88 s unknown time**.
  The white-shirt player received 0 s, yellow-shirt player 1.04 s, and green-jacket player
  0.88 s under the default conservative rules. These are algorithm outputs, **not manually
  verified ground truth**. The low attribution rate demonstrates a substantial current limitation.
- The report correctly leaves goal scoring unassessed for clips without marked goals.
- Browser checks covered English/Arabic switching, right-to-left layout, sample labels,
  starting a match, real/synthetic uploads, keyboard goal marking, player assignment,
  automatic results, and annotated playback controls. Desktop and narrow viewports were inspected.

User footage, extracted frames, thumbnails, model weights, signing keys, and test reports are
excluded from the source ZIP. No gameplay video is represented as synthetic sample evidence.

## What has NOT been established

- Reliable football goal detection on real goal-scoring footage.
- Accurate possession percentages or a definitive MVP on real matches.
- Robustness to moving cameras, crowded matches, airborne balls, or occlusions.
- Cross-platform execution on Windows/macOS; setup notes are provided, but only Linux was run.
- Audio/speech judging, the two additional games, or a complete competition submission.

The existing demo has no visible goals and cannot validate real goal detection. A synthetic
boundary-crossing test verifies the scoring rule, not real-world goal recognition.

## Real-footage acceptance test to perform later

1. Obtain permission to use a short, stationary-camera family match with both goals visible.
   Include a known goal for each side, a miss, a loose ball, passes, and a short occlusion.
2. Manually annotate goal times and player-control intervals independently of the app.
3. Run the app using marked boundaries and verified track-to-player assignments.
4. Check the overlays at every goal candidate, possession transition, and identity change.
   Record goal precision/recall, timing error, attributed/unknown time, and possession error.
5. Verify one counted goal per real crossing and no count for the miss. Reject physical-goal
   claims based solely on ambiguous 2D geometry.
6. Import the signed report once; re-import it and confirm rejection without changing the score.
   Change calibration/mappings and confirm the new result replaces the previous snapshot.
7. Repeat on another suitable clip. Document failures before describing the judge as accurate.

No numerical football-accuracy target has been met or claimed. Until those comparisons exist,
this is an experimental detection and rules prototype with explicit uncertainty.

## Three-game update

- Added Souq Shopping Relay (team sequence memory) and Matchday Mic (individual commentary).
- **31 automated tests passed** before the final audio-decoder compatibility adjustment;
  coverage includes speech rules, Arabic normalization, silence retry, duplicate turns,
  final winners, and persisted sessions. No additional full-suite passes were requested.
- Downloaded the actual multilingual Whisper tiny model. Its CPU/int8 transcription of a
  synthesized English WAV returned `pass, and shoot, and goal.` without a retry. This verifies
  local decoding/transcription; it is not a human-speech or Arabic accuracy benchmark.
- The latest PyAV API removed a keyword used by the older faster-whisper convenience decoder.
  The app now decodes and resamples audio directly through PyAV before passing samples to Whisper.
- The three-game chooser and the individual-game setup/round screens were inspected in-browser.
- Microphone recording is implemented with permission handling and an upload fallback;
  physical microphone recording and Arabic recognition have not been validated on this device.
