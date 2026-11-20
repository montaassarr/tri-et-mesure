"""Step 3 of the demo video: lay each voice clip under its caption and export an MP4.

    uv run --with imageio-ffmpeg tools/demo/mux.py

Reads out/raw.webm (step 2), out/marks.json (when each caption appeared) and out/clips/*.mp3;
writes docs/demo/demo.mp4 (H.264 + AAC, 1280 px wide, sized to stay under GitHub's 10 MB video limit).
"""

import json
import subprocess
from pathlib import Path

import imageio_ffmpeg

HERE = Path(__file__).parent
OUT = HERE / "out"
TARGET = HERE.parent.parent / "docs" / "demo" / "demo.mp4"


def main() -> None:
    marks: list[dict[str, object]] = json.loads((OUT / "marks.json").read_text(encoding="utf-8"))
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(OUT / "raw.webm")]
    for m in marks:
        cmd += ["-i", str(OUT / "clips" / f"{m['id']}.mp3")]
    delays = "".join(
        f"[{i + 1}:a]adelay={int(m['t'])}|{int(m['t'])},volume=1.6[a{i}];" for i, m in enumerate(marks)
    )
    mix = "".join(f"[a{i}]" for i in range(len(marks)))
    # apad + -shortest: the video sets the length, the voice track is padded with silence.
    graph = f"[0:v]scale=1280:-2[v];{delays}{mix}amix=inputs={len(marks)}:normalize=0,apad[voice]"
    cmd += [
        "-filter_complex", graph,
        "-map", "[v]", "-map", "[voice]",
        "-c:v", "libx264", "-preset", "slow", "-crf", "28", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "96k",
        "-movflags", "+faststart", "-shortest",
        str(TARGET),
    ]
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd, check=True)
    print(f"saved {TARGET} ({TARGET.stat().st_size / 1e6:.1f} MB)")


main()
