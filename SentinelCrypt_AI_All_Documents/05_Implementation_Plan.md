# SentinelCrypt AI
## Implementation Plan

**Duration:** 12 focused development days  
**Developer:** One person  
**Priority:** Working prototype first, research depth second

---

## 1. Delivery Strategy

Build in five stages:

1. Research and data foundation.
2. ML detection engine.
3. Explainability and cryptographic audit.
4. Backend and frontend.
5. Evaluation, documentation, and demonstration.

Do not begin with the dashboard. Build and test the core engine first.

## 2. Priority Levels

### P0 — Mandatory

- Dataset loading.
- Leakage-safe preprocessing.
- Two ML models.
- Evaluation metrics.
- Single prediction.
- Hash-linked ledger.
- Verification tests.
- Basic FastAPI API.
- Basic React dashboard.

### P1 — Important

- SHAP explanations.
- Model comparison page.
- Audit record page.
- Research notebook.
- Exportable results.

### P2 — Optional

- Cross-dataset evaluation.
- Explanation stability score.
- Batch prediction.
- PostgreSQL.
- Advanced visual polish.
- Cloud deployment.

## 3. Day-by-Day Plan

### Day 1 — Research and repository setup

Tasks:

- Create GitHub repository.
- Write initial README.
- Read relevant papers.
- Select the first dataset.
- Define research question.
- Create Python environment.
- Create project folders.

Deliverables:

- Repository created.
- Literature notes.
- Initial architecture.
- Dataset selected.

### Day 2 — Dataset pipeline

Tasks:

- Download dataset.
- Inspect columns and labels.
- Build loader.
- Implement validation.
- Detect missing values.
- Document feature schema.
- Create a small sample dataset for tests.

Deliverables:

- `loader.py`
- `preprocessing.py`
- Dataset analysis notebook.

### Day 3 — Baseline ML model

Tasks:

- Implement train/test split.
- Build preprocessing pipeline.
- Train Logistic Regression.
- Calculate metrics.
- Save model artifact.
- Record configuration.

Deliverables:

- Baseline model.
- Metrics JSON.
- Confusion matrix.
- Reproducible training command.

### Day 4 — Second model and evaluation

Tasks:

- Train Random Forest.
- Compare both models.
- Add per-class metrics.
- Calculate false-positive rate.
- Check class imbalance.
- Write evaluation notes.

Deliverables:

- Model comparison.
- Evaluation notebook.
- Initial research findings.

### Day 5 — Prediction service

Tasks:

- Implement model loading.
- Validate feature schema.
- Implement single-record prediction.
- Add probability output.
- Add prediction IDs.
- Write prediction tests.

Deliverables:

- `predict.py`
- Prediction service.
- Unit tests.

### Day 6 — Explainability

Tasks:

- Integrate SHAP.
- Generate global importance.
- Generate local explanations.
- Store top feature contributions.
- Document limitations.
- Test explanation output.

Deliverables:

- Explanation service.
- SHAP plots.
- Explanation JSON format.

### Day 7 — Cryptographic ledger

Tasks:

- Implement canonical JSON.
- Implement SHA-256 hash calculation.
- Implement previous-hash linking.
- Store audit records.
- Implement verification.
- Test modified record detection.

Deliverables:

- `ledger.py`
- `verify.py`
- Ledger tests.
- Example audit chain.

### Day 8 — FastAPI backend

Tasks:

- Create FastAPI app.
- Add health endpoint.
- Add dataset endpoints.
- Add model endpoints.
- Add prediction endpoint.
- Add explanation endpoint.
- Add audit verification endpoint.
- Add OpenAPI descriptions.

Deliverables:

- Working backend.
- API documentation.
- API integration tests.

### Day 9 — React dashboard foundation

Tasks:

- Create React app.
- Build navigation.
- Build dashboard layout.
- Add API client.
- Add dataset page.
- Add model page.
- Add loading and error states.

Deliverables:

- Usable dashboard shell.
- Dataset and model screens.

### Day 10 — Dashboard integration

Tasks:

- Build prediction form.
- Display prediction result.
- Display explanation chart.
- Build audit ledger table.
- Add verification action.
- Add metrics visualization.

Deliverables:

