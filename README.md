# CREW / ORCH Dynamic Hypergraph Work

This private working repository collects the code, tests, scripts, and research notes used to study ORCH and the local lightweight dynamic-hypergraph implementation.

## Layout

- `ORCH/`: tracked ORCH source tree at the local working revision, including coordination and resource-scheduling additions.
- `WILDFIRE-ORCH/`: locally modified Unity source files, stored at their original relative paths.
- `workspace/`: CREW-level scripts, tests, and research notes.

Large experiment runs, Unity build products, caches, downloaded papers, archives, credentials, and model artifacts are intentionally excluded.

## Updating

Run `./sync_workspace.sh` from this repository, review `git status` and the staged diff, then commit and push. The script only synchronizes the selected source and analysis material; it does not commit or push automatically.

The upstream projects remain available in the adjacent `CREW/ORCH` and `CREW/WILDFIRE-ORCH` repositories. Their original Git histories and remotes are not modified by this snapshot repository.
