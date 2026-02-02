## Scope Contract

> **Purpose**: Define what a sub-scope promises to deliver to its parent orchestrator.
> Scope contracts are generated at decomposition time using PREPARE output and serve as
> the authoritative agreement between parent and sub-scope for deliverables and interfaces.

### Contract Format

Each sub-scope receives a scope contract with the following structure:

```
Scope Contract: {scope-name}

Identity:
  scope_id: {kebab-case identifier, e.g., "backend-api"}
  parent_scope: {parent scope_id or "root"}
  executor: rePACT

Deliverables:
  - {Expected file paths or patterns this scope produces}
  - {Non-file artifacts: API endpoints, schemas, migrations, etc.}

Interfaces:
  exports:
    - {Types, endpoints, APIs this scope exposes to siblings}
  imports:
    - {What this scope expects from sibling scopes}

Constraints:
  shared_files: []  # Files this scope must NOT modify (owned by siblings)
  conventions: []   # Coding conventions to follow (from parent or prior scopes)
```

### Design Principles

- **Minimal contracts** (~5-10 lines per scope): The integration phase catches what the contract does not specify. Over-specifying front-loads context cost into the orchestrator.
- **Backend-agnostic**: The contract defines WHAT a scope delivers, not HOW. The same contract format works whether the executor is rePACT (today) or TeammateTool (future).
- **Generated, not authored**: The orchestrator populates contracts from PREPARE output and detection analysis. Contracts are not hand-written.

### Generation Process

1. Identify sub-scope boundaries from detection analysis (confirmed or adjusted by user)
2. For each sub-scope:
   a. Assign `scope_id` from domain keywords (e.g., "backend-api", "frontend-ui", "database-migration")
   b. List expected deliverables from PREPARE output file references
   c. Identify interface exports/imports by analyzing cross-scope references in PREPARE output
   d. Set shared file constraints by comparing file lists across scopes (overlapping files go to constraints)
   e. Propagate parent conventions (from plan or ARCHITECT output if available)
3. Present contracts in the rePACT invocation prompt for each sub-scope

### Contract Lifecycle

```
Detection fires → User confirms boundaries → Contracts generated
    → Passed to rePACT per sub-scope → Sub-scope executes against contract
    → Sub-scope handoff includes contract fulfillment section
    → Integration phase verifies contracts across sub-scopes
```

### Contract Fulfillment in Handoff

When a sub-scope completes, its handoff includes a contract fulfillment section mapping actual outputs to contracted items:

```
Contract Fulfillment:
  Deliverables:
    - ✅ {delivered item} → {actual file/artifact}
    - ❌ {undelivered item} → {reason}
  Interfaces:
    exports: {what was actually exposed}
    imports: {what was actually consumed from siblings}
  Deviations: {any departures from the contract, with rationale}
```

The integration phase uses fulfillment sections from all sub-scopes to verify cross-scope compatibility.

---
