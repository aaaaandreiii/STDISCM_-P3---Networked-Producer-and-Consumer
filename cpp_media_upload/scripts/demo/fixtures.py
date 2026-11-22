"""Generate small, run-specific MP4 fixtures on the producer guest."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from checks import SCENARIOS, require


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def seed(samples, run_id):
    require(re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}", run_id), "invalid run ID")
    require(samples.is_dir() and not samples.is_symlink(), "producer sample directory missing")
    run = samples / run_id
    run.mkdir(mode=0o755)
    run.chmod(0o755)
    manifest = {}
    ffmpeg = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-filter_threads", "1"]

    def encode(args):
        subprocess.run([*ffmpeg, *args], check=True, timeout=40)

    def folder(path):
        path.mkdir(mode=0o755)
        path.chmod(0o755)

    with tempfile.TemporaryDirectory(prefix=".masters-", dir=run) as work:
        first, second = (Path(work) / f"{name}.mp4" for name in ("first", "second"))
        for source, hue in ((first, "0"), (second, "95")):
            encode([
                "-f", "lavfi", "-i", "testsrc2=duration=14:size=320x180:rate=20",
                "-vf", f"hue=h={hue}", "-an", "-c:v", "libx264", "-threads", "1",
                "-preset", "ultrafast", "-crf", "25", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", str(source)
            ])
        for scenario, producers in SCENARIOS.items():
            root = run / scenario
            folder(root)
            for producer in range(1, producers + 1):
                folder(root / f"producer_{producer}")
            manifest[scenario] = []

            def output(producer, suffix, source=None, copy=None):
                destination = root / f"producer_{producer}" / f"{run_id}-{suffix}.mp4"
                if copy:
                    shutil.copyfile(copy, destination)
                elif source:
                    encode(["-i", str(source), "-c", "copy", "-metadata",
                            f"comment={run_id}/{scenario}/{producer}/{suffix}", "-movflags", "+faststart",
                            str(destination)])
                else:
                    encode([
                        "-f", "lavfi", "-i", "testsrc2=duration=14:size=480x270:rate=24",
                        "-vf", "noise=alls=9:allf=t+u", "-an", "-c:v", "libx264",
                        "-threads", "1", "-preset", "ultrafast", "-crf", "5", "-pix_fmt", "yuv420p",
                        "-metadata", f"comment={run_id}/compression", "-movflags", "+faststart", str(destination)
                    ])
                destination.chmod(0o644)
                manifest[scenario].append({"producer": destination.parent.name, "filename": destination.name,
                                           "size": destination.stat().st_size, "sha256": digest(destination)})
                return destination

            if scenario == "duplicates":
                original = output(1, "duplicate-a", source=first)
                output(2, "duplicate-b", copy=original)
                output(1, "same-name", source=first)
                output(2, "same-name", source=second)
            elif scenario == "compression":
                output(1, "compression")
            else:
                for producer in range(1, producers + 1):
                    for index in range(1, 4 if scenario == "overload" else 2):
                        output(producer, f"{scenario}-{producer}-{index}", source=first if producer % 2 else second)
    (run / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
