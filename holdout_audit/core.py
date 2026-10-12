"""CSV validation and split checks. Reports never contain raw cell values."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MISSING = frozenset({"", "na", "n/a", "nan", "null", "none"})


class AuditError(ValueError):
    """An input cannot be audited without guessing its structure."""


@dataclass(frozen=True)
class Table:
    name: str
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

    def column(self, name: str) -> tuple[str, ...]:
        index = self.headers.index(name)
        return tuple(row[index] for row in self.rows)


@dataclass(frozen=True)
class Check:
    code: str
    title: str
    status: str
    severity: str
    summary: str
    evidence: dict[str, Any]
    recommendation: str
    complete: bool = True


@dataclass(frozen=True)
class Report:
    inputs: dict[str, Any]
    configuration: dict[str, Any]
    checks: tuple[Check, ...]

    @property
    def verdict(self) -> str:
        if any(check.status == "flag" for check in self.checks):
            return "review_required"
        if any(check.status == "inconclusive" for check in self.checks):
            return "inconclusive"
        return "no_findings"

    def fails(self, threshold: str = "warning") -> bool:
        if threshold not in {"none", "warning", "error"}:
            raise ValueError("threshold must be none, warning, or error")
        if threshold == "none":
            return False
        levels = {"info": 0, "warning": 1, "error": 2}
        return any(
            check.status == "inconclusive"
            or (check.status == "flag" and levels[check.severity] >= levels[threshold])
            or (check.status != "skipped" and not check.complete)
            for check in self.checks
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "tool_version": "0.1.0",
            "verdict": self.verdict,
            "inputs": self.inputs,
            "configuration": self.configuration,
            "checks": [asdict(check) for check in self.checks],
        }


def _missing(value: str) -> bool:
    return value.strip().casefold() in MISSING


def read_csv(path: str | Path) -> Table:
    """Read an entire UTF-8 CSV; reject ambiguous headers and record widths."""
    path = Path(path)
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream, strict=True)
            headers = next(reader, None)
            if not headers or any(not name.strip() for name in headers):
                raise AuditError(f"{path.name}: a nonempty header is required")
            if len(set(headers)) != len(headers):
                raise AuditError(f"{path.name}: duplicate column names are ambiguous")
            rows = []
            for number, row in enumerate(reader, 1):
                if len(row) != len(headers):
                    raise AuditError(
                        f"{path.name}: data record {number} has {len(row)} fields; "
                        f"expected {len(headers)}"
                    )
                rows.append(tuple(row))
            if not rows:
                raise AuditError(f"{path.name}: at least one data record is required")
            return Table(path.name, tuple(headers), tuple(rows))
    except (OSError, UnicodeError, csv.Error) as error:
        # Do not echo parser errors: they can include cell contents or absolute paths.
        raise AuditError(f"{path.name}: cannot read a valid UTF-8 CSV") from error


def _index(keys: tuple[tuple[str, ...], ...]) -> dict[tuple[str, ...], list[int]]:
    result: dict[tuple[str, ...], list[int]] = {}
    for number, key in enumerate(keys, 1):
        result.setdefault(key, []).append(number)
    return result


def _duplicate_check(keys: tuple[tuple[str, ...], ...], split: str) -> Check:
    index = _index(keys)
    repeated = sum(len(records) - 1 for records in index.values())
    return Check(
        f"{split}_duplicates", f"Repeated samples in {split}",
        "flag" if repeated else "pass", "warning",
        ("1 repeated feature record beyond the first occurrence." if repeated == 1
         else f"{repeated} repeated feature records beyond the first occurrence."),
        {"repeated_records": repeated, "unique_feature_records": len(index)},
        "Review repeated observations before splitting or evaluating. "
        "Repeated features can also be legitimate; do not delete them automatically.",
    )


def _overlap_check(train: tuple[tuple[str, ...], ...], test: tuple[tuple[str, ...], ...]) -> Check:
    left, right = _index(train), _index(test)
    shared = left.keys() & right.keys()
    pairs = [
        {"train_record": left[key][0], "test_record": right[key][0]}
        for key in sorted(shared, key=lambda key: right[key][0])[:5]
    ]
    return Check(
        "sample_overlap", "Samples shared across splits",
        "flag" if shared else "pass", "error",
        f"{sum(len(right[key]) for key in shared)} test records have an exact feature match in train.",
        {
            "shared_unique_samples": len(shared),
            "affected_train_records": sum(len(left[key]) for key in shared),
            "affected_test_records": sum(len(right[key]) for key in shared),
            "example_record_pairs": pairs,
        },
        "Inspect these record pairs. If they represent the same observation, "
        "deduplicate before splitting. Identical features alone do not prove leakage.",
    )


def _skipped(code: str, title: str, flag: str) -> Check:
    return Check(code, title, "skipped", "info", f"Not requested. Enable with {flag}.", {}, "", False)


def _group_check(train: Table, test: Table, column: str) -> Check:
    left_values, right_values = train.column(column), test.column(column)
    left = {value for value in left_values if not _missing(value)}
    right = {value for value in right_values if not _missing(value)}
    shared = left & right
    missing_train = sum(_missing(value) for value in left_values)
    missing_test = sum(_missing(value) for value in right_values)
    complete = not (missing_train or missing_test)
    status = "flag" if shared else ("pass" if complete else "inconclusive")
    return Check(
        "entity_overlap", "Entities shared across splits", status, "warning",
        f"{len(shared)} nonmissing entity IDs occur in both splits.",
        {
            "column": column, "shared_entities": len(shared),
            "affected_train_records": sum(value in shared for value in left_values),
            "affected_test_records": sum(value in shared for value in right_values),
            "missing_train_ids": missing_train, "missing_test_ids": missing_test,
        },
        "If evaluation must generalize to unseen entities, split by entity. "
        "Overlap may be appropriate for forecasting known entities. Missing IDs are unassessed.",
        complete,
    )


def _parse_times(values: tuple[str, ...]) -> tuple[list[datetime], int, set[bool]]:
    parsed, invalid, awareness = [], 0, set()
    for value in values:
        if _missing(value):
            invalid += 1
            continue
        try:
            stamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            aware = stamp.utcoffset() is not None
            awareness.add(aware)
            parsed.append(stamp.astimezone(timezone.utc) if aware else stamp.replace(tzinfo=timezone.utc))
        except (ValueError, OverflowError):
            invalid += 1
    return parsed, invalid, awareness


def _time_check(train: Table, test: Table, column: str) -> Check:
    left, bad_train, aware_train = _parse_times(train.column(column))
    right, bad_test, aware_test = _parse_times(test.column(column))
    mixed = len(aware_train | aware_test) > 1
    evidence: dict[str, Any] = {
        "column": column, "invalid_train_records": bad_train,
        "invalid_test_records": bad_test, "mixed_timezone_awareness": mixed,
    }
    if bad_train or bad_test or mixed:
        return Check(
            "time_order", "Strict future holdout", "inconclusive", "warning",
            "Time order cannot be established for every record.", evidence,
            "Use valid ISO 8601 dates/timestamps with consistent timezone awareness. "
            "All records must be parseable for this check to pass.", False,
        )
    # Only aggregate time boundaries are emitted; individual timestamps stay local.
    inverted = max(left) >= min(right)
    evidence["train_ends_before_test_starts"] = not inverted
    return Check(
        "time_order", "Strict future holdout", "flag" if inverted else "pass", "warning",
        "Train does not end strictly before test begins." if inverted
        else "Every train timestamp precedes every test timestamp.",
        evidence,
        "For a strictly future evaluation, put every training record before the first "
        "test timestamp. Ties are flagged. This check does not inspect feature availability.",
    )


def _target_check(train: Table, test: Table, target: str, features: tuple[str, ...]) -> Check:
    targets = train.column(target) + test.column(target)
    missing = sum(_missing(value) for value in targets)
    if missing or len(set(train.column(target))) < 2:
        return Check(
            "target_copy", "Target copied into a feature", "inconclusive", "warning",
            "Target-copy check needs complete targets and at least two train target values.",
            {"target": target, "missing_targets": missing},
            "Supply nonmissing targets and a nonconstant training target. "
            "This check looks for exact copies only.", False,
        )
    copies = [
        feature for feature in features
        if train.column(feature) + test.column(feature) == targets
    ]
    return Check(
        "target_copy", "Target copied into a feature", "flag" if copies else "pass", "error",
        ("1 feature column exactly matches the target in every record." if len(copies) == 1
         else f"{len(copies)} feature columns exactly match the target in every record."),
        {"target": target, "matching_columns": copies},
        "Verify whether these columns are available at prediction time. Remove copies "
        "created from the outcome. Exact equality is a review signal, not a causal diagnosis.",
    )


def audit(
    train_path: str | Path, test_path: str | Path, *, target: str | None = None,
    group: str | None = None, time: str | None = None, ignore: tuple[str, ...] = (),
) -> Report:
    """Audit all records, using exact CSV string equality for feature comparisons.

    Metadata columns (target/group/time/ignore) are excluded from feature keys.
    Returns evidence, never a claim that a dataset is leakage-free.
    """
    train, test = read_csv(train_path), read_csv(test_path)
    if set(train.headers) != set(test.headers):
        raise AuditError("Train and test must contain the same named columns")
    configured = [name for name in (target, group, time) if name is not None]
    if len(set(configured)) != len(configured):
        raise AuditError("Target, group, and time must be distinct columns")
    unknown = (set(configured) | set(ignore)) - set(train.headers)
    if unknown:
        raise AuditError("A configured column is absent from the CSV headers")
    excluded = set(configured) | set(ignore)
    features = tuple(name for name in train.headers if name not in excluded)
    if not features:
        raise AuditError("At least one feature column must remain after exclusions")

    def keys(table: Table) -> tuple[tuple[str, ...], ...]:
        positions = [table.headers.index(name) for name in features]
        return tuple(tuple(row[position] for position in positions) for row in table.rows)

    left, right = keys(train), keys(test)
    checks = (
        _overlap_check(left, right),
        _duplicate_check(left, "train"), _duplicate_check(right, "test"),
        _group_check(train, test, group) if group else _skipped("entity_overlap", "Entities shared across splits", "--group"),
        _time_check(train, test, time) if time else _skipped("time_order", "Strict future holdout", "--time"),
        _target_check(train, test, target, features) if target else _skipped("target_copy", "Target copied into a feature", "--target"),
    )
    return Report(
        {"train": {"name": train.name, "rows": len(train.rows)},
         "test": {"name": test.name, "rows": len(test.rows)}, "columns": len(train.headers)},
        {"target": target, "group": group, "time": time, "ignored": list(ignore),
         "features": list(features), "comparison": "exact CSV string equality"},
        checks,
    )
