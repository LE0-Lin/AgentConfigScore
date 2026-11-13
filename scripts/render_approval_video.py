"""Render a one-minute evidence walkthrough, not a live screen recording.

Development-only dependencies: Pillow and an installed ffmpeg executable.
All displayed results come from the retained JSON reports. No model calls.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw
from render_demo_gif import font

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/approval-gate"
W, H = 1280, 720
BG, PANEL, EDGE = "#0B1422", "#111E2D", "#304457"
WHITE, SOFT, MINT, CORAL = "#ECF3F8", "#A9BED0", "#76E5C1", "#FFAD9D"


def scenes():
    replay = json.loads((EXAMPLE / "recorded/result.json").read_text(encoding="utf-8"))
    smoke = json.loads((EXAMPLE / "assistant-recorded/result.json").read_text(encoding="utf-8"))
    if replay["evidence_tier"] != "synthetic_development_demo" or smoke["status"] != "completed":
        raise ValueError("Expected explicitly classified, completed development records")
    narrowed, repaired = replay["static"]["cases"]
    execution = {row["case"]: row for row in replay["execution"]}
    rows = smoke["transcript"]
    return [
        ("01 / THE PROBLEM", "The rule still exists. Its coverage changed.",
         [("Before: globs = workspace/**", WHITE), ("After:  globs = docs/**", CORAL),
          ("Never delete files without approval.", SOFT), ("Selected target: workspace/obsolete.txt", SOFT),
          ("Standalone scores: 100 -> 100", MINT)],
         "A clean lint score does not prove that a protection remains available."),
        ("02 / REVIEW BEFORE MERGE", "Installed ACS detects the lost requirement.",
         [("ACS " + replay["static"]["tool"]["version"] + " / opt-in scope compare", SOFT),
          ("Lost active directives: " + str(narrowed["report"]["summary"]["recognized_active_losses"]), CORAL),
          ("Source: .cursor/rules/deletion.mdc:5", WHITE),
          ("Review exit: " + str(narrowed["exit"]), CORAL),
          ("Restore coverage -> review exit: " + str(repaired["exit"]), MINT)],
         "Static prediction for declared file context; no runtime compliance claim."),
        ("03 / CHECK BEFORE THE EFFECT", "A separate host validates each delete request.",
         [("No grant      -> " + execution["missing_approval"]["reason"], CORAL),
          ("Self approval -> " + execution["self_approval"]["reason"], CORAL),
          ("Expired grant -> " + execution["expired"]["reason"], CORAL),
          ("Changed file  -> " + execution["changed_content"]["reason"], CORAL),
          ("Unrelated files: preserved in all 12 scripted cases", MINT)],
         "These 12 requests are synthetic development cases; approvals are simulated."),
        ("04 / ASSISTANT-OPERATED SMOKE", "Four actual requests through the JSON bridge.",
         [("1. No approval  -> " + rows[0]["result"]["reason"], CORAL),
          ("2. Wrong target -> " + rows[1]["result"]["reason"], CORAL),
          ("3. Matching grant -> " + rows[2]["result"]["decision"], MINT),
          ("4. Reuse grant  -> " + rows[3]["result"]["reason"], CORAL),
          ("Filesystem checks passed; one temporary file deleted", MINT)],
         "Maintainer-assisted Codex session; host approval simulated; not isolated."),
        ("05 / KNOW THE BOUNDARY", "One controlled tool. Explicit assumptions.",
         [("Host owns a stable local workspace", WHITE),
          ("Operator approval is issued outside the tool interface", WHITE),
          ("Arbitrary shell / code / hostile path races: out of scope", CORAL),
          ("No independent accuracy or general safety estimate", SOFT),
          ("ACS static CLI + separate example executor", MINT)],
         "The assistant smoke does not validate isolation or attest a backend model ID."),
        ("06 / REPRODUCE AND INSPECT", "Code, records and limitations are public.",
         [("python scripts/run_approval_demo.py", WHITE),
          ("       --output-dir approval-demo-result", WHITE),
          ("python examples/approval-gate/try_gate.py", WHITE),
          ("Linux / Windows / macOS installed-wheel replay", MINT),
          ("github.com/LE0-Lin/AgentConfigScore", SOFT)],
         "Rendered walkthrough from retained JSON; this video is not a screen recording.")]


def frame(scene, progress):
    label, title, lines, note = scene
    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)
    draw.text((52, 27), "AgentConfigScore", font=font(23, bold=True), fill=WHITE)
    draw.text((915, 30), "DELETION APPROVAL PROTOTYPE", font=font(16, bold=True), fill=MINT)
    draw.line((52, 76, W - 52, 76), fill=EDGE, width=2)
    draw.text((52, 106), label, font=font(18, bold=True), fill=MINT)
    draw.text((52, 145), title, font=font(33, bold=True), fill=WHITE)
    draw.rounded_rectangle((52, 217, W - 52, 550), radius=16, fill=PANEL, outline=EDGE, width=2)
    for index, (line, color) in enumerate(lines):
        draw.text((82, 248 + index * 55), line, font=font(24, mono=True), fill=color)
    draw.text((52, 581), note, font=font(19), fill=SOFT)
    draw.text((52, 640), "Development evidence  /  Temporary files  /  Explicit trust boundaries", font=font(17), fill=SOFT)
    draw.rectangle((0, H - 6, int(W * progress), H), fill=MINT)
    return canvas


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory")
    args = parser.parse_args(argv)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required for the MP4 walkthrough")
    args.output_dir.mkdir(exist_ok=False)
    with TemporaryDirectory(prefix="acs-video-frames-") as directory:
        directory = Path(directory)
        slides = scenes()
        for i, scene in enumerate(slides):
            image = frame(scene, (i + 1) / len(slides))
            image.save(directory / f"slide-{i}.png")
            image.save(args.output_dir / f"preview-{i + 1}.png")
        listing = directory / "slides.txt"
        listing.write_text("".join(f"file 'slide-{i}.png'\nduration 10\n" for i in range(len(slides)))
                           + f"file 'slide-{len(slides) - 1}.png'\n", encoding="utf-8")
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
                        "-i", str(listing), "-t", "60", "-r", "10", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart", str(args.output_dir / "approval-walkthrough.mp4")], check=True, timeout=90)
        frames = [Image.open(directory / f"slide-{i}.png").convert("P", palette=Image.Palette.ADAPTIVE, colors=96)
                  for i in range(len(slides))]
        frames[0].save(args.output_dir / "approval-walkthrough.gif", save_all=True, append_images=frames[1:],
                       duration=10000, loop=0, optimize=True)
    print("Rendered 60-second evidence walkthrough (MP4 and GIF).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