- End-to-end workflow:
  dataset → model → prediction → explanation → audit → verification.

### Day 11 — Research experiments

Tasks:

- Run final model comparisons.
- Run controlled explanation stability tests.
- Run ledger performance tests.
- Record all configurations.
- Create charts and tables.
- Write limitations.

Deliverables:

- Research results.
- Experiment notebook.
- Figures.
- Limitations section.

### Day 12 — Polish and presentation

Tasks:

- Fix critical bugs.
- Add screenshots.
- Improve README.
- Add setup instructions.
- Add architecture diagram.
- Prepare a two-minute demonstration.
- Prepare questions for professors.
- Tag a release.

Deliverables:

- GitHub-ready project.
- Demo-ready prototype.
- Research discussion notes.

## 4. Daily Work Routine

Suggested daily allocation:

| Activity | Time |
|---|---:|
| Coding | 3–5 hours |
| Research reading | 45–60 minutes |
| Testing | 30–60 minutes |
| Documentation | 30 minutes |
| Git commits | 10–15 minutes |

If college or travel reduces available time, preserve P0 features and reduce optional scope.

## 5. Git Commit Plan

Suggested commits:

```text
chore: initialize sentinelcrypt ai repository
docs: add product concept and technical requirements
feat: add dataset loader and validator
feat: add leakage safe preprocessing pipeline
feat: train baseline logistic regression model
feat: add random forest model comparison
feat: add prediction service
feat: integrate shap explanations
feat: implement hash linked audit ledger
test: add ledger tamper detection tests
feat: add fastapi prediction endpoints
feat: create react dashboard shell
feat: connect prediction and audit views
docs: add research experiments and limitations
chore: prepare v1.0 research prototype
```

## 6. Definition of Done

### ML

- [ ] Two models train successfully.
- [ ] Metrics are saved.
- [ ] Test split is isolated.
- [ ] Class imbalance is documented.
- [ ] Model artifacts load correctly.

### Explainability

- [ ] Local explanation works.
- [ ] Global importance works.
- [ ] Explanation limitations are documented.
- [ ] Explanation output is tested.

### Cryptography

- [ ] Canonical serialization is deterministic.
- [ ] Hash chain is generated.
- [ ] Verification passes for valid records.
- [ ] Modified records are detected.
- [ ] Broken links are detected.

### Backend

- [ ] Health endpoint works.
- [ ] Prediction endpoint works.
- [ ] Explanation endpoint works.
- [ ] Audit verification endpoint works.
- [ ] API errors are structured.

### Frontend

- [ ] Dashboard loads.
- [ ] Prediction form works.
- [ ] Explanation is readable.
- [ ] Audit table works.
- [ ] Verification result is visible.
- [ ] Loading and error states exist.

### Documentation

- [ ] README complete.
- [ ] Architecture documented.
- [ ] Dataset source cited.
- [ ] Setup instructions tested.
- [ ] Research limitations written.
- [ ] Demo flow prepared.

## 7. Demonstration Script

### Minute 0:00–0:20 — Problem

Explain that the project studies detection performance, explanation reliability, and evidence integrity.

### Minute 0:20–0:50 — ML prediction

Show a dataset, select a trained model, and generate a prediction.

### Minute 0:50–1:15 — Explainability

Show the top contributing features and explain that they describe model behavior.

### Minute 1:15–1:40 — Cryptographic audit

Show the stored prediction record and verify the hash chain.

### Minute 1:40–2:00 — Research direction

Explain the planned experiments and ask the professor for feedback on the research methodology.

## 8. Questions for Researchers

- Is cross-dataset generalization a suitable evaluation direction?
- What is the most defensible way to evaluate explanation reliability?
- Which baseline models should be included?
- How should class imbalance be handled for this dataset?
- What additional threat model should be considered for audit integrity?
- Could the project be developed into a supervised student research project?

## 9. Final Scope Control

If the project is behind schedule:

1. Keep one dataset.
2. Keep two models.
3. Keep single-record prediction.
4. Keep SHAP local explanation.
5. Keep hash-linked ledger.
6. Keep verification tests.
7. Remove batch prediction, cloud deployment, PostgreSQL, and advanced models.

A small, tested, reproducible prototype is preferable to an unfinished platform with many features.
