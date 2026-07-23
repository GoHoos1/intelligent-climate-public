# Repository Instructions for Coding Agents

## Governing Documentation

Treat these files as the current authoritative source of truth:

- `README.md`
- `docs/product-specification.md`
- `docs/phase-1-technical-design.md`

Do not assume requirements from governing documents mentioned in the Phase 1
design unless those files exist in this repository.

## Phase 1 Invariant

Phase 1 is strictly observation-only. Code must not issue, directly or
indirectly, a Home Assistant service call that changes a thermostat, fan,
switch, humidifier, dehumidifier, ventilation system, water heater, or other
climate-related entity.

Do not add direct `hass.services.async_call` usage. Do not add dormant control
branches, commented service calls, bypass flags, fake adapters, or future
control placeholders.

## Required Validation Commands

Run these before completing behavioral changes:

```powershell
python -m pytest --cov=custom_components.intelligent_climate --cov-report=term-missing
python -m ruff check .
python -m ruff format --check .
python -m mypy custom_components/intelligent_climate tests
```

Run hassfest and HACS validation locally when practical. If unavailable, report
the exact blocker.

Use a virtual environment, WSL2, or a dev container for dependencies. Do not
install additional packages into the global or per-user Python environment.

## Coding Expectations

- Keep code typed and small.
- Prefer immutable domain models for stable identifiers and configuration
  terminology.
- Avoid blocking Home Assistant's event loop.
- Preserve config-entry setup and unloadability.
- Do not add placeholder modules or entities for future features.
- Do not describe Home Assistant setup/unload compatibility as validated unless
  the genuine Home Assistant tests using the real `hass` fixture have run.
- Do not create climate, sensor, binary sensor, event, diagnostics, Repairs,
  coordinator, Store, schedule, model, simulation, or frontend code until an
  approved backlog slice calls for it.
- Update tests and documentation with behavioral changes.

## Repository Operations

Do not commit, push, rewrite Git history, open pull requests, modify GitHub
settings, or change Git configuration unless the user explicitly requests it.



# Intelligent Climate Codex Execution Policy

For each implementation task, own the complete engineering and validation loop unless the task prompt explicitly narrows your authority.

## Required workflow

1. Verify the current branch, repository state, GitHub authentication, and pull-request state.
2. Read all authoritative specifications, architecture documents, ADRs, backlog sections, existing implementation, and relevant tests before editing.
3. Implement only the requested task. Preserve all explicit exclusions and observation-only safety requirements.
4. Review the complete diff for correctness, scope, persistence compatibility, Home Assistant API correctness, and unintended behavior.
5. Run every locally available validation command:

   * full pytest suite;
   * coverage;
   * Ruff lint;
   * Ruff format check;
   * mypy;
   * JSON validation;
   * project-specific safety tests;
   * `git diff --check`.
6. Fix every actionable local failure and rerun validation.
7. Commit and push the completed task.
8. Create or update the task pull request.
9. Monitor all required GitHub checks, including HACS, Hassfest, and Quality.
10. For each failed check:

    * retrieve the exact current run and job logs;
    * identify the demonstrated root cause;
    * make the smallest correct fix;
    * rerun local validation;
    * commit and push;
    * monitor the new checks.
11. Continue until every required check passes or a genuine external blocker prevents completion.
12. Never merge the pull request unless explicitly instructed by the repository owner.

## Failure handling

Do not stop merely because the first implementation or CI run fails.

Do not ask the owner to retrieve logs that are accessible through `gh`.

Do not rerun an unchanged failure without first inspecting its logs.

Do not weaken tests, coverage thresholds, typing, validation, or safety rules merely to make CI pass.

When local and CI environments differ, treat CI as authoritative, inspect the exact difference, and make a type-safe and behaviorally correct adjustment.

Stop only for a genuine blocker such as:

* missing or expired authentication;
* insufficient repository or workflow permissions;
* unavailable required external infrastructure;
* an unresolved product or architecture choice that cannot safely be inferred;
* an external service outage.

## Handoff artifact

At the end of every task, create:

```text
codex-handoff/task-XX-handoff.md
```

Replace `XX` with the backlog task number.

The handoff file must remain untracked and must include:

* task name and scope;
* authoritative documents reviewed;
* branch name;
* base and head commits;
* pull-request number and URL;
* complete file list;
* implementation summary;
* schema or persistence changes;
* tests added or changed;
* all validation commands and exact results;
* coverage percentage;
* CI run IDs, URLs, and final statuses;
* exact failure causes and fixes;
* final commit list;
* `git status`;
* `git diff --stat main...HEAD`;
* full `git diff main...HEAD`;
* remaining risks, blockers, or CI-only considerations;
* confirmation that excluded features were not introduced;
* confirmation that the pull request was not merged.

Print the absolute path to the handoff file in the final response.

If the handoff file would become excessively large because of raw logs, include the relevant failure sections rather than entire successful logs. Always include the complete source diff.

## Intelligent Climate safety boundary

Unless a task explicitly and authoritatively changes the project phase, do not introduce:

* Home Assistant service calls that control HVAC equipment;
* writable climate entities;
* physical command adapters;
* predictive control;
* platform forwarding outside the requested task;
* undocumented persistence formats;
* out-of-scope entities, devices, coordinators, options flows, diagnostics, or Repairs.

Preserve strict schema validation and stable identifiers.
