# Data

Status: design only. No market data is downloaded in PHASE 1.

The future canonical store is versioned Parquet with raw, normalized, curated, features and
quarantine zones. Internal timestamps are UTC. Dataset validation must cover missing candles,
duplicates, continuity, zero volume, anomalous prices, timezone and incomplete candles.

Market data files and local databases are excluded from Git by `.gitignore`.
