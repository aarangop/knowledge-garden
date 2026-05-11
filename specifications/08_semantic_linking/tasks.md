# 08 — Tasks

## Step 1: GraphStore.get_all_chunks + derive_related_to

- [x] Write test: `get_all_chunks` returns chunks with embeddings
- [x] Write test: `derive_related_to` returns int count of edges created
- [x] Verify tests fail (red)
- [x] Add `get_all_chunks` abstract method to `GraphStore`
- [x] Add `derive_related_to` abstract method to `GraphStore`
- [x] Implement `get_all_chunks` in `Neo4jGraphStore`
- [x] Implement `derive_related_to` in `Neo4jGraphStore`
- [x] Verify tests pass (green)

## Step 2: SemanticLinker service

- [x] Write test: linker creates SIMILAR_TO edges for cross-note matches
- [x] Write test: linker excludes same-note matches
- [x] Write test: linker handles no matches gracefully
- [x] Write test: linker respects threshold and max_neighbors
- [x] Write test: linker emits progress callbacks (SIMILAR + RELATED phases)
- [x] Write test: LinkResult has correct shape
- [x] Write test: linker handles find_similar_chunks exceptions (fail open)
- [x] Verify tests fail (red)
- [x] Create `services/linker.py` with SemanticLinker, LinkPhase, LinkResult
- [x] Verify tests pass (green)

## Step 3: CLI `kg link` command

- [x] Write test: `kg link` exits 0 on success
- [x] Write test: `kg link` prints summary table
- [x] Verify tests fail (red)
- [x] Add `link` command to `cli.py` with Rich progress bars
- [x] Verify tests pass (green)

## Step 4: API endpoint

- [x] Add `POST /api/v1/link` endpoint
- [x] Verify endpoint returns correct response

## Step 5: Final verification

- [x] Run `ruff check` on all modified files
- [x] Run `mypy` on all modified files
- [x] Run full unit test suite

## Notes

- All 175 unit tests pass.
- Remaining ruff/mypy issues are pre-existing (long docstrings in `test_config.py`, unused `type: ignore` in `main.py`) — not introduced by this spec.
- Integration test (`test_linker_integration_creates_edges`) requires a live Neo4j instance; not yet run.
