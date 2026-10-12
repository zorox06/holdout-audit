import csv
import random
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from holdout_audit import AuditError, audit
from holdout_audit.core import read_csv


class CSVCase(unittest.TestCase):
    def setUp(self):
        # Keep test data in the checkout; suitable for restricted Windows environments.
        self.root = Path(__file__).resolve().parents[1] / ".test-tmp" / uuid4().hex
        self.root.mkdir(parents=True)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        boundary = Path(__file__).resolve().parents[1] / ".test-tmp"
        if self.root.resolve().parent != boundary.resolve():
            raise RuntimeError("Test cleanup path is outside .test-tmp")
        shutil.rmtree(self.root)

    def write(self, name, headers, rows):
        path = self.root / name
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(headers)
            writer.writerows(rows)
        return path

    def split(self, train, test, headers=("x", "y"), **options):
        left = self.write("train.csv", headers, train)
        right = self.write("test.csv", headers, test)
        return audit(left, right, **options)

    @staticmethod
    def check(report, code):
        return next(check for check in report.checks if check.code == code)


class AuditTests(CSVCase):
    def test_overlap_excludes_target_and_counts_records_not_pairs(self):
        report = self.split([("same", "0"), ("same", "1"), ("other", "1")],
                            [("same", "0"), ("same", "0"), ("new", "1")], target="y")
        check = self.check(report, "sample_overlap")
        self.assertEqual(check.evidence["shared_unique_samples"], 1)
        self.assertEqual(check.evidence["affected_test_records"], 2)
        self.assertEqual(check.evidence["affected_train_records"], 2)
        self.assertEqual(check.evidence["example_record_pairs"], [{"train_record": 1, "test_record": 1}])
        self.assertEqual(report.verdict, "review_required")
        self.assertTrue(report.fails("error"))

    def test_feature_comparison_is_exact(self):
        report = self.split([("1", "0"), (" a", "1")], [("1.0", "0"), ("a", "1")], target="y")
        self.assertEqual(self.check(report, "sample_overlap").status, "pass")

    def test_schema_order_does_not_change_matches(self):
        left = self.write("train.csv", ["x", "y"], [("a", "0"), ("b", "1")])
        right = self.write("test.csv", ["y", "x"], [("1", "a"), ("0", "c")])
        report = audit(left, right, target="y")
        self.assertEqual(self.check(report, "sample_overlap").evidence["affected_test_records"], 1)

    def test_schema_mismatch_is_an_error(self):
        left = self.write("train.csv", ["x", "y"], [(1, 0)])
        right = self.write("test.csv", ["x", "z"], [(2, 1)])
        with self.assertRaisesRegex(AuditError, "same named columns"):
            audit(left, right)

    def test_duplicate_counts_exclude_first_occurrence(self):
        report = self.split([("a", 0), ("a", 1), ("a", 0), ("b", 1)], [("c", 0), ("c", 1)], target="y")
        self.assertEqual(self.check(report, "train_duplicates").evidence["repeated_records"], 2)
        self.assertEqual(self.check(report, "test_duplicates").evidence["repeated_records"], 1)
        self.assertTrue(report.fails("warning"))
        self.assertFalse(report.fails("error"))

    def test_unconfigured_optional_checks_are_skipped(self):
        report = self.split([("a", 0)], [("b", 1)])
        self.assertEqual(report.verdict, "no_findings")
        self.assertFalse(report.fails())
        self.assertEqual(sum(check.status == "skipped" for check in report.checks), 3)

    def test_unknown_columns_and_no_features_are_rejected(self):
        for options in ({"target": "missing"}, {"ignore": ("missing",)}, {"target": "x", "group": "y"}):
            with self.subTest(options=options), self.assertRaises(AuditError):
                self.split([("a", 0)], [("b", 1)], **options)

    def test_metadata_roles_must_be_distinct(self):
        with self.assertRaisesRegex(AuditError, "distinct"):
            self.split([("a", 0)], [("b", 1)], target="y", group="y")

    def test_entity_ids_excluded_from_sample_keys(self):
        report = self.split([("1", "a", 0), ("2", "b", 1)], [("3", "a", 0)],
                            headers=("entity", "x", "y"), group="entity", target="y")
        self.assertEqual(self.check(report, "sample_overlap").status, "flag")
        self.assertEqual(self.check(report, "entity_overlap").status, "pass")

    def test_entity_overlap_reports_coverage_without_raw_ids(self):
        secret = "private-customer-id"
        report = self.split([(secret, "a"), ("", "b")], [(secret, "c"), ("other", "d")],
                            headers=("entity", "x"), group="entity")
        check = self.check(report, "entity_overlap")
        self.assertEqual(check.status, "flag")
        self.assertEqual(check.evidence["shared_entities"], 1)
        self.assertEqual(check.evidence["missing_train_ids"], 1)
        self.assertFalse(check.complete)
        self.assertTrue(report.fails("error"))
        self.assertNotIn(secret, str(report.to_dict()))

    def test_missing_entity_without_overlap_is_inconclusive(self):
        report = self.split([("NULL", "a")], [("new", "b")], headers=("entity", "x"), group="entity")
        self.assertEqual(self.check(report, "entity_overlap").status, "inconclusive")
        self.assertEqual(report.verdict, "inconclusive")
        self.assertTrue(report.fails("error"))
        self.assertFalse(report.fails("none"))

    def test_strict_future_time_passes(self):
        report = self.split([("2026-01-01", "a")], [("2026-02-01", "b")], headers=("date", "x"), time="date")
        self.assertEqual(self.check(report, "time_order").status, "pass")

    def test_equal_time_boundary_is_flagged(self):
        report = self.split([("2026-01-01", "a")], [("2026-01-01", "b")], headers=("date", "x"), time="date")
        self.assertEqual(self.check(report, "time_order").status, "flag")

    def test_timezones_are_compared_as_instants(self):
        report = self.split([("2026-01-01T00:00:00+05:30", "a")], [("2025-12-31T20:00:00Z", "b")],
                            headers=("date", "x"), time="date")
        self.assertEqual(self.check(report, "time_order").status, "pass")

    def test_invalid_or_missing_times_do_not_pass(self):
        for value in ("not-a-date", "", "2026-13-01", "2026-02-30"):
            with self.subTest(value=value):
                report = self.split([(value, "a")], [("2026-02-01", "b")], headers=("date", "x"), time="date")
                self.assertEqual(self.check(report, "time_order").status, "inconclusive")
                self.assertTrue(report.fails("error"))

    def test_mixed_timezone_awareness_is_inconclusive(self):
        report = self.split([("2026-01-01", "a")], [("2026-02-01T00:00:00Z", "b")], headers=("date", "x"), time="date")
        self.assertTrue(self.check(report, "time_order").evidence["mixed_timezone_awareness"])
        self.assertEqual(self.check(report, "time_order").status, "inconclusive")

    def test_target_copy_requires_match_in_both_splits(self):
        report = self.split([("0", "a", "0"), ("1", "b", "1")], [("0", "c", "0")],
                            headers=("copy", "feature", "y"), target="y")
        self.assertEqual(self.check(report, "target_copy").evidence["matching_columns"], ["copy"])
        altered = self.split([("0", "a", "0"), ("1", "b", "1")], [("1", "c", "0")],
                             headers=("copy", "feature", "y"), target="y")
        self.assertEqual(self.check(altered, "target_copy").status, "pass")

    def test_constant_and_missing_targets_are_inconclusive(self):
        for targets in (("0", "0"), ("0", "")):
            with self.subTest(targets=targets):
                report = self.split([("a", targets[0]), ("b", targets[1])], [("c", "1")], target="y")
                self.assertEqual(self.check(report, "target_copy").status, "inconclusive")

    def test_ignore_removes_record_ids_that_would_hide_duplicates(self):
        report = self.split([("id1", "same", "0"), ("id2", "other", "1")], [("id3", "same", "1")],
                            headers=("id", "x", "y"), target="y", ignore=("id",))
        self.assertEqual(self.check(report, "sample_overlap").evidence["affected_test_records"], 1)

    def test_overlap_matches_bruteforce_oracle_for_random_splits(self):
        rng = random.Random(812)
        for _ in range(60):
            train = [(str(rng.randrange(20)), str(rng.randrange(2))) for _ in range(rng.randrange(1, 35))]
            test = [(str(rng.randrange(20)), str(rng.randrange(2))) for _ in range(rng.randrange(1, 35))]
            report = self.split(train, test)
            expected = sum(any(item == row for row in train) for item in test)
            self.assertEqual(self.check(report, "sample_overlap").evidence["affected_test_records"], expected)
            self.assertEqual(self.check(report, "train_duplicates").evidence["repeated_records"], len(train) - len(set(train)))

    def test_report_is_deterministic(self):
        left = self.write("train.csv", ["x"], [("c",), ("b",), ("a",)])
        right = self.write("test.csv", ["x"], [("a",), ("c",)])
        self.assertEqual(audit(left, right).to_dict(), audit(left, right).to_dict())


