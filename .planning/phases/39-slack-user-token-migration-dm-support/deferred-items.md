# Phase 39 Deferred Items

Items discovered during execution that are out of scope for the current plan.

## Pre-existing test failures (not caused by Phase 39 changes)

### `tests/test_slack_channels.py::TestGetChannelsEndpoint::test_get_channels_returns_cached`

- **Discovered:** Plan 39-01, Task 2 verification
- **Status:** Pre-existing (verified via `git stash && pytest`)
- **Root cause:** Test provides only 2 `session.execute` side_effects, but the
  `/channels` route handler now calls `session.execute` 3 times:
    1. Auth lookup via `get_current_user` -> workspace_id
    2. `get_cached_channels(...)` -> integration row
    3. `get_selected_channels(...)` -> integration row (again)
- **Fix path:** Extend the `side_effect` list in `test_get_channels_returns_cached`
  to include a third result for the `get_selected_channels` call, or refactor
  the route to query the integration once and pass it into both helpers.
- **Out of scope because:** Plan 39-01 does not touch `get_channels`,
  `get_cached_channels`, or `get_selected_channels`. CONTEXT.md explicitly
  keeps the channel picker unchanged.
