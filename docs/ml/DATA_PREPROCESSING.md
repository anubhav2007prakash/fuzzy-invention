# SentinelCrypt AI — Dataset Documentation

## Initial Datasets
- UNSW-NB15
- CICIDS2017

Use the authoritative provider/source pages and record the exact retrieval date/version used.

## Dataset Record
Name; provider; source; license/terms; retrieval date; file names; SHA-256 file hash; rows; features; label definition; missing-value policy; duplicate policy; split strategy.

## Preprocessing
Document categorical encoding, numerical scaling, missing values, feature selection, label mapping, balancing, and seed.

## Leakage Prevention
Fit preprocessing parameters on training data where applicable. Keep test data isolated until final evaluation.

## Dataset Card
**Intended use:** controlled IDS research.

**Limitations:** benchmark datasets may not represent modern operational traffic.

**Ethical use:** benchmark performance must not be presented as proof of real-world detection capability.
