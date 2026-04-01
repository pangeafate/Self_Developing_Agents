# Example: Sprint Plan Self-Critique Output

This document demonstrates the structured output format for the two-pass self-critique
cycle that runs after every sprint plan is written. Two independent reviewer agents
evaluate the plan in parallel, then findings are consolidated and the plan is updated.

---

## Sprint Under Review

**SP_055: Add Notification Delivery System**

Goal: Add a notification system that delivers alerts to users via email and in-app
channels when key events occur (task overdue, assignment change, weekly summary).

---

## Iteration 1: Architect-Reviewer

**Scope**: Architecture risks, backward compatibility, deployment ordering, scope creep,
TDD compliance, missing edge cases, performance.

### Findings

1. **CRITICAL** — No rate limiting on notification dispatch. The plan describes a
   `dispatch_notifications()` function that iterates over all pending notifications and
   sends them immediately. For a user with 200 overdue tasks, this would fire 200 emails
   in a tight loop, likely hitting provider rate limits and causing partial delivery
   failures with no retry mechanism.

   *Recommendation*: Add a `NotificationBatch` abstraction with configurable
   `max_per_minute` throttling. Queue excess notifications for the next dispatch cycle.

2. **HIGH** — Deployment ordering risk. The plan creates a new `notifications` database
   table and immediately deploys code that queries it. If the migration script fails or
   runs after the code deploy, the application will crash with "table not found" errors
   on every notification check.

   *Recommendation*: Add an explicit deployment order section. Migration must run and be
   verified BEFORE code deployment. Add a defensive check: if the table query fails,
   log a warning and skip notification processing (do not crash the agent).

3. **HIGH** — Weekly summary has unbounded query. `gather_weekly_summary()` queries all
   tasks modified in the last 7 days with no pagination or row limit. For active users
   with thousands of tasks, this could time out or exhaust memory.

   *Recommendation*: Add `WEEKLY_SUMMARY_MAX_ITEMS = 100` cap. If exceeded, summarize
   top 100 by priority and note "and N more items" in the summary text.

4. **MEDIUM** — No user preference model. The plan sends all notification types to all
   users. There is no mechanism for users to opt out of specific notification types
   (e.g., "I don't want overdue alerts, only weekly summaries").

   *Recommendation*: Out of scope for this sprint, but add to "What We're NOT Doing"
   with a note that SP_056 should add user notification preferences. For now, document
   this limitation explicitly.

5. **LOW** — Test file naming inconsistency. The plan names the test file
   `test_notifications.py` but the domain module is `notification_delivery.py`. Convention
   in this codebase is `test_<module_name>.py`.

   *Recommendation*: Rename to `test_notification_delivery.py`.

---

## Iteration 2: Code-Reviewer

**Scope**: Verify factual claims against actual codebase. Check that referenced functions,
field names, signatures, imports, and table schemas actually exist. Find issues the
architect-reviewer missed.

### Findings

1. **CRITICAL** — Referenced function does not exist. The plan states: "Call existing
   `get_user_email()` from `src/lib/contacts.py`." However, the actual function in that
   module is `query_contact_by_id()` which returns a full contact dict. There is no
   `get_user_email()` helper. The plan would fail at implementation because the function
   call would raise `ImportError`.

   *Recommendation*: Either use `query_contact_by_id(contact_id)["email"]` directly, or
   add a thin wrapper `get_contact_email(contact_id: int) -> str | None` in the domain
   module. Do not assume helpers exist without checking.

2. **HIGH** — Wrong field name in database schema. The plan references a field called
   `notification_type` on the proposed notifications table, but later in the filtering
   logic it uses `type` as the field name. This would cause silent bugs where filters
   match nothing because the field name is wrong.

   *Recommendation*: Standardize on `notification_type` everywhere. Search-and-replace
   all instances of bare `type` in the plan.

3. **MEDIUM** — Missing import in test file. The plan's test examples import
   `NotificationPriority` from `src/lib/notification_delivery.py`, but this enum is never
   defined in the "Files to Create" section. The tests reference `NotificationPriority.HIGH`
   and `NotificationPriority.LOW` but the domain model section only defines
   `NotificationType`.

   *Recommendation*: Add `NotificationPriority` enum to the domain model section:
   `class NotificationPriority(str, Enum): HIGH = "high"; NORMAL = "normal"; LOW = "low"`.
   Add it to the `Notification` dataclass. Add priority-based ordering tests.

