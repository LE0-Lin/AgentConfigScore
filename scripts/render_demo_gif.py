#!/usr/bin/env python3
"""Render the README terminal demo as a deterministic animated GIF.

This is a maintainer tool, not a runtime dependency. Install Pillow before
running it: ``python -m pip install pillow``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "assets" / "agent-config-score-demo.gif"
WIDTH = 1200
HEIGHT = 675

COLORS = {
    "page": "#07111F",
    "glow": "#102A43",
    "window": "#0D1626",
    "chrome": "#162235",
    "border": "#2C3E55",
    "text": "#E6EDF3",
    "muted": "#8FA3B8",
    "green": "#7EE787",
    "cyan": "#79C0FF",
    "red": "#FF7B72",
    "amber": "#E3B341",
}


def _font(size: int, *, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    windows = Path("C:/Windows/Fonts")
    candidates = (
        [windows / ("consolab.ttf" if bold else "consola.ttf")]
        if mono
        else [windows / ("segoeuib.ttf" if bold else "segoeui.ttf")]
    )
    candidates.extend(
        [
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if mono and bold else
                 "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf" if mono else
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/System/Library/Fonts/SFNSMono.ttf" if mono else "/System/Library/Fonts/SFNS.ttf"),
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default(size=size)


TITLE = _font(34, bold=True)
SUBTITLE = _font(18)
BADGE = _font(14, bold=True)
MONO = _font(22, mono=True)
MONO_BOLD = _font(22, mono=True, bold=True)
FOOTER = _font(17)


OUTPUT_LINES = [
    [("AgentConfigScore regression  ", "text"), ("A 100", "green"), (" → ", "muted"), ("B 82 (-18)", "amber")],
    [("New findings: 2", "text"), ("   Resolved: 0   Suppressed: 0", "muted")],
    [],
    [("+ ERROR   ", "red"), ("curl-pipe-shell", "text"), ("   Remote script piped directly to a shell", "muted")],
    [("          .github/copilot-instructions.md:12", "muted")],
    [("+ WARNING ", "amber"), ("dead-path", "text"), ("          Referenced path does not exist: src/legacy_auth.py", "muted")],
    [("          AGENTS.md:31", "muted")],
    [],
    [("POLICY RESULT: BLOCKED", "red")],
]


def _text_segments(draw: ImageDraw.ImageDraw, x: int, y: int, segments: list[tuple[str, str]]) -> None:
    cursor = x
    for text, color in segments:
        font = MONO_BOLD if color in {"red", "amber", "green"} else MONO
        draw.text((cursor, y), text, fill=COLORS[color], font=font)
        cursor += int(draw.textlength(text, font=font))


def _frame(command_chars: int, visible_lines: int, *, cursor: bool = True) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), COLORS["page"])
    draw = ImageDraw.Draw(image)

    draw.ellipse((740, -250, 1320, 330), fill=COLORS["glow"])
    draw.text((62, 35), "AgentConfigScore", fill=COLORS["text"], font=TITLE)
    draw.text((390, 49), "PR regression gate for coding-agent instructions", fill=COLORS["muted"], font=SUBTITLE)

    badge = "DETERMINISTIC  •  ZERO RUNTIME DEPS"
    badge_width = int(draw.textlength(badge, font=BADGE)) + 30
    draw.rounded_rectangle((WIDTH - badge_width - 60, 38, WIDTH - 60, 72), radius=17, fill="#123B32", outline="#286B57")
    draw.text((WIDTH - badge_width - 45, 47), badge, fill=COLORS["green"], font=BADGE)

    left, top, right, bottom = 55, 98, WIDTH - 55, 608
    draw.rounded_rectangle((left, top, right, bottom), radius=16, fill=COLORS["window"], outline=COLORS["border"], width=2)
    draw.rounded_rectangle((left, top, right, top + 52), radius=16, fill=COLORS["chrome"])
    draw.rectangle((left, top + 36, right, top + 52), fill=COLORS["chrome"])
    for index, color in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
        x = left + 25 + index * 26
        draw.ellipse((x, top + 19, x + 13, top + 32), fill=color)
    draw.text((left + 475, top + 16), "pull request check", fill=COLORS["muted"], font=SUBTITLE)

    command = "agent-config-score diff origin/main"
    prompt_x, prompt_y = left + 32, top + 79
    draw.text((prompt_x, prompt_y), "$", fill=COLORS["green"], font=MONO_BOLD)
    shown = command[:command_chars]
    draw.text((prompt_x + 27, prompt_y), shown, fill=COLORS["text"], font=MONO)
    if cursor:
        cursor_x = prompt_x + 27 + int(draw.textlength(shown, font=MONO)) + 2
        draw.rectangle((cursor_x, prompt_y + 4, cursor_x + 11, prompt_y + 28), fill=COLORS["cyan"])

    output_y = prompt_y + 54
    for index, line in enumerate(OUTPUT_LINES[:visible_lines]):
        _text_segments(draw, prompt_x, output_y + index * 34, line)

    if visible_lines == len(OUTPUT_LINES):
        draw.rounded_rectangle((left + 27, bottom - 58, right - 27, bottom - 18), radius=8, fill="#291B20", outline="#71333A")
        draw.text((left + 47, bottom - 48), "BASELINE POLICY STAYED IN CONTROL — THIS REGRESSION CANNOT MERGE", fill="#FFB4AC", font=FOOTER)

    draw.text((60, 632), "A pull request can change the instructions. It cannot weaken the policy judging itself.", fill=COLORS["muted"], font=FOOTER)
    draw.text((1055, 632), "v0.18", fill=COLORS["cyan"], font=FOOTER)
    return image


def render(output: Path) -> None:
    frames: list[Image.Image] = []
    durations: list[int] = []

    frames.append(_frame(0, 0))
    durations.append(650)
    command_length = len("agent-config-score diff origin/main")
    for count in range(1, command_length + 1, 2):
        frames.append(_frame(min(count, command_length), 0))
        durations.append(65)
    frames.append(_frame(command_length, 0, cursor=False))
    durations.append(550)

    for visible in range(1, len(OUTPUT_LINES) + 1):
        frames.append(_frame(command_length, visible, cursor=False))
        durations.append(260 if OUTPUT_LINES[visible - 1] else 120)
    frames.append(_frame(command_length, len(OUTPUT_LINES), cursor=False))
    durations.append(3600)

    output.parent.mkdir(parents=True, exist_ok=True)
    palette_frames = [frame.quantize(colors=128, method=Image.Quantize.MEDIANCUT) for frame in frames]
    palette_frames[0].save(
        output,
        save_all=True,
        append_images=palette_frames[1:],
        duration=durations,
        loop=0,
        disposal=2,
        optimize=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    render(args.output)
    print(f"wrote {args.output} ({args.output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
