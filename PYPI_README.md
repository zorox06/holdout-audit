# Spliv

**Check your train/test split before trusting your model score.**

Spliv checks two CSV files or pandas DataFrames for exact sample overlap, repeated observations, shared entities, strict time-order violations, and features that copy the target. One command generates an offline HTML report with counts, record references, and practical next steps. JSON export and CI exit codes are included.

**Python 3.10+ · Optional pandas/notebook extras · No API keys · No audit uploads**

## Install and try the demo

```bash
pip install spliv
spliv demo
```

Open `report.html` in your browser. The bundled synthetic demo intentionally produces five flagged checks. Compare it with the repaired example:

```bash
spliv demo --clean --output clean-report.html
```

![Report generated from the synthetic demo](https://raw.githubusercontent.com/zorox06/holdout-audit/main/assets/report-preview.png)

## Google Colab and real training workflows

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/zorox06/holdout-audit/blob/main/examples/colab_quickstart.ipynb)

The notebook runs an actual scikit-learn workflow: load data, demonstrate a contaminated split, audit DataFrames, display the report, and fit a preprocessing/model pipeline only after the audit gate passes.

```python
%pip install -U "spliv[notebook]"

from spliv import audit
from IPython.display import display

# train_df and test_df include the target column from your chosen split.
report = audit(train_df, test_df, target="label")
display(report)
report.raise_for_findings()  # raises AuditFailed before training if review is needed
```

Use `pip install "spliv[pandas]"` outside notebooks for DataFrame support. CSV-only use keeps zero runtime dependencies. Upgrade to **0.2.0+** for these APIs; restart the notebook runtime if an older version was already imported.

Read the [practical recipes](https://github.com/zorox06/holdout-audit/blob/main/docs/workflows.md) for independent rows, customer/patient groups, forecasting, existing X/y splits, row inspection, and saved run artifacts.

DataFrame indexes are ignored; evidence uses 1-based row positions. Comparisons follow `to_csv(index=False)` string semantics, so `1` and `1.0` differ. Audit before fitting preprocessing. Spliv does not upload data, but uploaded Colab data is processed in Google's runtime.

## Audit your own CSVs

```bash
spliv audit train.csv test.csv --target churn --group customer_id --time observed_at --ignore record_id --output audit.html --json audit.json
```

Both files must be UTF-8, comma-delimited CSVs with the same unique, nonblank column names. Column order may differ. Target, entity, timestamp, and ignored columns are excluded from feature matching. Exclude unique record IDs so they do not hide otherwise identical samples. Repeat `--ignore` for additional metadata columns.

## Checks

| Check | Enable |
| --- | --- |
| Exact feature matches across train/test | Always |
| Repeated feature samples within train and within test | Always |
| Nonmissing entity IDs shared across splits | `--group` |
| Every train timestamp strictly before every test timestamp | `--time` |
| Features exactly copying the target across both splits | `--target` |

Feature matching uses exact CSV string equality. `1` and `1.0`, or `a` and ` a`, are distinct. Entity, time, and target completeness treat empty strings and case-insensitive `na`, `n/a`, `nan`, `null`, and `none` as missing. Timestamp parsing uses Python's ISO 8601 parser; mixed naive/aware timestamps are inconclusive. Target-copy checks need complete targets and at least two distinct training target values.

## Python API

```python
from spliv import audit

report = audit("train.csv", "test.csv", target="churn", ignore=("record_id",))
print(report.verdict)
print(report.to_dict())

if report.fails("warning"):
    raise SystemExit(1)
```

## CI behavior

`audit` defaults to `--fail-on warning`. Exit 0 means the chosen gate was met; exit 1 means a finding meets its threshold or a requested check is incomplete; exit 2 means an input, argument, or output error. `--fail-on error` allows complete warning findings. `--fail-on none` disables gating. Reports are still written when the gate fails. Demo commands disable gating unless explicitly requested.

## Privacy and limitations

Generated reports have no external assets or network calls. Raw cell values are not exported. Filenames, column labels, aggregate counts, and up to five record pairs are included; review metadata before sharing. Data record references start at 1 after the header. The tool does not edit input files.

Findings are review signals, not proof of leakage. Identical features and shared entities can be legitimate for some evaluation goals. The tool does not inspect preprocessing code, detect near-duplicates or transformed target proxies, or establish feature availability at prediction time. It reads all rows and holds both files and indexes in memory; use datasets that fit comfortably in RAM.

Read the [full documentation](https://github.com/zorox06/holdout-audit#readme), [report an issue](https://github.com/zorox06/holdout-audit/issues), or [contribute](https://github.com/zorox06/holdout-audit/blob/main/CONTRIBUTING.md).

Built by Akshay Sekhar. MIT licensed.
