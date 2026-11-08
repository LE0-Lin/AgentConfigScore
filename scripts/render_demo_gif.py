#!/usr/bin/env python3
"""Render the gallery from the installed release and local fixtures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
FIXTURES = ROOT / "tests" / "fixtures" / "contracts" / "regression"
MOVE = FIXTURES / "instruction-move"
SHELL = FIXTURES / "unsafe-shell"
RELEASE = "0.24.0"
WIDTH, HEIGHT = 1200, 675
INK = "#0B1422"
PANEL = "#111E2D"
EDGE = "#304457"
WHITE = "#ECF3F8"
SOFT = "#A9BED0"
MINT = "#76E5C1"
CORAL = "#FFAD9D"


def font(size: int, *, bold: bool = False, mono: bool = False):
    windows = Path("C:/Windows/Fonts")
    win = ("consolab.ttf" if bold else "consola.ttf") if mono else ("segoeuib.ttf" if bold else "segoeui.ttf")
    linux = "DejaVuSansMono" if mono else "DejaVuSans"
    paths = (
        windows / win,
        Path("/usr/share/fonts/truetype/dejavu") / (linux + ("-Bold.ttf" if bold else ".ttf")),
        Path("/System/Library/Fonts/SFNSMono.ttf" if mono else "/System/Library/Fonts/SFNS.ttf"),
    )
    for path in paths:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


HEADING = font(30, bold=True)
LABEL = font(17, bold=True)
MONO = font(23, mono=True)


def cli(*args: str, cwd: Path, expected: int = 0) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "agent_config_score", *args],
        cwd=cwd,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )
    if result.returncode != expected:
        raise RuntimeError(f"Expected exit {expected} for {args}, got {result.returncode}: {result.stderr.strip()}")
    return result.stdout


def comparison(fixture: Path, rule: str) -> dict:
    report = json.loads(cli(
        "compare", "base", "head", "--fail-on-new-errors", "--max-drop", "0", "--json",
        cwd=fixture, expected=1,
    ))
    if [item["code"] for item in report["new_findings"]] != [rule]:
        raise RuntimeError("Demo output changed. Review the gallery before regenerating it.")
    return report


def setup_checks() -> list[dict]:
    with TemporaryDirectory(prefix="acs-gallery-") as directory:
        root = Path(directory)
        shutil.copyfile(SHELL / "base" / "AGENTS.md", root / "AGENTS.md")
        subprocess.run(["git", "init", "-q", "--template=", "-b", "main"], cwd=root, check=True)
        cli("init", cwd=root)
        for name in (".agentconfigscore.json", ".github/workflows/agent-config-score.yml"):
            if not (root / name).is_file():
                raise RuntimeError(f"Setup did not create {name}")
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(
            ["git", "-c", "user.name=Gallery Fixture", "-c", "user.email=gallery@example.invalid",
             "-c", "core.hooksPath=.git/no-hooks", "-c", "commit.gpgsign=false",
             "commit", "-qm", "Initialize demo repository"],
            cwd=root, check=True,
        )
        subprocess.run(["git", "update-ref", "refs/remotes/origin/main", "HEAD"], cwd=root, check=True)
        report = json.loads(cli("doctor", "--json", cwd=root))
        selected = {"config", "instructions", "baseline", "workflow"}
        checks = [item for item in report["checks"] if item["name"] in selected]
        if len(checks) != len(selected) or any(item["status"] != "pass" for item in checks):
            raise RuntimeError(f"Unexpected doctor results: {checks}")
        return checks


def history_rows() -> list[dict]:
    from agent_config_score.history import append_snapshot

    with TemporaryDirectory(prefix="acs-history-gallery-") as directory:
        root = Path(directory)
        for side in ("base", "head", "base"):
            report = json.loads(cli(str(SHELL / side), "--json", cwd=root))
            append_snapshot(root, {"score": report["score"], "grade": report["grade"]})
        recorded = json.loads(cli("history", "--json", cwd=root))
        return recorded["history"]


def card(draw: ImageDraw.ImageDraw, bounds: tuple[int, int, int, int]) -> None:
    draw.rounded_rectangle(bounds, radius=18, fill=PANEL, outline=EDGE, width=2)


def save_gif(frames: list[Image.Image], durations: list[int], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    # A shared palette avoids color flicker. Retained frames let Pillow encode
    # only changed regions, keeping terminal typing compact without dropping it.
    palette = frames[-1].quantize(colors=256)
    converted = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    converted[0].save(
        output, save_all=True, append_images=converted[1:], duration=durations,
        loop=0, disposal=1, optimize=True,
    )


def render_move(output: Path, report: dict) -> None:
    finding = report["new_findings"][0]
    command = "agent-config-score compare base head"

    def frame(chars: int, step: int) -> Image.Image:
        image, draw = terminal(
            "instruction move", "Same instruction text. Same score. A new path to review.",
            "Reduced example from a merged PR  /  Identical instruction bytes",
        )
        prompt(draw, command[:chars], 191, cursor=step == 0)
        if step >= 1:
            base, head = report["base"], report["head"]
            segments(draw, 86, 254, [
                ("AgentConfigScore regression  ", "text"), (f"{base['grade']} {base['score']}", "green"),
                (" -> ", "muted"), (f"{head['grade']} {head['score']} ({report['delta']:+d})", "green"),
            ])
            segments(draw, 86, 291, [(f"New findings: {len(report['new_findings'])}", "text")])
        if step >= 2:
            segments(draw, 86, 365, [("+ " + finding["severity"].upper().ljust(8), "red"), (finding["code"], "text")])
            segments(draw, 86, 402, [("           Former path  " + finding["file"], "cyan")])
        if step >= 3:
            draw.text((86, 468), "PATH CHANGE  /  IDENTICAL TEXT", font=TERM_LABEL, fill=TERMINAL["muted"])
            segments(draw, 86, 500, [(finding["file"], "amber"), ("  ->  AGENTS.md", "text")])
            result_bar(draw, "REVIEW REQUIRED  /  EXIT 1     •     Approve the intended scope migration", failed=True)
        return image

    frames = [frame(0, 0)]
    durations = [500]
    for chars in range(3, len(command), 3):
        frames.append(frame(chars, 0))
        durations.append(60)
    frames.append(frame(len(command), 0))
    durations.append(450)
    for step in range(1, 4):
        frames.append(frame(len(command), step))
        durations.append(650 if step < 3 else 4000)
    save_gif(frames, durations, output)


TERMINAL = {
    "page": "#07111F", "glow": "#102A43", "window": "#0D1626",
    "chrome": "#162235", "border": "#2C3E55", "text": "#E6EDF3",
    "muted": "#8FA3B8", "green": "#7EE787", "cyan": "#79C0FF",
    "red": "#FF7B72", "amber": "#E3B341",
}
TERM_TITLE = font(34, bold=True)
TERM_SUBTITLE = font(19)
TERM_MONO = font(22, mono=True)
TERM_BOLD = font(22, mono=True, bold=True)
TERM_SMALL = font(18, mono=True)
TERM_LABEL = font(16, bold=True)
TERM_FOOTER = font(17)


def terminal(section: str, subtitle: str, footer: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), TERMINAL["page"])
    draw = ImageDraw.Draw(image)
    draw.ellipse((780, -270, 1370, 340), fill=TERMINAL["glow"])
    draw.text((60, 27), "AgentConfigScore", font=TERM_TITLE, fill=TERMINAL["text"])
    draw.text((62, 73), subtitle, font=TERM_SUBTITLE, fill=TERMINAL["muted"])
    badge = "LOCAL CLI  /  v" + RELEASE
    badge_width = round(draw.textlength(badge, font=TERM_LABEL)) + 30
    draw.rounded_rectangle((1140 - badge_width, 37, 1140, 71), radius=17, fill="#123B32", outline="#286B57")
    draw.text((1155 - badge_width, 44), badge, font=TERM_LABEL, fill=TERMINAL["green"])
    draw.rounded_rectangle((55, 116, 1145, 610), radius=16, fill=TERMINAL["window"], outline=TERMINAL["border"], width=2)
    draw.rounded_rectangle((56, 117, 1144, 163), radius=15, fill=TERMINAL["chrome"])
    draw.rectangle((56, 144, 1144, 163), fill=TERMINAL["chrome"])
    for index, color in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
        x = 80 + index * 26
        draw.ellipse((x, 133, x + 13, 146), fill=color)
    draw.text((600, 130), section, anchor="ma", font=TERM_SUBTITLE, fill=TERMINAL["muted"])
    draw.text((60, 632), footer, font=TERM_FOOTER, fill=TERMINAL["muted"])
    return image, draw


def segments(draw: ImageDraw.ImageDraw, x: int, y: int, parts: list[tuple[str, str]]) -> None:
    for text, color in parts:
        face = TERM_BOLD if color in {"green", "red", "amber"} else TERM_MONO
        draw.text((x, y), text, font=face, fill=TERMINAL[color])
        x += round(draw.textlength(text, font=face))


def prompt(draw: ImageDraw.ImageDraw, text: str, y: int, *, cursor: bool = False) -> None:
    segments(draw, 86, y, [("$ ", "green"), (text, "text")])
    if cursor:
        x = 86 + round(draw.textlength("$ ", font=TERM_BOLD) + draw.textlength(text, font=TERM_MONO)) + 2
        draw.rectangle((x, y + 4, x + 10, y + 26), fill=TERMINAL["cyan"])


def result_bar(draw: ImageDraw.ImageDraw, text: str, *, failed: bool = False) -> None:
    draw.rounded_rectangle(
        (82, 550, 1118, 590), radius=8,
        fill="#291B20" if failed else "#123B32", outline="#71333A" if failed else "#286B57",
    )
    draw.text((101, 560), text, font=TERM_FOOTER, fill=TERMINAL["red" if failed else "green"])


def render_regression(output: Path, report: dict) -> None:
    finding = report["new_findings"][0]
    added_line = (SHELL / "head" / finding["file"]).read_text(encoding="utf-8").splitlines()[finding["line"] - 1]
    command = "agent-config-score compare base head --fail-on-new-errors"
    base, head = report["base"], report["head"]
    lines = [
        [("AgentConfigScore regression  ", "text"), (f"{base['grade']} {base['score']}", "green"),
         (" -> ", "muted"), (f"{head['grade']} {head['score']} ({report['delta']:+d})", "amber")],
        [(f"New findings: {len(report['new_findings'])}", "text"),
         (f"   Resolved: {len(report['resolved_findings'])}   Suppressed: {len(head['suppressed_findings'])}", "muted")],
        [],
        [("+ " + finding["severity"].upper().ljust(8), "red"), (finding["code"], "text")],
        [("           " + finding["message"], "muted")],
        [(f"           {finding['file']}:{finding['line']}", "cyan")],
    ]

    def frame(chars: int, visible: int, *, cursor: bool = False, complete: bool = False) -> Image.Image:
        image, draw = terminal(
            "regression check", "A new risky instruction. A finding you can review.",
            "Local fixture  /  Condensed CLI results  /  Deterministic rules",
        )
        prompt(draw, command[:chars], 191, cursor=cursor)
        for index, line in enumerate(lines[:visible]):
            segments(draw, 86, 254 + index * 37, line)
        if complete:
            draw.text((86, 488), "ADDED IN " + finding["file"], font=TERM_LABEL, fill=TERMINAL["muted"])
            draw.text((86, 513), "+ " + added_line, font=TERM_SMALL, fill=TERMINAL["amber"])
            result_bar(draw, f"NEW ERROR GATE FAILED  /  EXIT 1     •     Review {finding['file']}:{finding['line']}", failed=True)
        return image

    frames = [frame(0, 0, cursor=True)]
    durations = [450]
    for chars in range(3, len(command), 3):
        frames.append(frame(chars, 0, cursor=True))
        durations.append(50)
    frames.append(frame(len(command), 0))
    durations.append(500)
    for visible in range(1, len(lines) + 1):
        frames.append(frame(len(command), visible))
        durations.append(310 if lines[visible - 1] else 140)
    frames.append(frame(len(command), len(lines), complete=True))
    durations.append(3800)
    save_gif(frames, durations, output)


def render_setup(output: Path) -> None:
    checks = setup_checks()
    commands = {
        0: "python -m pip install agent-config-score==" + RELEASE,
        2: "agent-config-score init",
        6: "agent-config-score doctor",
    }
    lines = {
        3: [("  CREATED  ", "cyan"), (".agentconfigscore.json", "text")],
        4: [("  CREATED  ", "cyan"), (".github/workflows/agent-config-score.yml", "text")],
    }
    for index, check in enumerate(checks):
        lines[7 + index] = [("  " + check["status"].upper() + "  ", "green"), (check["name"].ljust(14), "text")]

    def frame(visible: int, typing: tuple[int, int] | None = None) -> Image.Image:
        image, draw = terminal(
            "repository setup", "Install. Initialize. Verify the local integration.",
            "Commit the generated policy and workflow to enable the PR check.",
        )
        for index in range(visible):
            y = 184 + index * 31
            if index in commands:
                prompt(draw, commands[index], y)
            elif index in lines:
                segments(draw, 86, y, lines[index])
                if index >= 7:
                    message = checks[index - 7]["message"]
                    while draw.textlength(message, font=TERM_SMALL) > 705:
                        message = message[:-2].rstrip("…") + "…"
                    draw.text((391, y + 3), message, font=TERM_SMALL, fill=TERMINAL["muted"])
        if typing is not None:
            index, chars = typing
            prompt(draw, commands[index][:chars], 184 + index * 31, cursor=True)
        if visible == 11:
            result_bar(draw, "LOCAL CHECKS PASSED  /  Review and commit the generated files")
        return image

    frames, durations = [], []
    for index in range(11):
        if index in commands:
            for chars in range(0, len(commands[index]), 4):
                frames.append(frame(index, (index, chars)))
                durations.append(350 if chars == 0 else 50)
        frames.append(frame(index + 1))
        durations.append(240 if index in lines else 120)
    durations[-1] = 3600
    save_gif(frames, durations, output)


def render_history(output: Path) -> None:
    rows = history_rows()
    if len(rows) != 3:
        raise RuntimeError(f"Expected three recorded scores, got {rows}")
    labels = ("Baseline", "Risk added", "Risk resolved")
    scores = [row["score"] for row in rows]
    low, high = min(scores) - 2, max(scores)
    points = [(747 + 164 * i, round(467 - (score - low) / (high - low) * 210)) for i, score in enumerate(scores)]

    def frame(visible: int, progress: float = 1.0) -> Image.Image:
        image, draw = terminal(
            "score history", "The change, the record, and the recovery.",
            "Three local fixture snapshots  /  Scores read back with the history command",
        )
        prompt(draw, "agent-config-score history", 190)
        draw.line((663, 246, 663, 515), fill=TERMINAL["border"], width=2)
        draw.text((86, 251), "SNAPSHOT", font=TERM_SMALL, fill=TERMINAL["muted"])
        for x, label in ((355, "SCORE"), (445, "GRADE"), (550, "CHANGE")):
            draw.text((x, 251), label, anchor="ma", font=TERM_SMALL, fill=TERMINAL["muted"])
        draw.text((718, 192), "RECORDED SCORE", font=TERM_LABEL, fill=TERMINAL["muted"])
        for tick in (low, (low + high) // 2, high):
            y = round(467 - (tick - low) / (high - low) * 210)
            draw.line((727, y, 1096, y), fill=TERMINAL["chrome"], width=1)
            draw.text((712, y - 8), str(tick), anchor="ra", font=TERM_SMALL, fill=TERMINAL["muted"])
        for index in range(visible):
            row = rows[index]
            color = "amber" if index == 1 else "green"
            y = 312 + index * 68
            delta = "—" if index == 0 else f"{scores[index] - scores[index - 1]:+d}"
            draw.text((86, y), labels[index], font=TERM_MONO, fill=TERMINAL["text"])
            for x, value in ((355, str(row["score"])), (445, row["grade"]), (550, delta)):
                draw.text((x, y), value, anchor="ma", font=TERM_BOLD, fill=TERMINAL[color])
        for index in range(max(0, visible - 1)):
            start, end = points[index], points[index + 1]
            fraction = progress if index == visible - 2 else 1.0
            current = tuple(round(a + (b - a) * fraction) for a, b in zip(start, end))
            draw.line((start, current), fill=TERMINAL["cyan"], width=4)
        for index, (x, y) in enumerate(points[:visible]):
            if index == visible - 1 and index > 0 and progress < 1:
                continue
            color = TERMINAL["amber" if index == 1 else "green"]
            draw.ellipse((x - 7, y - 7, x + 7, y + 7), fill=color, outline=TERMINAL["text"], width=1)
            draw.text((x, y - 33), str(scores[index]), anchor="ma", font=TERM_BOLD, fill=color)
        for index, label in enumerate(("BASE", "+ RISK", "FIXED")):
            draw.text((points[index][0], 495), label, anchor="ma", font=TERM_LABEL, fill=TERMINAL["muted"])
        if visible == 3 and progress == 1:
            result_bar(draw, f"{scores[0]} → {scores[1]} → {scores[2]}  /  One recognized risk added, then removed")
        return image

    frames = [frame(0), frame(1)]
    durations = [550, 750]
    for visible in (2, 3):
        for step in range(1, 9):
            frames.append(frame(visible, step / 8))
            durations.append(70 if step < 8 else 850)
    durations[-1] = 3800
    save_gif(frames, durations, output)


def render_social(output: Path, report: dict) -> None:
    image = Image.new("RGB", (1280, 640), INK)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1280, 7), fill=MINT)
    draw.text((66, 52), "AGENT CONFIG REVIEW   /   LOCAL STATIC ANALYSIS", font=LABEL, fill=MINT)
    draw.text((62, 96), "AgentConfigScore", font=font(70, bold=True), fill=WHITE)
    draw.text((66, 200), "Same score. New review finding.", font=HEADING, fill=SOFT)
    card(draw, (66, 280, 1214, 534))
    draw.text((94, 310), "REVIEWED BASELINE", font=LABEL, fill=SOFT)
    draw.text((690, 310), "PROPOSED CHANGE", font=LABEL, fill=SOFT)
    draw.text((94, 353), f"docs/AGENTS.md   {report['base']['score']}", font=MONO, fill=WHITE)
    draw.text((690, 353), f"AGENTS.md   {report['head']['score']}", font=MONO, fill=WHITE)
    draw.line((94, 410, 1186, 410), fill=EDGE, width=2)
    draw.text((94, 443), report["new_findings"][0]["code"], font=HEADING, fill=CORAL)
    draw.text((1186, 455), "EXIT 1", anchor="ra", font=LABEL, fill=CORAL)
    draw.text((66, 576), "BASELINE POLICY  /  SOURCE-LOCATED FINDINGS  /  CI REVIEW", font=LABEL, fill=SOFT)
    draw.text((1214, 576), "v" + RELEASE, anchor="ra", font=LABEL, fill=MINT)
    image.save(output, format="PNG", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ASSETS / "agent-config-score-demo.gif")
    parser.add_argument("--all", action="store_true", help="Render all GIFs and the share card")
    args = parser.parse_args()
    if cli("--version", cwd=ROOT).strip() != f"AgentConfigScore {RELEASE}":
        parser.error(f"Install agent-config-score=={RELEASE} in the rendering environment")
    report = comparison(SHELL, "curl-pipe-shell")
    render_regression(args.output, report)
    if args.all:
        render_setup(ASSETS / "agent-config-score-setup.gif")
        render_history(ASSETS / "agent-config-score-history.gif")
        move = comparison(MOVE, "instruction-file-removed")
        render_move(ASSETS / "agent-config-score-instruction-move.gif", move)
        render_social(ASSETS / "agent-config-score-social-preview.png", move)


if __name__ == "__main__":
    main()
