---
paths:
  - "1 - Projects/*/activities/**"
---
# Activities (A)
- One activity per note, in the imperative: "Build the dashboard", not "Dashboard".
- `owner` and `due` only based on the raw source. The due date comes from `facts.py date` with the message date as the base, and the rule used goes into the S's Routing.
- Completed: `status: done` + `completed_on` with the date from `facts.py now`. Never delete.
