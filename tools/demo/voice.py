"""Step 1 of the demo video: one voice clip per caption, and how long each one lasts.

    uv run --with edge-tts --with mutagen tools/demo/voice.py

Reads tools/demo/narration.json; writes tools/demo/out/clips/<id>.mp3 and out/durations.json.
Uses Microsoft's neural voices through edge-tts: only the narration text leaves the machine.
Set VOICE=fr-FR-DeniseNeural (or another `edge-tts --list-voices` name) to change the voice.
"""

import asyncio
import json
import os
from pathlib import Path

import edge_tts
from mutagen.mp3 import MP3

HERE = Path(__file__).parent
OUT = HERE / "out"


async def main() -> None:
    spec = json.loads((HERE / "narration.json").read_text(encoding="utf-8"))
    voice = os.environ.get("VOICE", spec["voice"])
    clips = OUT / "clips"
    clips.mkdir(parents=True, exist_ok=True)
    durations: dict[str, int] = {}
    for seg in spec["segments"]:
        path = clips / f"{seg['id']}.mp3"
        text = seg.get("speech", seg["caption"]).replace("«", "").replace("»", "")
        await edge_tts.Communicate(text, voice, rate=spec.get("rate", "+0%")).save(str(path))
        durations[seg["id"]] = round(MP3(path).info.length * 1000)
        print(f"{seg['id']:>9}  {durations[seg['id']] / 1000:4.1f} s  {text}")
    (OUT / "durations.json").write_text(json.dumps(durations, indent=1), encoding="utf-8")
    print(f"total speech: {sum(durations.values()) / 1000:.0f} s with {voice}")


asyncio.run(main())
