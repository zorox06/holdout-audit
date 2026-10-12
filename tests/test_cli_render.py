from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

from holdout_audit import audit
from holdout_audit.cli import main
from holdout_audit.render import render_html, render_json
from test_core import CSVCase


class ReportTests(CSVCase):
    def test_html_escapes_untrusted_headers_and_filenames(self):
        injection = '<script>alert("x")</script>'
        report = self.split([("0", "0"), ("1", "1")], [("0", "0")], headers=(injection, "target"), target="target")
        report.inputs["train"]["name"] = '<img src=x onerror="alert(1)">'
        html = render_html(report)
        self.assertNotIn(injection, html)
        self.assertNotIn('<img src=x', html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;img src=x", html)
        self.assertEqual(html.count("<script>"), 1)  # only the static filter script
        self.assertIn("default-src 'none'", html)

    def test_exports_never_include_cell_values(self):
        secret = "do-not-export-this-value"
        report = self.split([(secret, "a")], [(secret, "b")], headers=("customer", "feature"), group="customer")
        self.assertNotIn(secret, render_html(report))
        self.assertNotIn(secret, render_json(report))

    def test_json_has_strict_versioned_schema_and_evidence(self):
        report = self.split([("a", 0)], [("a", 1)], target="y")
        payload = json.loads(render_json(report))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["verdict"], "review_required")
        self.assertEqual(payload["checks"][0]["evidence"]["affected_test_records"], 1)

    def test_skipped_and_incomplete_checks_remain_visible_in_html(self):
        report = self.split([("a", 0)], [("b", 1)], target="y")
        html = render_html(report)
        self.assertIn("Incomplete", html)
        self.assertIn("Not requested", html)
        self.assertIn("more information", html)
        self.assertIn("No sampling".upper(), html)


class CLITests(CSVCase):
    def invoke(self, args):
        out, error = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(error):
            status = main(args)
        return status, out.getvalue(), error.getvalue()

    def test_demo_produces_real_html_json_and_known_findings(self):
        html, data = self.root / "demo.html", self.root / "demo.json"
        status, output, _ = self.invoke(["demo", "--output", str(html), "--json", str(data)])
        self.assertEqual(status, 0)
        self.assertTrue(html.read_text(encoding="utf-8").startswith("<!doctype html>"))
        report = json.loads(data.read_text(encoding="utf-8"))
        self.assertEqual(report["verdict"], "review_required")
        self.assertEqual(sum(item["status"] == "flag" for item in report["checks"]), 5)
        self.assertEqual(report["checks"][0]["evidence"]["affected_test_records"], 2)
        self.assertIn("review required", output)

    def test_repaired_demo_passes_requested_checks(self):
        data = self.root / "clean.json"
        status, _, _ = self.invoke(["demo", "--clean", "--fail-on", "warning", "--output", str(self.root / "clean.html"), "--json", str(data)])
        self.assertEqual(status, 0)
        report = json.loads(data.read_text(encoding="utf-8"))
        self.assertEqual(report["verdict"], "no_findings")
        self.assertTrue(all(check["status"] == "pass" for check in report["checks"]))

    def test_gate_exit_code_and_report_written_on_failure(self):
        train = self.write("train.csv", ["x"], [("same",)])
        test = self.write("test.csv", ["x"], [("same",)])
        report = self.root / "report.html"
        status, _, _ = self.invoke(["audit", str(train), str(test), "--output", str(report)])
        self.assertEqual(status, 1)
        self.assertTrue(report.exists())

    def test_outputs_cannot_clobber_inputs(self):
        train = self.write("train.csv", ["x"], [("a",)])
        test = self.write("test.csv", ["x"], [("b",)])
        before = train.read_bytes()
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            main(["audit", str(train), str(test), "--output", str(train)])
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(train.read_bytes(), before)

    def test_duplicate_output_paths_rejected(self):
        path = str(self.root / "report")
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["demo", "--output", path, "--json", path])

    def test_missing_file_and_output_directory_return_exit_2(self):
        status, _, error = self.invoke(["audit", str(self.root / "absent.csv"), "test.csv"])
        self.assertEqual(status, 2)
        self.assertIn("cannot read", error)
        status, _, error = self.invoke(["demo", "--output", str(self.root / "absent" / "report.html")])
        self.assertEqual(status, 2)
        self.assertIn("could not be accessed", error)

    def test_module_entrypoint_runs_in_a_fresh_process(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, "-m", "holdout_audit", "demo", "--clean", "--output", str(self.root / "report.html")], cwd=root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no findings", result.stdout)


if __name__ == "__main__":
    unittest.main()
