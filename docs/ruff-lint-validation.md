# Ruff Lint Fix Validation

## Results

- `uv run ruff check src tests --fix`: executed first; seven manual violations remained, with no safe fixes available.
- `uv run ruff format src tests`: executed; formatting applied without unsafe fixes.
- `uv run ruff format --check src tests`: PASS, 233 files already formatted.
- `uv run ruff check src tests`: PASS, all checks passed.
- `uv run mypy src`: FAIL, 35 pre-existing errors in 18 files, checking 124 source files. A non-incremental run confirmed the same errors.
- `uv run pytest -q`: PASS, 218 passed, 1 skipped. No skip markers or assertions were weakened by this change.

The committed versions of the modified source files were type-checked in memory with the remaining sources unchanged. They reproduced all 35 MyPy errors. No source files were reverted for this comparison. CI is not fully green because MyPy still fails.

## Files and Reasons

The first four entries already had local edits when this task began. Those edits were preserved and validated.

- [src/sentinel/domain/repair/policy.py](../src/sentinel/domain/repair/policy.py): `ClassVar[frozenset[str]]` policy constants; protected paths and traversal checks unchanged.
- [src/sentinel/domain/repair/unified_diff.py](../src/sentinel/domain/repair/unified_diff.py): tuple-based `startswith` for file headers; parsing and mismatch behavior unchanged.
- [tests/unit/application/services/test_repair_execution_service.py](../tests/unit/application/services/test_repair_execution_service.py): Ruff-compliant import ordering.
- [tests/unit/application/tools/test_apply_patch.py](../tests/unit/application/tools/test_apply_patch.py): Ruff-compliant import ordering and formatting.
- [src/sentinel/infrastructure/mcp/tool_gateway.py](../src/sentinel/infrastructure/mcp/tool_gateway.py): catch verified MCP protocol/response errors and transport write timeouts, preserving result status, output, error, and request ID.
- [src/sentinel/infrastructure/persistence/sqllite/tool_execution_repository.py](../src/sentinel/infrastructure/persistence/sqllite/tool_execution_repository.py): rename the owned connection to avoid shadowing the injected parameter; remove a stale commented-out commit. No new connection or transaction behavior introduced.
- [src/sentinel/llm/ollama.py](../src/sentinel/llm/ollama.py): remove unused availability result assignment; narrow availability and generation exceptions without changing host/model configuration.
- [src/sentinel/workflows/nodes/investigator.py](../src/sentinel/workflows/nodes/investigator.py): catch expected plan validation errors rather than every exception.
- [src/sentinel/workflows/nodes/planner.py](../src/sentinel/workflows/nodes/planner.py): catch existing parsing and provider exceptions.
- [tests/unit/infrastructure/mcp/test_tool_gateway.py](../tests/unit/infrastructure/mcp/test_tool_gateway.py): instance-local denial content, real MCP connection error, raw timeout coverage, unexpected-error propagation coverage.
- [tests/unit/llm/test_ollama_provider.py](../tests/unit/llm/test_ollama_provider.py): availability success, expected SDK/transport/timeouts, and programming-error propagation coverage.
- [tests/unit/workflows/nodes/test_investigator.py](../tests/unit/workflows/nodes/test_investigator.py): validation error state and programming-error propagation coverage.
- [tests/unit/workflows/nodes/test_planner.py](../tests/unit/workflows/nodes/test_planner.py): use the actual application outage exception; parsing error state and programming-error propagation coverage.
- [tests/unit/workflows/test_sentinel_graph.py](../tests/unit/workflows/test_sentinel_graph.py): use `LLMConnectionError` for the simulated provider outage, preserving error-state assertions.
- [docs/ruff-lint-validation.md](ruff-lint-validation.md): record changes, validation, and exact remaining diagnostics.

## Exception Contracts

- MCP 2.2.0: `mcp.shared.exceptions.MCPError` represents peer protocol errors, read timeouts, and closed connections. The installed JSON-RPC dispatcher translates broken/closed streams to this type but can propagate raw `TimeoutError` on writes. `pydantic.ValidationError` represents responses that violate the negotiated protocol schema. Lifecycle `RuntimeError` and programming `TypeError` are not swallowed. Explicit denial remains a `DENIED` result.
- Ollama 0.6.2: the SDK converts HTTP status errors to `ollama.ResponseError` and HTTPX connection errors to built-in `ConnectionError`. `httpx.TransportError` covers other HTTP transport/timeouts. `asyncio.wait_for` raises built-in `TimeoutError`. Availability returns `False` for these failures; generation retains its `LLMConnectionError` wrapping for expected provider failures. Unrelated errors propagate.
- Planner: `PlanParsingError` is the existing parser contract, and `LLMError` includes the existing connection, timeout, and response failures. These retain the `{plan: None, error: str(exc)}` route.
- Investigator: `ValueError` covers the existing missing-plan guard and mapper's unsupported-action validation. Normal tool failures remain `ToolResult` values. Unexpected runtime/type errors propagate; the investigation error state is unchanged.

## Unresolved MyPy Diagnostics

The SQLite injected-connection branch still contains the pre-existing `connection.execute(...)` placeholder. The lint rename does not repair or change that branch. Repository/transaction tests passed, but they do not exercise that placeholder. Correcting it and the other API/type issues below requires separate work; the full CI build remains blocked.

