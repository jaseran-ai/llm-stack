"""Keep the main-branch ruleset's required checks in sync with the CI job names."""

import json
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]


class RulesetChecksTests(unittest.TestCase):
    def test_required_checks_match_ci_job_names(self):
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
        job_names = set(re.findall(r"^    name: (.+)$", ci, re.M))
        ruleset = json.loads((ROOT / ".github" / "rulesets" / "main.json").read_text())
        status_rule = next(r for r in ruleset["rules"] if r["type"] == "required_status_checks")
        required = {c["context"] for c in status_rule["parameters"]["required_status_checks"]}
        self.assertEqual(required, job_names)

    def test_ruleset_blocks_force_push_and_deletion(self):
        ruleset = json.loads((ROOT / ".github" / "rulesets" / "main.json").read_text())
        types = {r["type"] for r in ruleset["rules"]}
        self.assertTrue({"deletion", "non_fast_forward", "pull_request", "required_status_checks"} <= types)
        self.assertEqual(ruleset["bypass_actors"], [])

    def test_only_rebase_merges_preserve_commit_authors(self):
        # Squash and merge commits are authored by whoever merges the pull request.
        ruleset = json.loads((ROOT / ".github" / "rulesets" / "main.json").read_text())
        pr_rule = next(r for r in ruleset["rules"] if r["type"] == "pull_request")
        self.assertEqual(pr_rule["parameters"]["allowed_merge_methods"], ["rebase"])


if __name__ == "__main__":
    unittest.main()
