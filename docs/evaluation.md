# Evaluation Baseline

## Scope and Repeatability

The primary end-to-end fixture is
[`test_autonomous_repair.py`](../tests/integration/workflows/test_autonomous_repair.py).
It builds the real LangGraph workflow around a deterministic `LLMProvider`, a
temporary calculator repository, and an isolated SQLite database. It does not
call Ollama or another live model service. The repair and approval responses
are fixture-controlled; verification uses the configured local test runner.

Run the deterministic lifecycle and its focused parser, policy, workflow, and
persistence checks with:

```powershell
uv run pytest -q tests/integration/workflows/test_autonomous_repair.py tests/unit/application/agents/test_repair_parser.py tests/unit/application/services/test_repair_execution_service.py tests/unit/domain/repair tests/unit/application/tools/test_apply_patch.py tests/unit/workflows tests/unit/infrastructure/persistence/sqlite/test_incident_repository.py tests/unit/infrastructure/persistence/sqlite/test_repair_repository.py
```

The integration marker here means the workflow crosses real local tools and
SQLite; this test file uses no live Ollama service. The separate
[`test_planner_agent.py`](../tests/integration/agents/planner/test_planner_agent.py)
does use a live provider and is intentionally not part of this baseline. No
scores are reported by this design document; record results only after running
the command in the target environment.

## Scenario Criteria

| Scenario | Pass/fail criteria | Existing coverage and remaining gap |
| --- | --- | --- |
| Successful investigation and repair | The fixture's expected findings are supported by investigation evidence; the patch produces the exact expected file content; verification passes; error is empty; execution and incident are `COMPLETED`; one repair attempt is stored. | `test_investigation_findings_match_calculator_facts_without_repair` independently asserts the two expected evidence facts. The repair success test separately checks exact output, verification, and persisted completion. |
| Incorrect or invalid proposal | A semantically incorrect patch must fail verification. Malformed JSON, unsupported actions, unsafe paths, and invalid diffs must not alter protected or target files. A parse failure must persist a failed execution; a parsed proposal rejected by policy must also persist its rejected repair attempt. | Incorrect-but-applicable patch/retry is covered end-to-end. `test_invalid_repair_proposal_fails_through_investigation_service` covers an invalid step number with an otherwise valid `apply_patch` through `InvestigationService`, persisted failure, and unchanged source. Parser, unsafe path, and invalid-diff rules also have unit coverage. Raw malformed JSON and an unsafe-path proposal through the complete workflow remain gaps. |
| Verification failure after applying a patch | The first patch is applied but fails verification; retry context contains the failure; a corrected patch passes verification and completes the execution. | Covered by `test_autonomous_repair_retries_after_failed_verification`, including two numbered attempts and retry feedback. |
| Retry exhaustion | With `max_attempts = 3`, exactly three applied proposals are verified, all fail, no fourth proposal is requested, and the terminal execution is `FAILED`. | `test_autonomous_repair_stops_after_retry_limit` checks the count, then reloads the failed execution and incident and verifies their terminal states and execution timestamps. |
| Approval or policy rejection | A rejected approval or denied unsafe path performs no patch write, leaves the fixture unchanged, records a rejected/failed attempt, and ends with a failed execution. | Approval rejection is covered end-to-end, including unchanged source and no `apply_patch` call. Path traversal and protected-file rejection are covered by unit security tests, not the complete workflow. |
| Persistence of final outcomes | Reload the execution and incident by ID after both success and failure. Stored statuses and completion timestamps must match the graph result; stored attempt numbers, approval, and verification must match the scenario. | Successful repair and retry-exhaustion failure are asserted after reloading SQLite records. The malformed-proposal service-boundary test also reloads its failed execution and incident. |

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
  result. Treat duration as an observation, not an absolute pass threshold; do
  not add timing assertions that make CI dependent on machine load.

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
- API tests cover authentication, rate limiting, database failures, and a
  successful investigation response. They do not score repair quality.
- SQLite repositories cover attempt round trips and execution lifecycle state;
  PostgreSQL integration tests cover persistence when `TEST_POSTGRES_URL` is
  configured. Neither substitutes for terminal failed-outcome assertions in
  the deterministic repair scenario.
- `RepairLoopService` has only narrow unit coverage and is not used by the
  LangGraph application factory; this baseline evaluates the production graph
  path rather than treating the helper as an additional workflow.