```text
src\sentinel\domain\tool_execution.py:15: error: Missing type arguments for generic type "dict"  [type-arg]
src\sentinel\infrastructure\database\schema.py:107: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
src\sentinel\infrastructure\persistence\sqllite\tool_execution_repository.py:26: error: Argument 1 to "execute" of "Connection" has incompatible type "EllipsisType"; expected "str"  [arg-type]
src\sentinel\infrastructure\persistence\sqllite\tool_execution_repository.py:95: error: Missing type arguments for generic type "tuple"  [type-arg]
src\sentinel\infrastructure\persistence\sqllite\repair_repository.py:236: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
src\sentinel\infrastructure\persistence\sqllite\repair_repository.py:254: error: Returning Any from function declared to return "str"  [no-any-return]
src\sentinel\workflows\nodes\verification.py:7: error: Function is missing a return type annotation  [no-untyped-def]
src\sentinel\workflows\nodes\verification.py:11: error: Missing type arguments for generic type "dict"  [type-arg]
src\sentinel\workflows\nodes\verification.py:53: error: Function is missing a return type annotation  [no-untyped-def]
src\sentinel\workflows\nodes\investigator.py:5: error: Function is missing a return type annotation  [no-untyped-def]
src\sentinel\workflows\nodes\investigator.py:10: error: Missing type arguments for generic type "dict"  [type-arg]
src\sentinel\workflows\nodes\fail_execution.py:8: error: Missing type arguments for generic type "dict"  [type-arg]
src\sentinel\workflows\nodes\execution.py:9: error: Missing type arguments for generic type "dict"  [type-arg]
src\sentinel\workflows\nodes\error.py:4: error: Missing type arguments for generic type "dict"  [type-arg]
src\sentinel\workflows\nodes\complete_execution.py:8: error: Missing type arguments for generic type "dict"  [type-arg]
src\sentinel\application\repair\repair_agent.py:28: error: Argument "messages" to "LLMRequest" has incompatible type "list[dict[str, str]]"; expected "tuple[LLMMessage, ...]"  [arg-type]
src\sentinel\infrastructure\persistence\sqllite\incident_repository.py:67: error: Return type "Coroutine[Any, Any, Incident | None]" of "get" incompatible with return type "Incident | None" in supertype "sentinel.application.ports.incident_repository.IncidentRepository"  [override]
src\sentinel\application\services\investigation_service.py:14: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
src\sentinel\application\services\investigation_service.py:74: error: Returning Any from function declared to return "SentinelGraphState"  [no-any-return]
src\sentinel\application\services\investigation_service.py:80: error: "IncidentRepository" has no attribute "get_by_id"  [attr-defined]
src\sentinel\application\services\investigation_service.py:87: error: Returning Any from function declared to return "Incident"  [no-any-return]
src\sentinel\workflows\nodes\repair.py:10: error: Function is missing a return type annotation  [no-untyped-def]
src\sentinel\workflows\nodes\repair.py:13: error: Missing type arguments for generic type "dict"  [type-arg]
src\sentinel\workflows\nodes\repair.py:41: error: Function is missing a return type annotation  [no-untyped-def]
src\sentinel\workflows\nodes\repair.py:44: error: Missing type arguments for generic type "dict"  [type-arg]
src\sentinel\workflows\nodes\repair.py:82: error: Missing type arguments for generic type "dict"  [type-arg]
src\sentinel\workflows\nodes\planner.py:7: error: Function is missing a return type annotation  [no-untyped-def]
src\sentinel\workflows\nodes\planner.py:10: error: Missing type arguments for generic type "dict"  [type-arg]
src\sentinel\infrastructure\mcp\server.py:21: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
src\sentinel\infrastructure\mcp\client.py:48: error: Function is missing a return type annotation  [no-untyped-def]
src\sentinel\infrastructure\mcp\client.py:48: error: Missing type arguments for generic type "dict"  [type-arg]
src\sentinel\bootstrap\investigation.py:25: error: Unexpected keyword argument "database_path" for "SQLiteIncidentRepository"  [call-arg]
src\sentinel\bootstrap\investigation.py:25: note: "SQLiteIncidentRepository" defined in "sentinel.infrastructure.persistence.sqlite_incident_repository"
src\sentinel\bootstrap\investigation.py:29: error: Unexpected keyword argument "database_path" for "SQLiteToolExecutionRepository"; did you mean "database"?  [call-arg]
src\sentinel\bootstrap\investigation.py:29: note: "SQLiteToolExecutionRepository" defined in "sentinel.infrastructure.persistence.sqllite.tool_execution_repository"
src\sentinel\bootstrap\investigation.py:42: error: Unexpected keyword argument "tool_executor" for "InvestigatorAgent"  [call-arg]
src\sentinel\bootstrap\investigation.py:42: note: "InvestigatorAgent" defined in "sentinel.agents.investigator.agent"
src\sentinel\bootstrap\investigation.py:53: error: Argument "execution_repository" to "InvestigationService" has incompatible type "SQLiteToolExecutionRepository"; expected "ExecutionRepository"  [arg-type]
Found 35 errors in 18 files (checked 124 source files)
```

## Recommended Commit Message

`fix: resolve Ruff violations and narrow expected failure handling`