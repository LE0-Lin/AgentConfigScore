"""Execute the copy-ready comment script against a fake GitHub client."""

import json
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
WORKFLOW = ROOT / "examples" / "pr-comment.yml"


@unittest.skipUnless(NODE, "Node.js is required to verify the optional workflow script")
class PrCommentTests(unittest.TestCase):
    def run_script(self, comments=None, overrides=None):
        lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
        start = lines.index("          script: |") + 1
        script = "\n".join(line[12:] for line in lines[start:])
        env = {
            "ACS_BASE_SCORE": "100", "ACS_HEAD_SCORE": "82", "ACS_DELTA": "-18",
            "ACS_NEW_FINDINGS": "1", "ACS_NEW_ERRORS": "1", "ACS_RESOLVED": "0",
            "ACS_OUTCOME": "failure", "GITHUB_SERVER_URL": "https://github.com",
        }
        env.update(overrides or {})
        harness = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const calls = [];
const context = {repo: {owner: 'owner', repo: 'repo'}, issue: {number: 7}, runId: 123};
const github = {
  rest: {issues: {
    listComments: 'listComments',
    createComment: async args => calls.push({operation: 'create', ...args}),
    updateComment: async args => calls.push({operation: 'update', ...args}),
  }},
  paginate: async (endpoint, args) => {
    calls.push({operation: 'list', ...args});
    return input.comments;
  },
};
(async () => {
  let error = null;
  try {
    const sandbox = {github, context, process: {env: input.env}};
    await vm.runInNewContext('(async () => {' + input.script + '\n})()', sandbox);
  } catch (exception) { error = exception.message; }
  process.stdout.write(JSON.stringify({calls, error}));
})();
"""
        completed = subprocess.run(
            [NODE, "-e", harness],
            input=json.dumps({"script": script, "env": env, "comments": comments or []}),
            text=True, encoding="utf-8", capture_output=True, check=True,
        )
        return json.loads(completed.stdout)

    def test_first_blocked_run_creates_result_with_details_link(self):
        result = self.run_script()
        self.assertIsNone(result["error"])
        call = result["calls"][-1]
        self.assertEqual(call["operation"], "create")
        self.assertEqual(call["issue_number"], 7)
        self.assertIn("Blocked", call["body"])
        self.assertIn("100 → 82 (-18)", call["body"])
        self.assertIn("https://github.com/owner/repo/actions/runs/123", call["body"])

    def test_rerun_updates_bot_comment_after_many_user_comments(self):
        comments = [{"id": i, "body": "discussion", "user": {"type": "User"}}
                    for i in range(150)]
        comments.append({"id": 999, "body": "<!-- agent-config-score:regression -->old",
                         "user": {"type": "Bot", "login": "github-actions[bot]"}})
        result = self.run_script(comments)
        self.assertIsNone(result["error"])
        self.assertEqual(result["calls"][-1]["operation"], "update")
        self.assertEqual(result["calls"][-1]["comment_id"], 999)

    def test_user_or_other_bot_marker_does_not_claim_comment(self):
        for user in [{"type": "User", "login": "maintainer"},
                     {"type": "Bot", "login": "another[bot]"}]:
            with self.subTest(user=user):
                result = self.run_script([{
                    "id": 77, "body": "<!-- agent-config-score:regression -->", "user": user,
                }])
                self.assertEqual(result["calls"][-1]["operation"], "create")

    def test_identical_result_performs_no_write(self):
        body = self.run_script()["calls"][-1]["body"]
        result = self.run_script([{
            "id": 99, "body": body,
            "user": {"type": "Bot", "login": "github-actions[bot]"},
        }])
        self.assertIsNone(result["error"])
        self.assertEqual([call["operation"] for call in result["calls"]], ["list"])

    def test_successful_fix_shows_signed_improvement(self):
        result = self.run_script(overrides={
            "ACS_BASE_SCORE": "82", "ACS_HEAD_SCORE": "100", "ACS_DELTA": "18",
            "ACS_NEW_FINDINGS": "0", "ACS_NEW_ERRORS": "0",
            "ACS_RESOLVED": "1", "ACS_OUTCOME": "success",
        })
        self.assertIn("Passed", result["calls"][-1]["body"])
        self.assertIn("82 → 100 (+18)", result["calls"][-1]["body"])

    def test_invalid_outputs_stop_before_any_api_call(self):
        for overrides in [
            {"ACS_HEAD_SCORE": "$(malicious)"}, {"ACS_HEAD_SCORE": "101"},
            {"ACS_NEW_ERRORS": "2"}, {"ACS_DELTA": "0"},
            {"ACS_NEW_FINDINGS": "9007199254740992"}, {"ACS_OUTCOME": "cancelled"},
        ]:
            with self.subTest(overrides=overrides):
                result = self.run_script(overrides=overrides)
                self.assertIsNotNone(result["error"])
                self.assertEqual(result["calls"], [])

    def test_rule_breakdown_is_sorted_and_keeps_review_actionable(self):
        rows = [{"code": "dead-path", "severity": "warning", "count": 2},
                {"code": "rm-rf", "severity": "error", "count": 1}]
        result = self.run_script(overrides={"ACS_NEW_FINDINGS": "3", "ACS_NEW_RULE_COUNTS": json.dumps(rows)})
        self.assertIsNone(result["error"])
        body = result["calls"][-1]["body"]
        self.assertIn("| error | `rm-rf` | 1 |", body)
        self.assertIn("| warning | `dead-path` | 2 |", body)
        self.assertLess(body.index("`rm-rf`"), body.index("`dead-path`"))
        self.assertIn("agent-config-score diff --explain", body)
        self.assertIn("same baseline", body)

    def test_legacy_action_remains_usable_without_breakdown(self):
        result = self.run_script()
        self.assertIsNone(result["error"])
        self.assertIn("Rule breakdown unavailable", result["calls"][-1]["body"])

    def test_passing_with_new_warnings_still_asks_for_review(self):
        result = self.run_script(overrides={"ACS_BASE_SCORE": "100", "ACS_HEAD_SCORE": "96", "ACS_DELTA": "-4",
            "ACS_NEW_ERRORS": "0", "ACS_OUTCOME": "success",
            "ACS_NEW_RULE_COUNTS": json.dumps([{"code": "dead-path", "severity": "warning", "count": 1}])})
        self.assertIsNone(result["error"])
        body = result["calls"][-1]["body"]
        self.assertIn("**Passed**", body)
        self.assertIn("gate passed with new findings", body)

    def test_empty_and_large_breakdowns_are_not_misrepresented(self):
        clean = self.run_script(overrides={"ACS_NEW_FINDINGS": "0", "ACS_NEW_ERRORS": "0", "ACS_NEW_RULE_COUNTS": "[]"})
        self.assertIn("No new rule matches", clean["calls"][-1]["body"])
        rows = [{"code": code, "severity": "warning", "count": 1} for code in
                ("sudo", "dead-path", "chmod-777", "duplication", "high-duplication", "context-large", "context-too-large")]
        large = self.run_script(overrides={"ACS_NEW_FINDINGS": "7", "ACS_NEW_ERRORS": "0", "ACS_NEW_RULE_COUNTS": json.dumps(rows)})
        self.assertIsNone(large["error"])
        body = large["calls"][-1]["body"]
        self.assertIn("2 additional rule types", body)
        self.assertEqual(body.count("| warning |"), 5)

    def test_invalid_rule_payloads_stop_before_github_reads_or_writes(self):
        good = {"code": "rm-rf", "severity": "error", "count": 1}
        payloads = ("not JSON", "null", "{}", "[]", "x" * 16385,
            json.dumps([good] * 65), json.dumps([good, good]),
            json.dumps([{**good, "code": "@someone"}]),
            json.dumps([{**good, "code": "[link](https://example.invalid)"}]),
            json.dumps([{**good, "severity": "critical"}]),
            json.dumps([{**good, "count": True}]), json.dumps([{**good, "count": 1.5}]),
            json.dumps([{**good, "count": -1}]), json.dumps([{**good, "count": 9007199254740992}]),
            json.dumps([{**good, "severity": "warning"}]),
            json.dumps([{**good, "file": "sensitive-file", "message": "must never be rendered"}]))
        for payload in payloads:
            with self.subTest(payload=payload[:80]):
                result = self.run_script(overrides={"ACS_NEW_RULE_COUNTS": payload})
                self.assertIsNotNone(result["error"])
                self.assertEqual(result["calls"], [])
                self.assertNotIn("must never be rendered", result["error"])
