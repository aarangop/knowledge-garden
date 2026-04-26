# Spec-Driven Development (SDD) Workflow

This document governs how AI agents and human collaborators work on the Knowledge Garden project. Every code change flows through specifications first. Code is never written without a frozen spec backing it.

## Core Principles

1. **Specs before code.** No implementation begins until the relevant specification is reviewed and frozen by the human collaborator.
2. **Frozen specs are immutable.** Once a spec is agreed upon, it cannot be modified. Changes require a new spec with the next available number.
3. **TDD is mandatory.** Tests are written before implementation. The contract specifies which tests and edge cases must be covered. Tests must fail (red phase) before any production code is written.
4. **Audit closes the loop.** After implementation, an audit validates alignment between the contract and the code. Deviations are flagged, not silently accepted.

## Specification Structure

Specs live in `specifications/` and follow a numbered folder convention:

```
specifications/
├── 01_foundation/
│   ├── intent.md        # What and why (no technical detail)
│   ├── roadmap.md       # Ordered sub-steps for this phase
│   ├── contract.md      # Technical: interfaces, models, tests, edge cases
│   ├── tasks.md         # Atomic checkboxes for implementation
│   └── audit.md         # Post-implementation: alignment validation
├── 02_vault_parsing/
│   ├── ...
```

### Numbering Rules

- Numbers increment sequentially across the entire project: `01`, `02`, `03`, ...
- Each number maps to one logical unit of work (typically one roadmap phase).
- If a frozen spec needs changes, create a new spec at the next available number. Reference the original spec it amends. Example: `08_foundation_v2/intent.md` opens with "Amends: 01_foundation".
- Never renumber existing specs.

### Spec File Descriptions

**intent.md** — The "what" and "why" in plain language. Describes the expected behavior and outcome from a user's perspective. No code, no technical jargon beyond what's necessary. A non-technical collaborator should understand this file. Should be concise (under 300 words).

**roadmap.md** — Breaks the intent into ordered sub-steps. Each step is a discrete unit of work that can be completed and verified independently. Steps are ordered by dependency. Each step has a one-line description and a "done when" criterion. This file is the bridge between intent and contract.

**contract.md** — The technical specification. Contains:
- Data models and their fields
- Interface signatures (abstract classes, method signatures, return types)
- API endpoint definitions (method, path, request/response schemas)
- Configuration schema
- **Test specifications**: which test files to create, which test cases to write, and which edge cases must be covered
- **Test-first requirement**: for each interface or function specified, the contract lists the corresponding test cases. These tests are written BEFORE the implementation.
- Dependencies and assumptions

The contract is the authoritative source of truth for implementation. If the code and the contract disagree, the code is wrong.

**tasks.md** — A flat list of atomic checkboxes. Each task maps to a specific piece of the contract. Tasks follow TDD ordering:
1. Write test(s) for feature X → verify they fail (red)
2. Implement feature X → verify tests pass (green)
3. Refactor if needed

Tasks are granular enough that each can be completed in a single focused session without ambiguity.

**audit.md** — Written by the Auditor agent after implementation is complete. Contains:
- Checklist of every contract item and whether it was implemented correctly
- Test coverage assessment (are all specified tests present and passing?)
- Deviations from the contract (with justification or flag for review)
- Edge cases verified
- Overall alignment verdict: PASS, PASS WITH NOTES, or FAIL

## Agent Roles

Four specialized agents collaborate on this project. Each has a distinct responsibility and a corresponding prompt file in `.claude/agents/`.

### Architect (`architect.md`)
**Writes specifications.** Takes a feature description or problem statement and produces the full spec suite (intent, roadmap, contract, tasks). The Architect does not write production code or tests. The Architect's output is reviewed by the human collaborator before freezing.

Responsibilities:
- Draft intent.md, roadmap.md, contract.md, tasks.md for a given phase
- Ensure contract includes full test specifications with edge cases
- Ensure tasks follow TDD ordering (test → implement → verify)
- Reference prior frozen specs to maintain consistency
- Answer clarifying questions from the human collaborator during review

### Test Writer (`test-writer.md`)
**Writes tests in the red phase.** Takes a frozen contract and produces test files that fail. The Test Writer does not write production code. All tests must align exactly with what the contract specifies.

Responsibilities:
- Read the frozen contract's test specifications
- Write test files with all specified test cases and edge cases
- Use pytest fixtures and markers as defined in conftest.py
- Verify all tests fail (red phase) — if any test passes before implementation, flag it as a contract issue
- Tests must be self-contained and not depend on implementation details beyond the contract's interfaces

### Executor (`executor.md`)
**Implements the spec.** Takes a frozen contract and a red test suite, and writes the production code to make the tests pass. The Executor does not modify tests or specs.

Responsibilities:
- Read the frozen contract for interfaces, models, and behavior
- Implement production code that makes the red tests pass (green phase)
- Follow the task list in tasks.md in order
- Refactor for clarity after tests pass, without breaking them
- Flag any contract ambiguities — do NOT resolve them silently; raise them for the Architect
- Do not add behavior beyond what the contract specifies

### Auditor (`auditor.md`)
**Validates alignment.** After the Executor completes implementation, the Auditor reviews the code against the contract and writes audit.md.

Responsibilities:
- Compare every contract item against the implementation
- Verify all specified tests exist and pass
- Check for deviations: missing features, extra features, interface mismatches
- Check edge case coverage
- Write audit.md with a structured checklist and verdict
- If verdict is FAIL, list the specific items that need correction

## Development Cycle

For each specification:

```
1. SPECIFY   → Architect drafts spec files
2. REVIEW    → Human collaborator reviews, requests changes
3. FREEZE    → Human approves → spec is frozen (no further edits)
4. TEST      → Test Writer writes failing tests from contract
5. RED CHECK → Verify all tests fail
6. IMPLEMENT → Executor writes code to pass tests
7. GREEN CHECK → Verify all tests pass
8. AUDIT     → Auditor validates alignment, writes audit.md
9. REVIEW    → Human reviews audit, approves or requests fixes
```

Steps 4-8 can iterate if the audit finds issues. The spec itself does not change — if the spec was wrong, a new amendment spec is created.

## TDD Protocol

Every function, method, and endpoint specified in the contract gets tests BEFORE implementation.

### Red Phase (Test Writer)
- Write tests that exercise the contract's interfaces
- Use mocks/fakes for dependencies (e.g., mock GraphStore for testing the linker)
- Tests must be runnable and must FAIL
- Commit the red tests before any implementation begins

### Green Phase (Executor)
- Write the minimum code to make tests pass
- Do not add untested behavior
- Run the full test suite after each task completion

### Refactor Phase (Executor)
- Clean up implementation without changing behavior
- All tests must still pass after refactoring

## File Conventions

- Spec files are Markdown
- Test files mirror the source structure: `tests/test_<module>.py`
- Fixtures go in `tests/fixtures/` (sample vault directories, mock data)
- Integration tests are marked with `@pytest.mark.integration`
- Unit tests are marked with `@pytest.mark.unit`
