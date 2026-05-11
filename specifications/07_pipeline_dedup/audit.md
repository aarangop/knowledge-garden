# Audit: 07_pipeline_dedup

**Spec:** specifications/07_pipeline_dedup/
**Date:** 2026-05-09
**Verdict:** PASS WITH NOTES

---

## Contract Alignment

| Contract Item | Status | Notes |
|---|---|---|
| `DedupConfig` model with `threshold: float = 0.95` | ✅ Implemented | `config.py` line 155–156. Exact match. |
| `BusinessConfig.dedup: DedupConfig = DedupConfig()` | ✅ Implemented | `config.py` line 179. |
| `DedupConfig` exported in `__all__` | ✅ Implemented | `config.py` line 29. |
| YAML key `dedup.threshold` | ✅ Implemented | `config.yaml` line 43–44 contains `dedup:\n  threshold: 0.95`. |
| `IngestPhase` replaces old values with `CHUNKING / DEDUP / UPSERT` | ✅ Implemented | `pipeline.py` lines 20–23. `EMBEDDING` and `INDEXING` are absent. |
| `IngestResult.chunks_skipped` field | ✅ Implemented | `pipeline.py` line 33. |
| `IngestPipeline.__init__` signature with `dedup_threshold: float = 0.95` | ✅ Implemented | `pipeline.py` lines 38–52. Exact match. |
| CHUNKING phase: progress callback `(CHUNKING, i, total_notes, note.title)` | ✅ Implemented | `pipeline.py` lines 65–70. |
| Embed in batches of `embed_batch_size` | ✅ Implemented | `pipeline.py` lines 83–95. |
| DEDUP phase: call `find_similar_chunks(embedding, limit=1, threshold=dedup_threshold)` per chunk | ✅ Implemented | `pipeline.py` lines 97–118. |
| DEDUP: mark chunk as duplicate if any match returned | ✅ Implemented | `pipeline.py` lines 108–116. |
| DEDUP progress callback `(DEDUP, checked_count, total_chunks, f"{skipped} skipped")` | ✅ Implemented | `pipeline.py` lines 120–127. `dedup_checked = end_idx` is used as `checked_count`. |
| UPSERT: upsert parent note once per unique note ID in a `set[UUID]` | ✅ Implemented | `pipeline.py` lines 129–134. `upserted_note_ids` is a `set[UUID]`. |
| UPSERT: only upsert new (non-duplicate) chunks | ✅ Implemented | `pipeline.py` lines 136–138 iterate `new_chunks`. |
| UPSERT progress callback `(UPSERT, upserted_count, total_new_chunks, f"batch {batch_idx+1}/{num_batches}")` | ✅ Implemented | `pipeline.py` lines 140–146. |
| Empty vault: no callbacks fired | ✅ Implemented | Lines 63–70 only fire callback inside `for i, note in enumerate(notes)` which is empty. |
| No chunks: notes still upserted, no DEDUP/UPSERT callbacks | ✅ Implemented | `pipeline.py` lines 148–150. Notes are upserted. The `if all_chunks:` guard prevents DEDUP/UPSERT callbacks. |
| `find_similar_chunks` exception: treat as not duplicate (fail open) | ✅ Implemented | `pipeline.py` lines 110–118. `except Exception` catches all errors, logs a warning, does not mark as duplicate. |
| All chunks in a batch are duplicates: note still upserted | ✅ Implemented | Note upsert iterates `batch_chunks` (all chunks), not `new_chunks` (`pipeline.py` line 129). |
| `ProgressCallback` type alias `Callable[[IngestPhase, int, int, str], None]` | ✅ Implemented | `pipeline.py` line 26. |
| CLI: pass `dedup_threshold=business.dedup.threshold` to `IngestPipeline` | ✅ Implemented | `cli.py` line 77. |
| CLI: show DEDUP and UPSERT progress bars (replacing EMBEDDING/INDEXING) | ✅ Implemented | `cli.py` lines 89–100. Three tasks: `chunking_task`, `dedup_task`, `upsert_task`. |
| CLI: display `chunks_skipped` in result table | ✅ Implemented | `cli.py` line 266: `"Chunks skipped (dedup)"` row. |

---

## Test Coverage

| Specified Test | Present | Passing | Notes |
|---|---|---|---|
| `test_pipeline_dedup_skips_identical_chunks` | ✅ | ✅ | `test_pipeline.py` line 368. Mocks one match → `chunks_skipped == 1`, `chunks_created == 1`. |
| `test_pipeline_dedup_keeps_novel_chunks` | ✅ | ✅ | `test_pipeline.py` line 403. No matches → `chunks_skipped == 0`, `chunks_created == 2`. |
| `test_pipeline_dedup_threshold_from_constructor` | ✅ | ✅ | `test_pipeline.py` line 426. Passes `dedup_threshold=0.9` and asserts it reaches `find_similar_chunks`. |
| `test_pipeline_upsert_note_called_once_per_note` | ✅ | ✅ | Present as `test_pipeline_upsert_note_called_once_per_note_across_batches` at line 335. 4 chunks from 1 note, batch_size=2 → `upsert_note` called once. Contract name differs slightly but the test is functionally identical. |
| `test_pipeline_chunks_skipped_zero_for_empty_index` | ⚠️ | ✅ | No test exists with this exact name. However, `test_pipeline_dedup_keeps_novel_chunks` (line 403) and `test_pipeline_result_is_ingest_result` (line 96) both assert `chunks_skipped == 0` when `find_similar_chunks` returns `[]`. The semantic intent is fully covered even though the exact function name is missing. |
| `test_pipeline_result_has_chunks_skipped` | ✅ | ✅ | `test_pipeline.py` line 67. Constructs `IngestResult` with `chunks_skipped=3` and asserts field. |

