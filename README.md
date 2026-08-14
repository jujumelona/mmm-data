# MMM Data

Remote persistence store for **M.M.M Make Minecraft Mode**.

This repository is intentionally separate from the MMM source repository. MMM uses it only when remote trajectory persistence is explicitly enabled by the user.

## Stored data

- verifier-qualified, sanitized structural trajectories
- task/process metadata needed for procedural-memory reuse
- objective verifier receipts and verification levels
- content hashes / provenance needed to reject stale or corrupted records

## Not stored

- chain-of-thought or hidden reasoning
- raw prompts
- source-code bodies or private source paths
- API keys, tokens, credentials, cookies, or other secrets

## Layout

MMM owns the format under `memory/<format-version>/`. The current store format is `v3`; task-class JSONL shards are created lazily when verified records are synced.

Remote writes remain fail-closed unless `MMM_REMOTE_TRAJECTORY_STORE_CONSENT=1` (the Colab `ALLOW_REMOTE_TRAJECTORY_STORE` option) is explicitly enabled.
