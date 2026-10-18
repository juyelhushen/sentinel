# Evaluation Baseline

## Scope and Repeatability

The primary end-to-end fixture is
[`test_autonomous_repair.py`](../tests/integration/workflows/test_autonomous_repair.py).
It builds the real LangGraph workflow around a deterministic `LLMProvider`, a
temporary calculator repository, and an isolated SQLite database. It does not
call Ollama or another live model service. The repair and approval responses
are fixture-controlled; verification uses the configured local test runner.

Run the deterministic evaluation from the repository root with:

```bash
uv run python scripts/run_evaluation.py
```

The runner invokes existing pytest scenarios by node ID and does not reimplement
the workflow. It uses pytest and the Python standard library only. Reports are
written to `data/evaluation-reports/` by default (the directory is gitignored)
with matching names `sentinel-evaluation-<UTC timestamp>.json` and `.md`. Choose
another local destination with `--output-dir`, for example:

```bash
uv run python scripts/run_evaluation.py --output-dir data/my-evaluation-runs
```

If a generated filename already exists, the runner adds a numeric suffix rather
than overwriting the earlier report.

The integration marker on the lifecycle fixtures means they exercise real local
tools and SQLite; they do not call Ollama or another live model service. The separate
[`test_planner_agent.py`](../tests/integration/agents/planner/test_planner_agent.py)
does use a live provider and is intentionally not part of this baseline. Results
from this runner describe only these deterministic fixtures, not general LLM
performance.

## Scenarios and Criteria

| Report scenario ID | Scenario and pass/fail criteria | Existing coverage and remaining gap |
| --- | --- | --- |
| `investigation_fact_accuracy` | Findings support both calculator facts: the implementation subtracts and the addition test fails. Repair and verification are not run. | `test_investigation_findings_match_calculator_facts_without_repair` asserts the facts independently. |
| `successful_repair_and_persistence` | The patch produces exact expected content; verification passes; execution and incident persist as `COMPLETED`; one repair attempt is stored. | `test_autonomous_repair_fixes_broken_repository` checks output, verification, and SQLite records. |
| `invalid_proposal_rejection` | An invalid step number containing an otherwise valid patch is rejected through `InvestigationService`; failure is observable, execution failure persists, and the repository is unchanged. | `test_invalid_repair_proposal_fails_through_investigation_service` covers this case. Raw malformed JSON and an unsafe-path proposal through the full service boundary remain gaps; parser and path-policy unit tests cover local behavior. |
| `verification_retry` | The first patch is applied but fails verification; retry context includes failure feedback; a corrected patch passes and completes the execution. | `test_autonomous_repair_retries_after_failed_verification` checks two attempts and retry feedback. |
| `retry_exhaustion_and_persisted_failure` | With `max_attempts = 3`, exactly three applied proposals fail verification, no fourth proposal is requested, and SQLite contains failed execution and incident records. | `test_autonomous_repair_stops_after_retry_limit` checks attempts and reloads failed records and execution timestamps. |
| `approval_rejection` | Rejected approval performs no patch write, leaves the fixture unchanged, and records the rejected attempt. | `test_rejected_repair_does_not_modify_repository` covers approval rejection. Unsafe-path rejection is unit-tested, not through the full workflow. |

The runner selects these six existing tests: investigation fact accuracy,
successful repair with persistence, invalid proposal rejection, verification
retry, retry exhaustion with persisted failure, and approval rejection. The
successful and failed persistence checks are part of their corresponding
scenario results, not separately duplicated scenarios.

## Report Semantics

Each JSON scenario record contains its ID, expected outcome, actual outcome,
pytest status, pass flag, number of observed test executions, elapsed seconds,
retry count, and safe error category when applicable. The Markdown table also
includes the observed execution count. `actual_outcome` comes from explicit metadata recorded by the
scenario test; missing or mismatched metadata makes the scenario fail. The
Markdown report presents the same scenario results and totals. Run metadata
includes a UTC timestamp, suite ID, `runner_status`, pytest exit code, and
confirmation that this is not a live-model evaluation. Duplicate registry
entries or repeated executions are reported as failed duplicate results.