class ParsingTests(CSVCase):
    def test_empty_and_header_only_inputs_are_rejected(self):
        for content in ("", "x,y\n"):
            path = self.root / "input.csv"
            path.write_text(content, encoding="utf-8")
            with self.subTest(content=content), self.assertRaises(AuditError):
                read_csv(path)

    def test_duplicate_blank_and_ragged_headers_records_are_rejected(self):
        for content in ("x,x\n1,2\n", "x, \n1,2\n", "x,y\n1\n", "x,y\n1,2,3\n", 'x,y\n"unterminated,2\n'):
            path = self.root / "input.csv"
            path.write_text(content, encoding="utf-8")
            with self.subTest(content=content), self.assertRaises(AuditError):
                read_csv(path)

    def test_bom_multiline_and_quoted_commas_are_supported(self):
        path = self.root / "input.csv"
        path.write_bytes('\ufeffx,y\n"hello, world","line1\nline2"\n'.encode("utf-8"))
        table = read_csv(path)
        self.assertEqual(table.headers, ("x", "y"))
        self.assertEqual(table.rows, (("hello, world", "line1\nline2"),))

    def test_invalid_encoding_and_missing_files_return_safe_errors(self):
        path = self.root / "input.csv"
        path.write_bytes(b"x\n\xffprivate-value")
        with self.assertRaises(AuditError) as caught:
            read_csv(path)
        self.assertNotIn("private-value", str(caught.exception))
        with self.assertRaises(AuditError):
            read_csv(self.root / "absent.csv")
