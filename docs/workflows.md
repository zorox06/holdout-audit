# Use Spliv while building a model

[Open the runnable Colab notebook](https://colab.research.google.com/github/zorox06/holdout-audit/blob/main/examples/colab_quickstart.ipynb)

Run the audit **after choosing a split and before fitting preprocessing or a model**. A passing audit is a limited check of the supplied data, not proof that your features or evaluation design are valid.

## Colab / Jupyter

```python
%pip install -U "spliv[notebook]"
from spliv import audit
from IPython.display import display

report = audit(train_df, test_df, target="label")
display(report)
report.raise_for_findings()
```

Use `pip install "spliv[pandas]"` in a regular training environment if you only need DataFrame support. Plain `pip install spliv` still supports CSV files without runtime dependencies. If you already imported an older version in a notebook, restart the runtime after upgrading and rerun the cells.

Spliv does not upload data. A Colab notebook runs in Google's environment: uploaded data lives there, not exclusively on your computer. Use local Jupyter for data that must remain on your machine.

## Independent rows: split, audit, then fit

This recipe assumes `df` is a pandas DataFrame and `label` is its classification target. Avoid random row splits for related observations or forecasting.

```python
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from spliv import audit

train, test = train_test_split(df, test_size=0.2, random_state=42, stratify=df["label"])
report = audit(train, test, target="label", ignore=("record_id",))
report.raise_for_findings()  # stops here on flagged or incomplete requested checks

# Exclusions affect the audit only. Remove metadata from model inputs yourself.
features = [c for c in df.columns if c not in ("label", "record_id")]
model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
model.fit(train[features], train["label"])
score = model.score(test[features], test["label"])
```

This estimator expects numeric features. For categorical data use an appropriate `ColumnTransformer` inside the pipeline. For regression, use a regression estimator and omit classification stratification. Fit imputers, encoders, feature selectors, and scalers inside the training pipeline. Spliv cannot detect whether preprocessing was already fitted on holdout data. [scikit-learn's leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage) explains this boundary.

## New customers, users, or patients: split by entity

```python
from sklearn.model_selection import GroupShuffleSplit
from spliv import audit

splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
train_idx, test_idx = next(splitter.split(df, groups=df["customer_id"]))
train, test = df.iloc[train_idx], df.iloc[test_idx]
report = audit(train, test, target="label", group="customer_id", ignore=("record_id",))
report.raise_for_findings()
```

This evaluates unseen entities. Shared entities may be intentional when predicting future behavior for existing customers. Choose the evaluation goal first. Missing entity IDs make the requested check incomplete.

## Forecasting: hold out future observations

```python
import pandas as pd
from spliv import audit

data = df.copy()
data["observed_at"] = pd.to_datetime(data["observed_at"], utc=True, errors="raise")
cutoff = pd.Timestamp("2025-01-01", tz="UTC")  # choose a boundary appropriate to your data
train = data[data["observed_at"] < cutoff]
test = data[data["observed_at"] >= cutoff]
report = audit(train, test, target="label", time="observed_at", ignore=("record_id",))
report.raise_for_findings()
```

Both splits must be nonempty. Tied timestamps across the boundary are flagged. The time check cannot establish when labels or features became available; delayed labels may require an embargo/gap. If customers legitimately repeat through time, requesting disjoint entities would impose a different evaluation goal.

## Already have X_train, X_test, y_train, y_test?

For pandas Series labels, check index alignment before assigning them. Do not silently reset/reorder labels.

```python
assert X_train.index.equals(y_train.index), "Training labels are misaligned"
assert X_test.index.equals(y_test.index), "Test labels are misaligned"
assert "__target__" not in X_train and "__target__" not in X_test
train = X_train.assign(__target__=y_train)
test = X_test.assign(__target__=y_test)
report = audit(train, test, target="__target__")
report.raise_for_findings()
```

For NumPy inputs, explicitly construct DataFrames with the same feature names and positionally aligned labels first. Spliv does not infer feature names or label alignment from arrays.

## Investigate findings, don't automatically delete data

```python
import pandas as pd
display(pd.DataFrame(report.summary()))
overlap = next(c for c in report.checks if c.code == "sample_overlap")
for pair in overlap.evidence["example_record_pairs"]:
    # Inspect privately; this displays raw rows in your notebook.
    display(train.iloc[[pair["train_record"] - 1]])
    display(test.iloc[[pair["test_record"] - 1]])
```

Record references are 1-based row positions, independent of pandas index labels. At most five example pairs are included; aggregate counts cover all records. DataFrame indexes are not compared. Promote a meaningful index to a named column with `reset_index()` and select it as `group` or `time` if appropriate.

`report.raise_for_findings()` raises `spliv.AuditFailed`, with the report available as `exception.report`. The default warning gate blocks every flagged or incomplete requested check. Use `"error"` only when your evaluation goal permits complete warning findings. `"none"` explicitly disables the gate.

## Save reports with a training run

```python
from pathlib import Path
import json

Path("split-report.html").write_text(report.to_html(), encoding="utf-8")
Path("split-report.json").write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
```

Write artifacts before calling the gate if you want them even when training is blocked. Store them alongside the dataset version, split seed, feature list, and model configuration. Do not use an input filename as an output path.

## DataFrame comparison contract

The adapter reads DataFrames in memory with the same behavior as [`to_csv(index=False)`](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_csv.html), then runs the CSV audit engine. It writes no temporary CSV files and does not mutate the DataFrames.

- Flat, unique, nonblank string column names and scalar cells are required; nested values and MultiIndex columns are rejected.
- Index labels are ignored. Missing cells become empty strings; `NA`, `null`, and the other documented missing markers still apply to metadata checks.
- Matching is exact serialized string equality: `1` and `1.0` differ, as do differently formatted equivalent timestamps used as features. Normalize intended types consistently yourself; no automatic conversion is claimed.
- Both splits and their serialized representations must fit in memory. This is not a streaming audit or a general schema/type validator.
- The target-copy check finds exact copies only. It cannot detect transformed target proxies, future-derived features, near-duplicates, preprocessing leakage, or label misalignment.
