# SentinelCrypt AI
## UI/UX Design Document

**Version:** 1.0  
**Design direction:** Professional cybersecurity research console  
**Platform:** Responsive web dashboard

---

## 1. UX Principles

1. Clarity over decoration.
2. Research evidence over impressive-looking numbers.
3. Explain every important result.
4. Make system status visible.
5. Never present model output as absolute truth.
6. Keep the interface usable on a laptop.
7. Use accessible contrast and keyboard navigation.

## 2. Visual Direction

### Design language

- Dark professional security-console aesthetic.
- Neutral surfaces.
- Restrained accent colors.
- Clear typography.
- Minimal decorative effects.
- Consistent status badges.
- Data visualizations with readable labels.

### Suggested color semantics

| Meaning | Use |
|---|---|
| Neutral | General information |
| Blue | Model and dataset information |
| Amber | Warnings or uncertain results |
| Red | Detected attack classification or verification failure |
| Green | Successful verification or completed task |
| Purple | Explainability and research insights |

Colors must not be the only way to communicate status. Include text and icons.

## 3. Information Architecture

- Dashboard
- Datasets
- Models
- Predictions
- Explainability
- Audit Ledger
- Experiments
- Documentation
- Settings

## 4. Main Screens

### Screen 1: Dashboard

Purpose: Give the user an overview.

Components:

- Total datasets.
- Trained models.
- Predictions generated.
- Audit records.
- Ledger verification status.
- Recent predictions.
- Model performance summary.
- Quick actions:
  - Upload dataset.
  - Train model.
  - Run prediction.
  - Verify ledger.

### Screen 2: Dataset Explorer

Components:

- Dataset name.
- Dataset source.
- Row count.
- Feature count.
- Label distribution.
- Missing-value summary.
- Feature preview table.
- Validation status.
- Dataset documentation link.

Empty state:

> No dataset loaded. Upload a supported CSV to begin.

### Screen 3: Model Lab

Components:

- Model selection.
- Dataset selection.
- Train/test split configuration.
- Random seed.
- Training status.
- Metrics cards.
- Confusion matrix.
- Per-class metrics table.
- Model version.
- Downloadable experiment result.

### Screen 4: Prediction Workspace

Components:

- Model selector.
- Feature input form.
- Validation messages.
- Predict button.
- Predicted class.
- Probability display.
- Model version.
- Explanation preview.
- Audit record status.

Important copy:

> Prediction is a model output and should be interpreted with the evaluation results and limitations.

### Screen 5: Explanation View

Components:

- Predicted class.
- Top contributing features.
- Positive and negative contribution indicators.
- Feature values.
- Explanation method.
- Explanation limitations.
- Explanation stability result, if available.

### Screen 6: Audit Ledger

Components:

- Record list.
- Record ID.
- Timestamp.
- Prediction class.
- Current hash.
- Previous hash.
- Verification status.
- Record details drawer.
- Verify entire ledger button.

### Screen 7: Research Experiments

Components:

- Experiment name.
- Research question.
- Dataset.
- Model.
- Configuration.
- Metrics.
- Notes.
- Result charts.
- Export button.

## 5. Key User Flows

### Flow A: Train a model

Dashboard → Datasets → Select dataset → Model Lab → Configure → Train → Metrics → Save model.

### Flow B: Explain a prediction

Dashboard → Prediction Workspace → Enter features → Predict → View explanation → View audit record.

### Flow C: Verify evidence

Audit Ledger → Verify ledger → System recalculates hashes → Verification report → View failed records if any.

## 6. UX States

Every major operation must support:

- Loading state.
- Success state.
- Empty state.
- Validation error.
- Server error.
- Retry action.
- Clear explanation of what happened.

## 7. Accessibility

- Keyboard-accessible controls.
- Visible focus indicators.
- Form labels.
- Descriptive button names.
- Table headers.
- Text alternatives for charts.
- No color-only status indicators.
- Responsive layout for narrow screens.

## 8. Suggested Dashboard Layout

```text
┌─────────────────────────────────────────────────────────────┐
│ SentinelCrypt AI                         System: Healthy    │
├───────────────┬─────────────────────────────────────────────┤
│ Dashboard     │ Overview                                    │
│ Datasets      │ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │
│ Models        │ │Datasets│ │ Models │ │Alerts  │ │Ledger  │ │
│ Predictions   │ └────────┘ └────────┘ └────────┘ └────────┘ │
│ Explainability│                                             │
│ Audit Ledger  │ Model Performance      Recent Predictions  │
│ Experiments   │ [Chart]                  [Table]            │
│ Docs          │                                             │
└───────────────┴─────────────────────────────────────────────┘
```

## 9. Important UX Copy

### Model result

> Model evaluation is based on the selected dataset and test split. Results may not generalize to unseen environments.

### Audit verification success

> Ledger verified. All checked records matched their stored hashes and chain links.

### Audit verification failure

> Verification failed. One or more records or chain links do not match the expected values.

### Explanation limitation

> Feature contributions describe this model's behavior for this input. They do not prove causation.

## 10. UX Acceptance Criteria

- A user can reach every core module from navigation.
- The dashboard shows system status.
- Prediction errors are understandable.
- Explanations are readable without inspecting raw JSON.
- Ledger verification clearly distinguishes success and failure.
- The interface works on laptop and mobile widths.
