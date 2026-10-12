import html
import unittest

from spliv import AuditError, AuditFailed, audit
from test_core import CSVCase

try:
    import pandas as pd
except ImportError:
    pd = None


@unittest.skipIf(pd is None, "optional pandas integration")
class DataFrameTests(CSVCase):
    def test_overlap_ignores_index_preserves_inputs_and_matches_csv(self):
        train = pd.DataFrame({'x': ['secret,a', 'b\nline'], 'y': [0, 1]}, index=[100, 200])
        test = pd.DataFrame({'y': [1, 0], 'x': ['secret,a', 'c']}, index=[800, 100])
        original = train.copy(deep=True)
        report = audit(train, test, target='y')
        train.to_csv(self.root / 'train.csv', index=False)
        test.to_csv(self.root / 'test.csv', index=False)
        csv_report = audit(self.root / 'train.csv', self.root / 'test.csv', target='y')
        self.assertEqual(report.checks, csv_report.checks)
        self.assertEqual(self.check(report, 'sample_overlap').evidence['example_record_pairs'],
                         [{'train_record': 1, 'test_record': 1}])
        pd.testing.assert_frame_equal(train, original)
        self.assertNotIn('secret,a', report.to_html())
        self.assertNotIn('800', str(report.to_dict()))

    def test_nullable_dtypes_missing_entities_are_inconclusive(self):
        train = pd.DataFrame({'x': [1, 2], 'id': pd.Series(['a', pd.NA], dtype='string'),
                              'y': pd.Series([0, 1], dtype='Int64')})
        test = pd.DataFrame({'x': [3], 'id': ['b'], 'y': [0]})
        report = audit(train, test, group='id', target='y')
        self.assertEqual(self.check(report, 'entity_overlap').status, 'inconclusive')
        with self.assertRaises(AuditFailed) as caught:
            report.raise_for_findings('error')
        self.assertIs(caught.exception.report, report)

    def test_datetime_and_categorical_values(self):
        train = pd.DataFrame({'x': pd.Categorical(['a', 'b']), 't': pd.to_datetime(['2024-01-01', '2024-01-02'], utc=True)})
        test = pd.DataFrame({'x': ['c'], 't': pd.to_datetime(['2024-02-01'], utc=True)})
        self.assertEqual(self.check(audit(train, test, time='t'), 'time_order').status, 'pass')

    def test_float_vs_integer_contract_is_not_silent_normalization(self):
        report = audit(pd.DataFrame({'x': [1]}), pd.DataFrame({'x': [1.0]}))
        self.assertEqual(self.check(report, 'sample_overlap').status, 'pass')

    def test_ambiguous_frames_are_rejected(self):
        good = pd.DataFrame({'x': [1]})
        bad_frames = [pd.DataFrame([[1, 2]], columns=['x', 'x']),
                      pd.DataFrame({0: [1]}), pd.DataFrame({' ': [1]}),
                      pd.DataFrame({'x': []}), pd.DataFrame({'x': [[1, 2]]}),
                      pd.DataFrame([[1]], columns=pd.MultiIndex.from_tuples([('x', 'a')]))]
        for bad in bad_frames:
            with self.subTest(columns=str(bad.columns)), self.assertRaises(AuditError):
                audit(bad, good)
        with self.assertRaises(AuditError):
            audit([1, 2], good)

    def test_real_training_split_preserves_metadata_exclusions(self):
        train = pd.DataFrame({'x': [4, 5], 'label': [0, 1], 'id': ['u', 'v'], 'row_id': [1, 2]})
        test = pd.DataFrame({'x': [4], 'label': [1], 'id': ['w'], 'row_id': [3]})
        report = audit(train, test, target='label', group='id', ignore=('row_id',))
        self.assertEqual(report.configuration['features'], ['x'])
        self.assertEqual(self.check(report, 'sample_overlap').status, 'flag')
        self.assertEqual(self.check(report, 'entity_overlap').status, 'pass')


class NotebookReportTests(CSVCase):
    def test_gate_stops_training_and_keeps_report(self):
        report = self.split([('a', 0), ('b', 1)], [('a', 1)], target='y')
        with self.assertRaises(AuditFailed) as caught:
            report.raise_for_findings()
        self.assertIs(caught.exception.report, report)
        self.assertIs(report.raise_for_findings('none'), report)
        with self.assertRaises(ValueError):
            report.raise_for_findings('typo')

    def test_passing_gate_returns_report_and_summary_is_structured(self):
        report = self.split([('a', 0), ('b', 1)], [('c', 1)], target='y')
        self.assertIs(report.raise_for_findings(), report)
        self.assertEqual(len(report.summary()), 6)
        self.assertEqual(report.summary()[0]['status'], 'pass')

    def test_rich_display_is_sandboxed_and_html_is_escaped(self):
        report = self.split([('a', 0), ('b', 1)], [('c', 1)], headers=('x" onload="evil', 'y'), target='y')
        rich = report._repr_html_()
        self.assertIn('sandbox="allow-scripts"', rich)
        self.assertNotIn('allow-same-origin', rich)
        self.assertNotIn('<script>', rich)
        from spliv.render import render_html
        self.assertIn(html.escape(render_html(report, embedded=True), quote=True), rich)
        self.assertIn('type="button" hidden>Print', html.unescape(rich))
        self.assertNotIn('type="button" hidden>Print', report.to_html())


if __name__ == '__main__':
    unittest.main()
