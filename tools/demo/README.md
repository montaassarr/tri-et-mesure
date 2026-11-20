# Demo video

A narrated walk through the four roles, rebuilt in three steps. The voice sets the pace:
each caption stays on screen exactly as long as its sentence.

```bash
# 0. the app must be running (pnpm dev) with demo data loaded
uv run --with edge-tts --with mutagen tools/demo/voice.py      # 1. one voice clip per caption
cd apps/web && node scripts/demo-video.mjs http://localhost:5173 "Accident - contrat CT71957885"; cd ../..   # 2. record
uv run --with imageio-ffmpeg tools/demo/mux.py                  # 3. voice + video -> docs/demo/demo.mp4
```

- Text and voice: [narration.json](narration.json). Change a sentence, re-run the 3 steps.
- Another voice: `VOICE=fr-FR-DeniseNeural uv run ...` (list: `edge-tts --list-voices`).
- Step 2 opens the case named on the command line: pick an open case the AI got right.
- The voice is Microsoft's neural text-to-speech (via edge-tts); only the narration text is sent.
