# Temporal Integrity Validation

## Overview

The **Temporal Integrity** subsystem ensures temporal consistency across SentinelCrypt's database records. It validates relationships between experiments, models, predictions, and audit records to detect impossible timestamps, future dates where inappropriate, reversed time ordering, and clock skew.

This is a **read-only validation** — no database mutations occur during verification.

## Clock Assumptions

Before validating, understand these fundamental clock assumptions:

| Assumption | Description |
|---|---|
| **UTC convention** | All timestamps in the database are stored as UTC and are timezone-naive (naive datetime objects representing UTC) |
| **System clock as source of truth** | The running system's clock is the authoritative source for "current time" during validation |
| **Clock skew tolerance** | Small clock skew (< 5 seconds) is expected and reported as a warning, not an error |
| **Cryptographic provenance takes precedence** | The audit ledger's hash chain is the authoritative record of what occurred; system timestamps are secondary |
| **No real-world time claims** | System timestamps do not claim real-world wall-clock accuracy — they only reflect ordering and relative timing |

## Validation Checks

The temporal consistency module validates the following relationships:

### 1. Experiment-Prediction Timeline

**Invariant**: `experiment.created_at <= prediction.created_at`

A prediction cannot be created before its associated experiment model was created.

**Severity levels**:
- **ERROR**: Prediction created more than 5 seconds before its experiment (`delta < -5s`)
- **WARN**: Small clock skew (`-5s <= delta < 0`) — expected in distributed systems
- **INFO**: Prediction and experiment created at nearly the same time (`delta >= 0`)

### 2. Future Timestamps

**Check**: Prediction/experiment created_at should not be more than 1 year in the future relative to the system clock.

**Severity**: **MEDIUM** — may be legitimate for forecast/scenario use cases.

### 3. Updated-at >= Created-at

**Invariant**: For any record, `updated_at >= created_at`

A record cannot be "updated" before it was "created".

**Severity**: **HIGH** — indicates data corruption or manual timestamp manipulation.

### 4. Cross-Model Temporal Relationships

**Check**: Prediction.created_at should be reasonable relative to ModelRecord.created_at and Experiment.created_at.

**Valid relationships**:
- `Experiment.created_at <= ModelRecord.created_at <= Prediction.created_at`
- Predictions should typically be created within a reasonable window (e.g., 30 days) after their model's creation

## Detection Rules

### Impossible Timeline (`impossible_timeline`)

```python
# Example: prediction created 3600s (1hr) before experiment
delta = prediction.created_at - experiment.created_at  # -3600 seconds
# Severity: HIGH
# Message: "Prediction ID X created 3600.0s BEFORE its experiment ID Y"
```

### Temporal Skew (`temporal_skew`)

```python
# Example: prediction created 2s before experiment (within tolerance)
delta = prediction.created_at - experiment.created_at  # -2 seconds
# Severity: WARN
# Message: "Prediction ID X precedes experiment ID Y by 2.00s (clock skew?)."
# Details: delta_seconds=-2.0, clock_skew_tolerance_s=5
```

### Future Timestamp (`future_timestamp`)

```python
# Example: prediction created 400 days in the future
delta = (now - prediction.created_at).total_seconds()  # -34560000 seconds (400 days)
# Severity: MEDIUM
# Message: "Prediction ID X has created_at more than 1 year in the future relative to system clock"
```

### Updated Before Created (`inconsistent_timestamp`)

```python
# Example: updated_at is 1 hour before created_at
# Severity: HIGH
# Message: "Record ID X was updated before it was created."
```

## API Integration

The temporal validation is integrated into the database integrity audit endpoint:

```
POST /api/v1/integrity/database/verify
```

The response includes a `findings` array with temporal check results, grouped by severity:
- `high` (ERROR) — must be investigated
- `medium` (WARN) — suspicious but possibly explainable
- `low` (INFO) — informational

## Example Audit Report Temporal Section

```json
{
  "total_issues": 3,
  "issues_by_severity": {
    "high": 1,
    "medium": 1,
    "low": 1
  },
  "findings": [
    {
      "type": "impossible_timeline",
      "severity": "high",
      "table": "predictions",
      "description": "Prediction ID pred-55 created 7200.0s BEFORE its experiment ID exp-33",
      "affected_ids": ["pred-55"],
      "affected_table": "predictions"
    },
    {
      "type": "temporal_skew",
      "severity": "warn",
      "table": "predictions",
      "description": "Prediction ID pred-12 precedes experiment ID exp-33 by 3.00s (clock skew?).",
      "affected_ids": ["pred-12"],
      "details": {
        "delta_seconds": -3.0,
        "clock_skew_tolerance_s": 5
      }
    },
    {
      "type": "future_timestamp",
      "severity": "medium",
      "table": "experiments",
      "description": "Experiment ID exp-99 has created_at more than 1 year in the future relative to system clock",
      "affected_ids": ["exp-99"]
    }
  ]
}
```

## Remediation Guidelines

### For Impossible Timelines (`high` severity):

1. **Verify the timestamps** — check if this is a data entry error
2. **If intentional** — document the exception with a valid reason
3. **If erroneous** — correct the `created_at` to be after the experiment's creation
4. **Never delete records** to fix the timeline — use proper timestamp updates

### For Temporal Skew (`warn` severity):

1. **Check system clock synchronization** across all database nodes
2. **Verify NTP/PNTP is running** and synchronized
3. **Accept as expected** if within the 5-second tolerance
4. **Log** for monitoring but no immediate action required

### For Future Timestamps (`medium` severity):

1. **Confirm this is intentional** — some use cases involve forecast dates
2. **If unintentional** — correct the timestamp to a past date
3. **If for a future scenario** — add metadata noting the forecast/projection nature

### For Updated-Before-Created (`high` severity):

1. **Immediately investigate** — this strongly indicates data corruption
2. **Restore from backup** if the correct timestamps are known
3. **Manually reset** `created_at` and `updated_at` to proper values
4. **Review write procedures** to prevent recurrence

## Non-Goals (Out of Scope)

The following are intentionally NOT validated by this subsystem:

- **Real-world clock accuracy** — we do not verify that database timestamps match actual wall-clock time
- **Geographic time zones** — all timestamps are UTC; no timezone conversion is performed
- **Network latency** — inter-node communication delays are not modeled
- **DST transitions** — daylight saving time changes are not accounted for (all times are UTC)
- **Cryptographic proof of time** — the audit ledger proves ordering, not absolute time

## Related Components

- **Database Integrity Audit** (`POST /api/v1/integrity/database/verify`) — overall integrity including temporal checks
- **Audit Ledger** (`/audit/records`) — cryptographic hash chain that provides ordering proof
- **Experiment Service** (`/experiments`) — manages experiment lifecycle and timestamps
- **Prediction Service** (`/predictions`) — manages prediction records and model links