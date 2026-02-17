# SE2300-PlantBuddy
A Personal Plant Care Tracker

PlantBuddy is a console-based personal plant care tracker that allows users to manage plant profiles, rooms, care schedules, care logs, health scores, reminders, alerts, and weekly reporting/export. All data is saved locally using SQLite so it persists between sessions.

---

## Features (Mapped to Functional Requirements)

### Plant Profiles (FR-1)
- Add plant (nickname, plant type, room, notes)
- View plant list
- Edit plant
- Delete plant

### Room Conditions (FR-2)
- Create rooms with light/humidity
- Edit room light/humidity
- Assign plants to rooms
- Editing a room triggers schedule recalculation for plants in that room

### Care Categories (FR-3)
- Care types supported:
  - `WATER`
  - `FERTILIZE`
  - `REPOT`

### Personalized Intervals (FR-4)
- Recommended care intervals are computed using a transparent rule table:
  - Base schedule depends on plant type
  - Water/Fertilize intervals adjusted by room light/humidity
  - Repot uses a long interval in this simplified model

### Dashboard (FR-5)
- Shows:
  - Due Today
  - Overdue
  - Upcoming (7 days)

### Reminders on Startup (FR-6)
- On program start, PlantBuddy displays:
  - Alerts
  - Overdue items
  - Due Today items

### Care Logging (FR-7)
- Log a care event for a plant:
  - Timestamp is saved automatically
  - Optional notes
- Updates `last_done` for that care type

### Health Score (FR-8)
- Each plant has a health score (0–100)
- Overdue tasks reduce health (rule-based)
- Logging care restores a small amount

### Alerts (FR-9)
- Alerts appear if overdue days exceed thresholds:
  - Water ≥ 3 days overdue
  - Fertilize ≥ 7 days overdue
  - Repot ≥ 30 days overdue

### Weekly Summary + Export (FR-10)
- Displays weekly care events (past 7 days)
- Export option:
  - CSV (`plantbuddy_weekly_YYYYMMDD_HHMMSS.csv`)
  - TXT (`plantbuddy_weekly_YYYYMMDD_HHMMSS.txt`)

### Persistence (FR-11)
- Uses `plantbuddy.db` (SQLite) to save:
  - rooms
  - plants
  - care plans
  - care events
  - health snapshots

---

## Requirements / Tech
- Python 3.10+ (recommended 3.11+)
- No external packages needed (uses standard library only)
- Runs on Windows/macOS/Linux

---

## How to Run

1. Put `plantbuddy.py` in a folder.
2. Open terminal in that folder.
3. Run:

```bash
python plantbuddy.py
