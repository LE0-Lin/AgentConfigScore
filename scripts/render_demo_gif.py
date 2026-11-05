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


TITLE = font(44, bold=True)
HEADING = font(30, bold=True)
TEXT = font(23)
LABEL = font(17, bold=True)
MONO = font(23, mono=True)
SCORE = font(52, bold=True)


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


def comparison() -> dict:
    report = json.loads(cli("compare", "base", "head", "--json", cwd=MOVE, expected=1))
    if [item["code"] for item in report["new_findings"]] != ["instruction-file-removed"]:
        raise RuntimeError("Instruction-move demo output changed. Review the gallery before regenerating it.")
    return report


def setup_checks() -> list[tuple[str, str]]:
    with TemporaryDirectory(prefix="acs-gallery-") as directory:
        root = Path(directory)
        shutil.copyfile(SHELL / "base" / "AGENTS.md", root / "AGENTS.md")
        subprocess.run(["git", "init", "-q", "--template=", "-b", "main"], cwd=root, check=True)
        cli("init", cwd=root)
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
        checks = [(item["name"], item["status"]) for item in report["checks"] if item["name"] in selected]
        if len(checks) != len(selected) or any(status != "pass" for _, status in checks):
            raise RuntimeError(f"Unexpected doctor results: {checks}")
        return checks


def history_scores() -> list[int]:
    from agent_config_score.history import append_snapshot

    with TemporaryDirectory(prefix="acs-history-gallery-") as directory:
        root = Path(directory)
        for side in ("base", "head", "base"):
            report = json.loads(cli(str(SHELL / side), "--json", cwd=root))
            append_snapshot(root, {"score": report["score"], "grade": report["grade"]})
        recorded = json.loads(cli("history", "--json", cwd=root))
        return [row["score"] for row in recorded["history"]]


def canvas(section: str, headline: str, detail: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), INK)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 7), fill=MINT)
    draw.text((58, 39), "AGENTCONFIGSCORE  /  " + section, font=LABEL, fill=MINT)
    draw.text((1142, 39), "v" + RELEASE, anchor="ra", font=LABEL, fill=SOFT)
    draw.text((56, 81), headline, font=TITLE, fill=WHITE)
    draw.text((58, 146), detail, font=TEXT, fill=SOFT)
    return image, draw


def card(draw: ImageDraw.ImageDraw, bounds: tuple[int, int, int, int]) -> None:
    draw.rounded_rectangle(bounds, radius=18, fill=PANEL, outline=EDGE, width=2)


def save_gif(frames: list[Image.Image], durations: list[int], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    palette = [frame.quantize(colors=128) for frame in frames]
    palette[0].save(output, save_all=True, append_images=palette[1:], duration=durations, loop=0, disposal=2, optimize=True)


def render_regression(output: Path, report: dict) -> None:
    finding = report["new_findings"][0]
    frames = []
    for step in range(3):
        image, draw = canvas("REGRESSION REVIEW", "Same score. New finding.", "An instruction file moves to the repository root.")
        for x, name, path, score in (
            (58, "REVIEWED BASELINE", "docs/AGENTS.md", report["base"]["score"]),
            (616, "PROPOSED CHANGE", "AGENTS.md", report["head"]["score"]),
        ):
            card(draw, (x, 205, x + 526, 369))
            draw.text((x + 24, 226), name, font=LABEL, fill=SOFT)
            draw.text((x + 24, 282), path, font=MONO, fill=WHITE)
            if step >= 1:
                draw.text((x + 496, 300), str(score), anchor="rm", font=SCORE, fill=MINT)
        card(draw, (58, 396, 1142, 584))
        draw.text((82, 416), "$ agent-config-score compare base head", font=MONO, fill=WHITE)
        if step == 2:
            draw.text((82, 471), finding["code"], font=HEADING, fill=CORAL)
            draw.text((82, 524), "Former path  " + finding["file"], font=TEXT, fill=SOFT)
            draw.text((1115, 524), "REVIEW REQUIRED  /  EXIT 1", anchor="ra", font=LABEL, fill=CORAL)
        draw.text((58, 620), "Reduced example from a merged PR  •  Identical instruction bytes", font=LABEL, fill=SOFT)
        frames.append(image)
    save_gif(frames, [1050, 1300, 4500], output)


def render_setup(output: Path) -> None:
    checks = setup_checks()
    frames = []
    for step in range(3):
        image, draw = canvas("QUICK START", "Install. Initialize. Verify.", "A local check confirms the files, policy, and Git baseline.")
        card(draw, (58, 205, 1142, 586))
        draw.text((82, 231), "$ python -m pip install agent-config-score==" + RELEASE, font=MONO, fill=WHITE)
        if step >= 1:
            draw.text((82, 295), "$ agent-config-score init", font=MONO, fill=WHITE)
            draw.text((82, 337), ".agentconfigscore.json  +  GitHub workflow", font=TEXT, fill=MINT)
        if step >= 2:
            draw.text((82, 399), "$ agent-config-score doctor", font=MONO, fill=WHITE)
            for index, (name, status) in enumerate(checks):
                column, row = divmod(index, 2)
                draw.text((82 + 485 * column, 461 + 47 * row), f"{status.upper()}  {name}", font=MONO, fill=MINT)
        draw.text((58, 620), "Commit the generated policy and workflow to enable the PR check.", font=LABEL, fill=SOFT)
        frames.append(image)
    save_gif(frames, [1200, 1450, 4200], output)


def render_history(output: Path) -> None:
    scores = history_scores()
    if len(scores) != 3:
        raise RuntimeError(f"Expected three recorded scores, got {scores}")
    frames = []
    for visible in range(1, len(scores) + 1):
        image, draw = canvas("SCORE HISTORY", "Follow the change over time.", "$ agent-config-score history")
        card(draw, (58, 206, 1142, 586))
        points = [(224 + 376 * i, 352 + (max(scores) - score) * 6) for i, score in enumerate(scores)]
        if visible > 1:
            draw.line(points[:visible], fill=MINT, width=4)
        for index, (x, y) in enumerate(points[:visible]):
            draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill=MINT if index != 1 else CORAL)
            draw.text((x, y - 66), str(scores[index]), anchor="ma", font=SCORE, fill=WHITE)
        for index, label in enumerate(("Baseline", "Risk added", "Risk resolved")):
            draw.text((224 + 376 * index, 526), label, anchor="ma", font=TEXT, fill=SOFT)
        draw.text((58, 620), "Three recorded scores from the local regression fixture", font=LABEL, fill=SOFT)
        frames.append(image)
    save_gif(frames, [900, 1150, 4000], output)


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
    report = comparison()
    render_regression(args.output, report)
    if args.all:
        render_setup(ASSETS / "agent-config-score-setup.gif")
        render_history(ASSETS / "agent-config-score-history.gif")
        render_social(ASSETS / "agent-config-score-social-preview.png", report)


if __name__ == "__main__":
    main()