4. **MEDIUM** — Email channel assumes SMTP. The plan's email sending function uses
   `smtplib` directly. However, the existing codebase uses a CLI mail tool for all
   outbound email (visible in `src/lib/email_sender.py` which shells out to `himalaya`).
   Using `smtplib` would bypass the existing email infrastructure and require separate
   SMTP credentials that are not configured on the server.

   *Recommendation*: Use the existing `send_email()` function from `email_sender.py`
   instead of raw SMTP. This maintains consistency and avoids credential management.

5. **LOW** — Redundant database query. `check_overdue_tasks()` queries all tasks, then
   filters in Python for overdue ones. The database API supports filter parameters that
   could do this server-side, reducing data transfer.

   *Recommendation*: Use the database API's filter parameter:
   `filters={"field_due_date": {"lt": today}, "field_status": {"not": "done"}}`.

---

## Consolidated Action Items

| # | Severity | Source | Issue | Action |
|---|----------|--------|-------|--------|
| 1 | CRITICAL | architect | No rate limiting on dispatch | Add `NotificationBatch` with `max_per_minute` throttling |
| 2 | CRITICAL | code | `get_user_email()` does not exist | Use `query_contact_by_id()` or add thin wrapper |
| 3 | HIGH | architect | Deployment ordering risk | Add deployment order section; defensive table check |
| 4 | HIGH | architect | Unbounded weekly summary query | Add `WEEKLY_SUMMARY_MAX_ITEMS = 100` cap |
| 5 | HIGH | code | Field name mismatch (`type` vs `notification_type`) | Standardize on `notification_type` |
| 6 | MEDIUM | architect | No user preference model | Document as out-of-scope limitation |
| 7 | MEDIUM | code | `NotificationPriority` enum missing from plan | Add enum definition and wire into dataclass |
| 8 | MEDIUM | code | Email channel uses wrong sending mechanism | Use existing `send_email()` from `email_sender.py` |
| 9 | LOW | architect | Test file naming inconsistency | Rename to `test_notification_delivery.py` |
| 10 | LOW | code | Redundant in-Python filtering | Use database API server-side filters |

---

## Updated Plan Sections

The following sections of the sprint plan were updated to address CRITICAL and HIGH
findings. MEDIUM items were documented; LOW items were fixed inline.

### Added: Deployment Order (addresses #3)

```
## Deployment Order

1. Run migration script: `python scripts/create_notifications_table.py`
2. Verify table exists: `python scripts/verify_table.py --table notifications`
3. Deploy code: `bash scripts/deploy.sh`

If step 1 fails, do NOT proceed to step 3. The notification check includes a
defensive guard: if the table query raises an error, log a warning and return
an empty notification list (do not crash the agent).
```

### Updated: Technical Approach (addresses #1, #2, #5, #8)

- `dispatch_notifications()` now uses `NotificationBatch` with `max_per_minute=30`
  default. Excess notifications are deferred to the next cycle with a `deferred_at`
  timestamp.
- Replaced `get_user_email()` call with `query_contact_by_id(contact_id)["email"]`.
  Added a `get_contact_email()` convenience wrapper to the domain module with proper
  `None` handling for contacts without email addresses.
- All references to bare `type` field replaced with `notification_type`.
- Email sending now uses `send_email()` from `email_sender.py` instead of `smtplib`.

### Updated: Domain Model (addresses #7)

Added `NotificationPriority` enum:
```python
class NotificationPriority(str, Enum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
```

Added `priority: NotificationPriority` field to `Notification` dataclass with default
`NotificationPriority.NORMAL`.

### Updated: Testing Strategy (addresses #4, #9, #10)

- Test file renamed from `test_notifications.py` to `test_notification_delivery.py`.
- Added test: `test_weekly_summary_caps_at_100_items` — verifies that summaries with >100
  items are truncated with an "and N more" note.
- Added test: `test_dispatch_respects_rate_limit` — verifies that only `max_per_minute`
  notifications are sent per cycle.
- Added test: `test_overdue_check_uses_server_side_filter` — verifies the database API
  call includes filter parameters.
- Added tests for `NotificationPriority` ordering and default values.

### Updated: What We're NOT Doing (addresses #6)

Added:
- User notification preferences (opt-in/opt-out per notification type). Planned for a
  future sprint. All users receive all notification types in this version.

---

## Verdict

All 2 CRITICAL and 3 HIGH issues resolved in the plan before implementation begins.
3 MEDIUM issues addressed (2 fixed, 1 documented as out-of-scope). 2 LOW issues fixed
inline. The plan is approved for implementation.
