---
type: lifecycle
status: active
source_of_truth_for:
  - lifecycle-gates
read_when:
  - phase-review
  - choose-next-task
update_when:
  - lifecycle-policy-change
---

# Lifecycle

This lifecycle is not waterfall. A project may return to an earlier phase, insert an experiment, skip an irrelevant phase, change scope, pause, or retire. Skips must be documented.

| Phase | Goal | Gate | Minimal Outputs | Exit Criteria | Next Step | Returns |
|---|---|---|---|---|---|---|
| 0. Inception | Decide whether the idea is worth framing | soft | short note or brief stub | owner and problem candidate exist | discovery | retire |
| 1. Discovery | Understand the problem and users | soft | product notes, risks | key assumptions named | definition | inception |
| 2. Definition | Define scope and desired outcome | soft | brief, roadmap, requirements draft | scope and success criteria are clear | architecture | discovery |
| 3. Architecture | Choose baseline architecture | hard | architecture doc, ADRs | significant decisions accepted | bootstrap | definition |
| 4. Bootstrap | Create first running system | hard | runnable app, checks | `make check` passes | delivery | architecture |
| 5. Delivery | Build verified vertical slices | soft | tasks, tests, docs updates | user value is demonstrable | readiness or evolution | definition |
| 6. Production Readiness | Prove operational readiness | hard | runbooks, rollback, backups if needed | production risks accepted | operation | delivery |
| 7. Operation | Run and observe the system | hard | operational checks | incidents and releases are manageable | evolution | readiness |
| 8. Evolution | Improve or pivot based on evidence | soft | updated roadmap | next investment decision is recorded | delivery or retirement | discovery |
| 9. Retirement | Shut down safely | hard | export, deletion, decommission record | users and data are handled | close | operation |

Ready for development starts only after the definition and architecture gaps are addressed.