Elapsed time covers pytest setup, call, and teardown for that test and is
measured with `time.perf_counter()`. It is unavailable (`null` in JSON) if the
test was not collected. Retry count means additional repair attempts after the
initial attempt; it is read from explicit test metadata. It is unavailable
(`null`) if the test did not report it; it is never substituted with zero.
The repair-disabled investigation-only scenario reports retries as unavailable,
not zero.
Scenario-specific error categories are fixed labels and exception messages or
test output are not copied into reports.

`passed` requires both a passing pytest test and an actual outcome matching the
scenario's expected outcome. Skipped tests and tests not collected are marked
unavailable, not silently omitted, count as non-passing, and cause a nonzero
runner exit. A failed test or outcome mismatch is marked failed and also causes
a nonzero exit.

The total scenario count is the pass-rate denominator:
`pass_rate = passed / configured scenarios`. Skipped and uncollected scenarios
remain in that denominator; the report also lists failed and unavailable
counts separately. The runner computes these values from each run; no example
score is hardcoded.

## Measurements

Keep outcomes separate rather than combining them into a single score:

- **Investigation accuracy:** `supported expected findings / expected findings`.
  Define the expected facts in the fixture before execution. Pass a scenario only
  when all required facts are supported by tool evidence and no contradictory
  finding is asserted. The calculator fixture now asserts two explicit facts;
  this tiny result is a deterministic check, not a general accuracy score.
- **Repair application:** `successful patch steps / planned patch steps`, plus
  exact expected file content. A rejected scenario passes only when the file
  remains byte-for-byte unchanged and no patch succeeds.
- **Verification:** the final `VerificationResult.passed` value and captured
  test-run status. Passing-repair scenarios require `true`; verification-failure
  and exhaustion scenarios require the expected failed attempts.
- **Safe rejection:** approval/policy status, unchanged repository content, no
  successful patch, and a terminal failed execution.
- **Retries and persistence:** use the length and attempt numbers of
  `result["repair_attempts"]` or reload attempts from `SQLiteRepairRepository`;
  compare them to the configured `RepairRetryPolicy.max_attempts` and expected
  scenario count.
- **Duration:** wrap each `ainvoke`/`investigate` call with the Python standard
  library's `time.perf_counter()` and record elapsed seconds with the scenario
  result. The runner measures each pytest protocol with that monotonic clock.
  Treat duration as an observation, not an absolute pass threshold; do not add
  timing assertions that make CI dependent on machine load.

The scenario fixture should use a small repository with an intentionally
incorrect implementation and one known failing test. For this fixture,
predeclare the expected evidence (for example, the implementation subtracts
where the test expects addition) so investigation accuracy is measurable
without model grading or extra dependencies.

## Coverage Reviewed

- Planner and investigation parsing/agents and workflow nodes have deterministic
  unit tests; the calculator evidence check is a separate repair-disabled graph
  test. Graph routing and terminal execution nodes are tested separately.
- Repair parsing, previous-attempt context, patch application, verification,
  retry policy, approval rejection, and repository path protections have unit
  tests.
- The autonomous-repair integration fixture covers the graph's successful
  lifecycle, verification retry, approval rejection, retry exhaustion, invalid
  proposal failure through `InvestigationService`, and repair-attempt persistence
  behavior.
- `scripts/run_evaluation.py` selects those existing tests and emits machine
  JSON plus a human Markdown summary. It records only fixture metadata and test
  outcomes; it does not persist raw prompts, incident bodies, patches, or
  exception messages.
- API tests cover authentication, rate limiting, database failures, and a
  successful investigation response. They do not score repair quality.
- SQLite repositories cover attempt round trips and execution lifecycle state;
  PostgreSQL integration tests cover persistence when `TEST_POSTGRES_URL` is
  configured. Neither substitutes for terminal failed-outcome assertions in
  the deterministic repair scenario.
- `RepairLoopService` has only narrow unit coverage and is not used by the
  LangGraph application factory; this baseline evaluates the production graph
  path rather than treating the helper as an additional workflow.