import json
from pathlib import Path
import unittest

from agent_config_score.config import SCHEMA_URL, parse_policy
from agent_config_score.initializer import CONFIG_CONTENT
from agent_config_score.rules import RULES


class ConfigSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        schema_path = Path(__file__).resolve().parents[1] / "schema" / "agentconfigscore.schema.json"
        cls.schema = json.loads(schema_path.read_text(encoding="utf-8"))

    def test_schema_uses_expected_draft_and_canonical_url(self):
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(self.schema["$id"], SCHEMA_URL)
        self.assertFalse(self.schema["additionalProperties"])

    def test_schema_rule_enum_matches_stable_catalog(self):
        rule_schema = self.schema["properties"]["suppressions"]["items"]["properties"]["rule"]
        self.assertEqual(rule_schema["enum"], [rule.code for rule in RULES])

    def test_schema_matches_parser_policy_bounds(self):
        policy = self.schema["properties"]["policy"]["properties"]
        self.assertEqual(policy["max_drop"]["minimum"], 0)
        self.assertEqual(policy["fail_under"]["minimum"], 0)
        self.assertEqual(policy["fail_under"]["maximum"], 100)
        self.assertEqual(policy["fail_on_new_errors"]["type"], "boolean")

    def test_schema_requires_auditable_suppression_fields(self):
        suppression = self.schema["properties"]["suppressions"]["items"]
        self.assertEqual(set(suppression["required"]), {"rule", "reason", "expires"})
        self.assertFalse(suppression["additionalProperties"])
        self.assertEqual(suppression["properties"]["reason"]["maxLength"], 500)
        self.assertEqual(suppression["properties"]["expires"]["format"], "date")
        self.assertTrue(suppression["properties"]["paths"]["uniqueItems"])

    def test_initializer_emits_schema_annotated_parser_valid_config(self):
        data = json.loads(CONFIG_CONTENT)
        self.assertEqual(data["$schema"], SCHEMA_URL)
        policy = parse_policy(data)
        self.assertEqual(policy.max_drop, 0)
        self.assertTrue(policy.fail_on_new_errors)

    def test_parser_accepts_editor_schema_annotation(self):
        policy = parse_policy({"$schema": SCHEMA_URL, "version": 1})
        self.assertEqual(policy.max_drop, 0)


if __name__ == "__main__":
    unittest.main()
