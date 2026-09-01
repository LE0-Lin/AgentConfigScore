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
SETUP_OUTPUT = ROOT / "assets" / "agent-config-score-setup.gif"
HISTORY_OUTPUT = ROOT / "assets" / "agent-config-score-history.gif"
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
MONO_SMALL = _font(19, mono=True)
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


SETUP_LINES = [
    [("$ ", "green"), ("python -m pip install agent-config-score", "text")],
    [("  Installed agent-config-score 0.18.0", "muted")],
    [],
    [("$ ", "green"), ("agent-config-score init", "text")],
    [("  CREATED  ", "cyan"), (".agentconfigscore.json", "text")],
    [("  CREATED  ", "cyan"), (".github/workflows/agent-config-score.yml", "text")],
    [],
    [("$ ", "green"), ("agent-config-score doctor", "text")],
    [("  PASS  ", "green"), ("config", "text"), ("        Policy and schema are valid", "muted")],
    [("  PASS  ", "green"), ("instructions", "text"), ("  4 supported files found", "muted")],
    [("  PASS  ", "green"), ("baseline", "text"), ("      Automatic diff baseline: origin/main", "muted")],
    [("  PASS  ", "green"), ("workflow", "text"), ("      Pull-request gate is installed", "muted")],
]


def _shell_frame(title: str, subtitle: str, badge: str) -> tuple[Image.Image, ImageDraw.ImageDraw, tuple[int, int, int, int]]:
    image = Image.new("RGB", (WIDTH, HEIGHT), COLORS["page"])
    draw = ImageDraw.Draw(image)
    draw.ellipse((740, -250, 1320, 330), fill=COLORS["glow"])
    draw.text((62, 35), title, fill=COLORS["text"], font=TITLE)
    draw.text((390, 49), subtitle, fill=COLORS["muted"], font=SUBTITLE)

    badge_width = int(draw.textlength(badge, font=BADGE)) + 30
    draw.rounded_rectangle(
        (WIDTH - badge_width - 60, 38, WIDTH - 60, 72),
        radius=17,
        fill="#123B32",
        outline="#286B57",
    )
    draw.text((WIDTH - badge_width - 45, 47), badge, fill=COLORS["green"], font=BADGE)

    window = (55, 98, WIDTH - 55, 608)
    left, top, right, bottom = window
    draw.rounded_rectangle(window, radius=16, fill=COLORS["window"], outline=COLORS["border"], width=2)
    draw.rounded_rectangle((left, top, right, top + 52), radius=16, fill=COLORS["chrome"])
    draw.rectangle((left, top + 36, right, top + 52), fill=COLORS["chrome"])
    for index, color in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
        x = left + 25 + index * 26
        draw.ellipse((x, top + 19, x + 13, top + 32), fill=color)
    draw.text((left + 475, top + 16), "terminal", fill=COLORS["muted"], font=SUBTITLE)
    return image, draw, window


def _setup_frame(visible_lines: int) -> Image.Image:
    image, draw, window = _shell_frame(
        "AgentConfigScore",
        "from install to protected pull requests",
        "30-SECOND SETUP",
    )
    left, top, right, bottom = window
    start_y = top + 76
    for index, line in enumerate(SETUP_LINES[:visible_lines]):
        _text_segments(draw, left + 32, start_y + index * 32, line)

    if visible_lines == len(SETUP_LINES):
        draw.rounded_rectangle((left + 27, bottom - 54, right - 27, bottom - 14), radius=8, fill="#123B32", outline="#286B57")
        draw.text((left + 47, bottom - 44), "READY — EVERY PULL REQUEST IS NOW PROTECTED", fill=COLORS["green"], font=FOOTER)

    draw.text((60, 632), "Install. Initialize. Verify. No service account and no runtime dependencies.", fill=COLORS["muted"], font=FOOTER)
    draw.text((1055, 632), "v0.18", fill=COLORS["cyan"], font=FOOTER)
    return image


def render_setup(output: Path) -> None:
    frames = [_setup_frame(0)]
    durations = [600]
    for visible in range(1, len(SETUP_LINES) + 1):
        frames.append(_setup_frame(visible))
        durations.append(220 if SETUP_LINES[visible - 1] else 120)
    frames.append(_setup_frame(len(SETUP_LINES)))
    durations.append(3200)
    _save_gif(frames, durations, output)


HISTORY_ROWS = [
    ("2026-08-28", 82, "B", "-", "8f13c42"),
    ("2026-08-29", 88, "B", "+6", "2b94a10"),
    ("2026-08-30", 94, "A", "+6", "a73e5cf"),
    ("2026-09-01", 100, "A", "+6", "5b283e5"),
]


