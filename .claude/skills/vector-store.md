---
name: vector-store
description: Embedding model, vector file format, metadata shape, and cosine-search interface for MLB Draft Oracle. Use when working on grading, ADP analysis, similarity search, or anything under the vector-store module.
---

# Vector Store: MLB Draft Oracle

## Embedding Model

`sentence-transformers/all-MiniLM-L6-v2` — local, CPU, 384-dimensional vectors.

```python
# install once
# uv add sentence-transformers

from sentence_transformers import SentenceTransformer
_model = SentenceTransformer("all-MiniLM-L6-v2")  # cached at module level

def embed(text: str) -> list[float]:
    return _model.encode(text, normalize_embeddings=True).tolist()
```

Cache the loaded model at module import — pay the ~1 s load cost once per process, not per call.

Do **not** use OpenAI embeddings (`text-embedding-3-small` etc.) — that is a paid API call per vector.

## Embedding Text Recipe

The text fed to `embed()` must be consistent. Use this format for picks:

```
{player_name} | {position} | {strategy_name} | {rationale} | HR:{hr} RBI:{rbi} R:{r} SB:{sb} AVG:{avg} OBP:{obp} SLG:{slg} K:{k} W:{w} S:{s} ERA:{era} WHIP:{whip}
```

For ADP vectors:
```
{player_name} | {position} | pick:{pick_number} | season:{season}
```

Keep the recipe in one place (a constants module or the vector-store module itself). Never scatter it.

## Storage Layout

```
./memory/
├── vectors/
│   ├── picks/<uuid>.json     one file per embedded pick
│   └── adp/<uuid>.json       one file per ADP datapoint
```

All paths must go through the `paths` module. No hard-coded strings.

## Pick Vector File Schema

```json
{
  "id": "<uuid4>",
  "kind": "pick",
  "draft_id": "<uuid4>",
  "team_id": "<uuid4>",
  "strategy": "Power Hitting",
  "round": 1,
  "pick_number": 1,
  "player_id": 12345,
  "player_name": "Aaron Judge",
  "position": "OF",
  "rationale": "...",
  "stats_snapshot": {"HR": 58, "RBI": 144, "AVG": 0.267},
  "embedding": [0.123, ...],   // 384 floats
  "indexed_at": "2025-06-01T12:00:00Z"
}
```

## ADP Vector File Schema

```json
{
  "id": "<uuid4>",
  "kind": "adp",
  "draft_id": "<uuid4>",
  "player_id": 12345,
  "player_name": "Aaron Judge",
  "position": "OF",
  "pick_number": 3,
  "season": 2025,
  "embedding": [0.123, ...],   // 384 floats
  "indexed_at": "2025-06-01T12:00:00Z"
}
```

## Cosine Similarity Search

No FAISS, no Chroma, no external vector DB. Use NumPy cosine similarity over all loaded vectors.

```python
import numpy as np
from pathlib import Path
import json

def _load_vectors(directory: Path) -> list[dict]:
    return [json.loads(f.read_text()) for f in directory.glob("*.json")]

def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    return float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb)))

def find_cohort_centroid(strategy: str, vectors: list[dict]) -> list[float] | None:
    """Return mean embedding for picks matching the strategy, or None if < 5 found."""
    cohort = [v["embedding"] for v in vectors if v.get("strategy") == strategy]
    if len(cohort) < 5:
        cohort = [v["embedding"] for v in vectors]  # cold-start fallback
    if not cohort:
        return None
    return np.mean(np.array(cohort), axis=0).tolist()
```

## In-Process Cache

Cache loaded vectors keyed on file mtime so repeated grade lookups don't re-read disk on every call.

```python
_cache: dict[str, tuple[float, dict]] = {}  # path -> (mtime, data)

def load_vector(path: Path) -> dict:
    mtime = path.stat().st_mtime
    if path.as_posix() in _cache and _cache[path.as_posix()][0] == mtime:
        return _cache[path.as_posix()][1]
    data = json.loads(path.read_text())
    _cache[path.as_posix()] = (mtime, data)
    return data
```

## Grading Integration

Cohort fit formula:
```python
cohort_fit = mean(cosine_similarity(pick_embedding, centroid) for pick_embedding in team_pick_embeddings)
# map to [0, 1] — cosine similarity of normalized vectors is already in [-1, 1]; clamp then rescale:
cohort_fit_01 = (cohort_fit + 1) / 2
```

Tag fit formula:
```python
tag_fit = sum(1 for pick in team_picks if strategy_tags_clear(pick)) / len(team_picks)
```

Alignment score:
```python
alignment_score = round(100 * (0.5 * cohort_fit_01 + 0.5 * tag_fit))
```

Weights (0.5 / 0.5) live in one config location — do not scatter them.
