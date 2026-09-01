from pathlib import Path
import struct
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


class VisualAssetContractTests(unittest.TestCase):
    def test_gif_gallery_has_expected_canvas_and_stays_compact(self):
        for name in (
            "agent-config-score-demo.gif",
            "agent-config-score-setup.gif",
            "agent-config-score-history.gif",
        ):
            path = ASSETS / name
            data = path.read_bytes()
            with self.subTest(name=name):
                self.assertIn(data[:6], {b"GIF87a", b"GIF89a"})
                self.assertEqual(struct.unpack("<HH", data[6:10]), (1200, 675))
                self.assertLess(len(data), 800_000)

    def test_workflow_overview_is_accessible_svg(self):
        root = ET.parse(ASSETS / "agent-config-score-workflow.svg").getroot()
        namespace = {"svg": "http://www.w3.org/2000/svg"}
        self.assertEqual(root.attrib["width"], "1200")
        self.assertEqual(root.attrib["height"], "420")
        self.assertIsNotNone(root.find("svg:title", namespace))
        self.assertIsNotNone(root.find("svg:desc", namespace))

    def test_readme_uses_public_gallery_urls(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for name in (
            "agent-config-score-demo.gif",
            "agent-config-score-setup.gif",
            "agent-config-score-history.gif",
            "agent-config-score-workflow.svg",
        ):
            with self.subTest(name=name):
                self.assertIn(
                    f"https://raw.githubusercontent.com/LE0-Lin/AgentConfigScore/main/assets/{name}",
                    readme,
                )

    def test_visual_tour_references_every_asset(self):
        tour = (ROOT / "docs" / "visual-tour.md").read_text(encoding="utf-8")
        for name in (
            "agent-config-score-demo.gif",
            "agent-config-score-setup.gif",
            "agent-config-score-history.gif",
            "agent-config-score-workflow.svg",
        ):
            with self.subTest(name=name):
                self.assertIn(f"../assets/{name}", tour)


if __name__ == "__main__":
    unittest.main()