def _history_frame(visible_rows: int) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), COLORS["page"])
    draw = ImageDraw.Draw(image)
    draw.ellipse((720, -260, 1320, 340), fill=COLORS["glow"])
    draw.text((62, 35), "AgentConfigScore", fill=COLORS["text"], font=TITLE)
    draw.text((390, 49), "instruction quality, visible over time", fill=COLORS["muted"], font=SUBTITLE)

    badge = "AUDITABLE HISTORY"
    badge_width = int(draw.textlength(badge, font=BADGE)) + 30
    draw.rounded_rectangle((WIDTH - badge_width - 60, 38, WIDTH - 60, 72), radius=17, fill="#17344F", outline="#2B6190")
    draw.text((WIDTH - badge_width - 45, 47), badge, fill=COLORS["cyan"], font=BADGE)

    left, top, right, bottom = 55, 98, WIDTH - 55, 608
    draw.rounded_rectangle((left, top, right, bottom), radius=16, fill=COLORS["window"], outline=COLORS["border"], width=2)
    split = 685
    draw.line((split, top + 28, split, bottom - 28), fill=COLORS["border"], width=2)

    draw.text((left + 30, top + 27), "$ agent-config-score history", fill=COLORS["text"], font=MONO)
    draw.text((left + 30, top + 83), "DATE         SCORE  GRADE  CHANGE   COMMIT", fill=COLORS["muted"], font=BADGE)
    for index, (date, score, grade, change, commit) in enumerate(HISTORY_ROWS[:visible_rows]):
        y = top + 126 + index * 58
        score_color = COLORS["green"] if grade == "A" else COLORS["amber"]
        draw.text((left + 30, y), date, fill=COLORS["text"], font=MONO_SMALL)
        draw.text((left + 245, y), f"{score:>3}", fill=score_color, font=MONO_BOLD)
        draw.text((left + 340, y), grade, fill=score_color, font=MONO_BOLD)
        draw.text((left + 410, y), f"{change:>3}", fill=COLORS["green"] if change != "-" else COLORS["muted"], font=MONO_SMALL)
        draw.line((left + 485, y - 3, left + 485, y + 25), fill=COLORS["border"], width=1)
        draw.text((left + 505, y), commit, fill=COLORS["muted"], font=MONO_SMALL)

    chart_left, chart_top, chart_right, chart_bottom = split + 65, top + 92, right - 45, bottom - 96
    draw.text((split + 45, top + 28), "Score trend", fill=COLORS["text"], font=MONO_BOLD)
    for score in (80, 90, 100):
        y = chart_bottom - int((score - 80) / 20 * (chart_bottom - chart_top))
        draw.line((chart_left, y, chart_right, y), fill="#26384E", width=1)
        draw.text((chart_left - 40, y - 10), str(score), fill=COLORS["muted"], font=BADGE)

    points: list[tuple[int, int]] = []
    for index, (_, score, _, _, _) in enumerate(HISTORY_ROWS[:visible_rows]):
        x = chart_left + int(index * (chart_right - chart_left) / (len(HISTORY_ROWS) - 1))
        y = chart_bottom - int((score - 80) / 20 * (chart_bottom - chart_top))
        points.append((x, y))
    if len(points) > 1:
        draw.line(points, fill=COLORS["cyan"], width=5, joint="curve")
    for index, (x, y) in enumerate(points):
        draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill=COLORS["green"], outline="#D7FFE0", width=2)
        draw.text((x - 12, chart_bottom + 20), f"#{index + 1}", fill=COLORS["muted"], font=BADGE)

    if visible_rows == len(HISTORY_ROWS):
        draw.rounded_rectangle((left + 27, bottom - 57, right - 27, bottom - 17), radius=8, fill="#123B32", outline="#286B57")
        draw.text((left + 47, bottom - 47), "TREND: +18 OVERALL — EVERY CHANGE HAS EVIDENCE", fill=COLORS["green"], font=FOOTER)

    draw.text((60, 632), "Turn instruction quality from a one-time score into a reviewable engineering signal.", fill=COLORS["muted"], font=FOOTER)
    draw.text((1055, 632), "v0.18", fill=COLORS["cyan"], font=FOOTER)
    return image


def render_history(output: Path) -> None:
    frames = [_history_frame(0)]
    durations = [800]
    for visible in range(1, len(HISTORY_ROWS) + 1):
        frames.append(_history_frame(visible))
        durations.append(650)
    frames.append(_history_frame(len(HISTORY_ROWS)))
    durations.append(3600)
    _save_gif(frames, durations, output)


def _save_gif(frames: list[Image.Image], durations: list[int], output: Path) -> None:
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
    parser.add_argument("--all", action="store_true", help="Render the complete visual demo gallery")
    args = parser.parse_args()
    outputs = [(render, args.output)]
    if args.all:
        outputs.extend([(render_setup, SETUP_OUTPUT), (render_history, HISTORY_OUTPUT)])
    for renderer, output in outputs:
        renderer(output)
        print(f"wrote {output} ({output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