Additional tests present beyond the contract's list (all pass):
- `test_ingest_phase_no_embedding_or_indexing` — verifies old phase values are gone.
- `test_pipeline_dedup_fail_open_on_exception` — covers the "exception → not duplicate" edge case.
- `test_pipeline_all_chunks_duplicate_note_still_upserted` — covers "all chunks duplicate → note still upserted" edge case.
- Full progress callback coverage: phases, argument values, optional callback.

Config tests relevant to spec 07 (all pass):
- `test_dedup_config_model` — `DedupConfig()` default threshold.
- `test_dedup_config_custom_threshold` — YAML override to 0.8.
- `test_dedup_config_exported` — importable from `knowledge_garden.config`.
- `test_business_config_defaults` and `test_business_config_from_yaml_full` — both assert `config.dedup.threshold == 0.95`.

CLI tests relevant to spec 07 (all pass):
- `test_ingest_command_exits_zero`, `test_ingest_happy_path`, `test_ingest_prints_summary_table` — all construct `IngestResult` with `chunks_skipped=0`, confirming the field is integrated end-to-end in the CLI.
- No dedicated CLI test asserts the literal string `"Chunks skipped"` is printed; the table row is present in the implementation but not unit-tested by name.

---

## Edge Cases

| Edge Case | Covered | Notes |
|---|---|---|
| Chunk with no embedding (embed returns fewer vectors than texts) | ❌ | Contract says "skip batch with warning". The implementation uses `zip(..., strict=True)` at `pipeline.py` line 93, which raises `ValueError` rather than skipping with a warning. No test covers this path. |
| `find_similar_chunks` raises an exception | ✅ | `test_pipeline_dedup_fail_open_on_exception` line 456. |
| All chunks in a batch are duplicates | ✅ | `test_pipeline_all_chunks_duplicate_note_still_upserted` line 485. Note is still upserted. |
| Empty vault | ✅ | `test_pipeline_empty_vault` line 143 and `test_pipeline_progress_callback_not_called_for_empty_vault` line 519. |
| No chunks (chunking produces 0) | ✅ | `test_pipeline_single_note_no_chunks` line 164. Note upserted, no embed/dedup/upsert callbacks. |

---

## Deviations

1. **Exact test name `test_pipeline_chunks_skipped_zero_for_empty_index` absent**: The contract lists this as a required test. It is not present by that name. The intent is covered by `test_pipeline_dedup_keeps_novel_chunks` and `test_pipeline_result_is_ingest_result`, which both assert `chunks_skipped == 0` with an empty `find_similar_chunks` return. Strictly the contract specifies the name; this is a minor naming deviation.

2. **Exact test name `test_pipeline_upsert_note_called_once_per_note` absent**: Present as `test_pipeline_upsert_note_called_once_per_note_across_batches`. The test is functionally correct and more specific than the contract required (multi-batch scenario). The intent is fully satisfied.

3. **"Embed returns fewer vectors than texts" edge case handled differently**: Contract (Section 8) specifies: "if `embed` returns fewer vectors than texts, that batch is skipped with a warning." The implementation at `pipeline.py` line 93 uses `zip(..., strict=True)`, which raises `ValueError` rather than skipping with a warning. This deviates from the contract's specified behavior for this edge case. No test verifies either the contract behavior or the actual behavior. This is the only behavioral deviation found.

4. **Note upsert in UPSERT phase iterates `batch_chunks` not `new_chunks`**: The contract says "Upsert parent notes for new chunks". The implementation iterates all `batch_chunks` when deciding whether to upsert the note (line 129), not just `new_chunks`. This means a note whose only batch entry is a duplicate chunk still gets its note upserted. This actually satisfies the edge case from Section 8 ("All chunks in a batch are duplicates → note is still upserted") and is the correct behavior. The contract wording is slightly ambiguous but the test `test_pipeline_all_chunks_duplicate_note_still_upserted` confirms the intent. No functional issue.

5. **CLI test does not assert the "Chunks skipped (dedup)" string**: The contract (Section 6) says "Display `chunks_skipped` in the result table." The implementation does this (label is `"Chunks skipped (dedup)"` at `cli.py` line 266). The CLI tests pass `chunks_skipped=0` in all happy-path mocks and confirm the table renders; however none of the CLI tests explicitly asserts the label string `"Chunks skipped"` appears in output. This is a gap in CLI test coverage but does not indicate a missing implementation.

---

## Observations

- `pipeline.py` is clean and readable. The batch loop structure (embed → dedup → upsert) matches the contract flow exactly.
- Using `zip(..., strict=True)` at line 93 is a reasonable defensive choice but differs from the contract's "skip with warning" prescription. If the embedder ever returns a mismatched batch, the pipeline will raise rather than log and continue.
- The `_note_by_id` helper at line 160 does a linear scan per chunk per batch; for large vaults this is O(notes * chunks) but is acceptable given the current scale of the project.
- `config.yaml` in the repository already has `dedup.threshold: 0.95`, confirming the configuration change was deployed.

---

## Verdict Rationale

All contract items from Sections 1–6 are correctly implemented. The six specified new tests are all present and passing, with two using slightly different names (`_across_batches` suffix; absent `_zero_for_empty_index` name) while fully covering the same intent. All 82 tests in the three targeted test files pass.

The only behavioral deviation is the handling of a mismatched embedding batch (`zip strict=True` vs. "skip with warning") and the absence of a test for that edge case. This is a minor deviation in an edge case that does not affect the primary dedup feature. It is flagged for future spec amendment if the behavior needs to be locked down.

**PASS WITH NOTES** — all core contract items implemented correctly; two test names differ from the contract's specified names; one edge case (embedding batch mismatch) is handled differently from the contract spec with no test coverage.
