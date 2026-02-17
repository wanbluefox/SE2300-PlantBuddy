
import csv
import sqlite3
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Optional, List, Tuple


# ----------------------------
# Domain Models (Custom types)
# ----------------------------

@dataclass
class Room:
    room_id: Optional[int]
    name: str
    light_level: str   # LOW, MEDIUM, BRIGHT
    humidity_level: str  # LOW, NORMAL, HIGH


@dataclass
class Plant:
    plant_id: Optional[int]
    nickname: str
    plant_type: str   # TROPICAL, SUCCULENT, FICUS
    room_id: int
    notes: str


@dataclass
class CarePlan:
    plant_id: int
    care_type: str  # WATER, FERTILIZE, REPOT
    interval_days: int
    last_done: Optional[str]  # YYYY-MM-DD or None


# ----------------------------
# Constants / Rules
# ----------------------------

VALID_LIGHT_LEVELS = {"LOW", "MEDIUM", "BRIGHT"}
VALID_HUMIDITY_LEVELS = {"LOW", "NORMAL", "HIGH"}
VALID_PLANT_TYPES = {"TROPICAL", "SUCCULENT", "FICUS"}

# FR-3: Include REPOT
VALID_CARE_TYPES = {"WATER", "FERTILIZE", "REPOT"}

# FR-9: simple alert thresholds (days overdue)
ALERT_THRESHOLDS = {
    "WATER": 3,
    "FERTILIZE": 7,
    "REPOT": 30,
}

BASE_RULES = {
    "TROPICAL":  {"WATER": 7,  "FERTILIZE": 30, "REPOT": 180},
    "SUCCULENT": {"WATER": 14, "FERTILIZE": 60, "REPOT": 365},
    "FICUS":     {"WATER": 10, "FERTILIZE": 45, "REPOT": 270},
}

LIGHT_ADJUST = {"LOW": 2, "MEDIUM": 0, "BRIGHT": -2}
HUMIDITY_ADJUST = {"LOW": -1, "NORMAL": 0, "HIGH": 1}

MIN_INTERVAL_DAYS = 2

HEALTH_MAX = 100
HEALTH_MIN = 0


# ----------------------------
# Persistence (SQLite)
# ----------------------------

class PlantBuddyDB:
    def __init__(self, db_path: str = "plantbuddy.db") -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self._create_tables()

    def _create_tables(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS rooms (
                room_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                light_level TEXT NOT NULL,
                humidity_level TEXT NOT NULL
            );
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS plants (
                plant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                nickname TEXT NOT NULL,
                plant_type TEXT NOT NULL,
                room_id INTEGER NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(room_id) REFERENCES rooms(room_id) ON DELETE RESTRICT
            );
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS care_plans (
                plant_id INTEGER NOT NULL,
                care_type TEXT NOT NULL,
                interval_days INTEGER NOT NULL,
                last_done TEXT,
                PRIMARY KEY (plant_id, care_type),
                FOREIGN KEY(plant_id) REFERENCES plants(plant_id) ON DELETE CASCADE
            );
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS care_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                plant_id INTEGER NOT NULL,
                care_type TEXT NOT NULL,
                event_datetime TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(plant_id) REFERENCES plants(plant_id) ON DELETE CASCADE
            );
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS health_snapshots (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                plant_id INTEGER NOT NULL,
                snapshot_date TEXT NOT NULL,
                health_score INTEGER NOT NULL,
                FOREIGN KEY(plant_id) REFERENCES plants(plant_id) ON DELETE CASCADE
            );
        """)
        self.conn.commit()

    # ---- Rooms ----
    def add_room(self, room: Room) -> int:
        cur = self.conn.execute(
            "INSERT INTO rooms (name, light_level, humidity_level) VALUES (?, ?, ?)",
            (room.name, room.light_level, room.humidity_level),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_rooms(self) -> List[Room]:
        cur = self.conn.execute("SELECT room_id, name, light_level, humidity_level FROM rooms ORDER BY name;")
        return [Room(*row) for row in cur.fetchall()]

    def get_room(self, room_id: int) -> Optional[Room]:
        cur = self.conn.execute(
            "SELECT room_id, name, light_level, humidity_level FROM rooms WHERE room_id = ?",
            (room_id,),
        )
        row = cur.fetchone()
        return Room(*row) if row else None

    def update_room(self, room: Room) -> None:
        self.conn.execute(
            "UPDATE rooms SET name = ?, light_level = ?, humidity_level = ? WHERE room_id = ?",
            (room.name, room.light_level, room.humidity_level, room.room_id),
        )
        self.conn.commit()

    # ---- Plants ----
    def add_plant(self, plant: Plant) -> int:
        cur = self.conn.execute(
            "INSERT INTO plants (nickname, plant_type, room_id, notes) VALUES (?, ?, ?, ?)",
            (plant.nickname, plant.plant_type, plant.room_id, plant.notes),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_plants(self) -> List[Tuple[int, str, str, int, str, str]]:
        cur = self.conn.execute("""
            SELECT p.plant_id, p.nickname, p.plant_type, p.room_id, r.name, p.notes
            FROM plants p
            JOIN rooms r ON r.room_id = p.room_id
            ORDER BY p.nickname;
        """)
        return cur.fetchall()

    def get_plant(self, plant_id: int) -> Optional[Plant]:
        cur = self.conn.execute(
            "SELECT plant_id, nickname, plant_type, room_id, notes FROM plants WHERE plant_id = ?",
            (plant_id,),
        )
        row = cur.fetchone()
        return Plant(*row) if row else None

    def update_plant(self, plant: Plant) -> None:
        self.conn.execute(
            "UPDATE plants SET nickname = ?, plant_type = ?, room_id = ?, notes = ? WHERE plant_id = ?",
            (plant.nickname, plant.plant_type, plant.room_id, plant.notes, plant.plant_id),
        )
        self.conn.commit()

    def delete_plant(self, plant_id: int) -> None:
        self.conn.execute("DELETE FROM plants WHERE plant_id = ?", (plant_id,))
        self.conn.commit()

    # ---- Care Plans ----
    def upsert_care_plan(self, plan: CarePlan) -> None:
        self.conn.execute("""
            INSERT INTO care_plans (plant_id, care_type, interval_days, last_done)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(plant_id, care_type)
            DO UPDATE SET interval_days=excluded.interval_days, last_done=excluded.last_done;
        """, (plan.plant_id, plan.care_type, plan.interval_days, plan.last_done))
        self.conn.commit()

    def get_care_plan(self, plant_id: int, care_type: str) -> Optional[CarePlan]:
        cur = self.conn.execute("""
            SELECT plant_id, care_type, interval_days, last_done
            FROM care_plans
            WHERE plant_id = ? AND care_type = ?;
        """, (plant_id, care_type))
        row = cur.fetchone()
        return CarePlan(*row) if row else None

    # ---- Events ----
    def add_care_event(self, plant_id: int, care_type: str, event_datetime: str, notes: str) -> None:
        self.conn.execute("""
            INSERT INTO care_events (plant_id, care_type, event_datetime, notes)
            VALUES (?, ?, ?, ?)
        """, (plant_id, care_type, event_datetime, notes))
        self.conn.commit()

    def list_events_in_range(self, start_dt: str, end_dt: str) -> List[Tuple[int, int, str, str, str]]:
        # returns: event_id, plant_id, care_type, event_datetime, notes
        cur = self.conn.execute("""
            SELECT event_id, plant_id, care_type, event_datetime, notes
            FROM care_events
            WHERE event_datetime >= ? AND event_datetime < ?
            ORDER BY event_datetime ASC;
        """, (start_dt, end_dt))
        return cur.fetchall()

    def get_plant_label(self, plant_id: int) -> str:
        cur = self.conn.execute("""
            SELECT p.nickname, r.name
            FROM plants p JOIN rooms r ON r.room_id = p.room_id
            WHERE p.plant_id = ?
        """, (plant_id,))
        row = cur.fetchone()
        if not row:
            return f"Plant#{plant_id}"
        return f"{row[0]} (Room: {row[1]})"

    # ---- Health ----
    def add_health_snapshot(self, plant_id: int, snapshot_date: str, health_score: int) -> None:
        self.conn.execute("""
            INSERT INTO health_snapshots (plant_id, snapshot_date, health_score)
            VALUES (?, ?, ?)
        """, (plant_id, snapshot_date, health_score))
        self.conn.commit()

    def get_latest_health(self, plant_id: int) -> Optional[int]:
        cur = self.conn.execute("""
            SELECT health_score
            FROM health_snapshots
            WHERE plant_id = ?
            ORDER BY snapshot_date DESC, snapshot_id DESC
            LIMIT 1
        """, (plant_id,))
        row = cur.fetchone()
        return int(row[0]) if row else None

    def close(self) -> None:
        self.conn.close()


# ----------------------------
# Services (Business logic)
# ----------------------------

class ScheduleService:
    @staticmethod
    def compute_interval_days(plant_type: str, care_type: str, light_level: str, humidity_level: str) -> int:
        base_days = BASE_RULES[plant_type][care_type]
        if care_type == "REPOT":
            # Repot usually not affected by light/humidity in this simplified model
            return max(MIN_INTERVAL_DAYS, base_days)
        adjusted = base_days + LIGHT_ADJUST[light_level] + HUMIDITY_ADJUST[humidity_level]
        return max(MIN_INTERVAL_DAYS, adjusted)

    @staticmethod
    def compute_due_date(last_done: Optional[str], interval_days: int) -> date:
        if last_done is None:
            return date.today()
        last_done_date = datetime.strptime(last_done, "%Y-%m-%d").date()
        return last_done_date + timedelta(days=interval_days)


class HealthService:
    @staticmethod
    def compute_health_score(current_score: int, overdue_days: int, care_type: str) -> int:
        # Water overdue hurts more than fertilize; repot is light penalty.
        per_day_penalty = {"WATER": 2, "FERTILIZE": 1, "REPOT": 0}.get(care_type, 1)
        penalty = max(0, overdue_days) * per_day_penalty
        new_score = current_score - penalty
        return max(HEALTH_MIN, min(HEALTH_MAX, new_score))


# ----------------------------
# CLI Helpers
# ----------------------------

def input_non_empty(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("❌ Input cannot be empty.")


def input_choice(prompt: str, valid_choices: List[str]) -> str:
    valid_set = {c.upper() for c in valid_choices}
    while True:
        value = input(prompt).strip().upper()
        if value in valid_set:
            return value
        print(f"❌ Invalid choice. Valid: {', '.join(sorted(valid_set))}")


def input_int(prompt: str) -> int:
    while True:
        raw = input(prompt).strip()
        try:
            return int(raw)
        except ValueError:
            print("❌ Please enter an integer.")


def pick_room(db: PlantBuddyDB) -> int:
    rooms = db.list_rooms()
    if not rooms:
        print("No rooms found. Please create a room first.")
        return -1

    print("\nRooms:")
    for room in rooms:
        print(f"  {room.room_id}) {room.name} (Light={room.light_level}, Humidity={room.humidity_level})")

    while True:
        room_id = input_int("Select room_id: ")
        if db.get_room(room_id):
            return room_id
        print("❌ Invalid room_id.")


def rebuild_care_plans_for_plant(db: PlantBuddyDB, plant: Plant) -> None:
    room = db.get_room(plant.room_id)
    if room is None:
        return

    for care_type in ("WATER", "FERTILIZE", "REPOT"):
        interval_days = ScheduleService.compute_interval_days(
            plant_type=plant.plant_type,
            care_type=care_type,
            light_level=room.light_level,
            humidity_level=room.humidity_level,
        )
        existing = db.get_care_plan(plant.plant_id, care_type)
        last_done = existing.last_done if existing else None
        db.upsert_care_plan(CarePlan(plant_id=plant.plant_id, care_type=care_type, interval_days=interval_days, last_done=last_done))


# ----------------------------
# Dashboard + Reminders (FR-5, FR-6, FR-9)
# ----------------------------

def compute_dashboard(db: PlantBuddyDB) -> Tuple[List[str], List[str], List[str], List[str]]:
    today = date.today()
    plants = db.list_plants()

    due_today: List[str] = []
    overdue: List[str] = []
    upcoming: List[str] = []
    alerts: List[str] = []

    for plant_id, nickname, plant_type, room_id, room_name, notes in plants:
        for care_type in ("WATER", "FERTILIZE", "REPOT"):
            plan = db.get_care_plan(plant_id, care_type)
            if not plan:
                continue

            due_date = ScheduleService.compute_due_date(plan.last_done, plan.interval_days)
            days_until = (due_date - today).days
            label = f"{nickname} [{care_type}] due {due_date.isoformat()}"

            if days_until == 0:
                due_today.append(label)
            elif days_until < 0:
                overdue_days = -days_until
                overdue.append(label + f"  (OVERDUE {overdue_days}d)")

                # FR-9 alerts: show when overdue exceeds threshold
                threshold = ALERT_THRESHOLDS.get(care_type, 7)
                if overdue_days >= threshold:
                    alerts.append(f"⚠️ ALERT: {nickname} is {overdue_days}d overdue for {care_type} (threshold {threshold}d)")

                # FR-8 health update (simple rule-based)
                current_health = db.get_latest_health(plant_id)
                if current_health is None:
                    current_health = HEALTH_MAX
                new_health = HealthService.compute_health_score(current_health, overdue_days, care_type)
                db.add_health_snapshot(plant_id, today.strftime("%Y-%m-%d"), new_health)

            elif 1 <= days_until <= 7:
                upcoming.append(label + f"  (in {days_until}d)")

    return due_today, overdue, upcoming, alerts


def print_dashboard(db: PlantBuddyDB) -> None:
    due_today, overdue, upcoming, alerts = compute_dashboard(db)

    print("\n=== DASHBOARD ===")
    print(f"Today: {date.today().isoformat()}")

    print("\n--- Alerts ---")
    print("\n".join(alerts) if alerts else "None")

    print("\n--- Due Today ---")
    print("\n".join(due_today) if due_today else "None")

    print("\n--- Overdue ---")
    print("\n".join(overdue) if overdue else "None")

    print("\n--- Upcoming (7 days) ---")
    print("\n".join(upcoming) if upcoming else "None")


def print_startup_reminders(db: PlantBuddyDB) -> None:
    # FR-6: reminders at app start
    due_today, overdue, _, alerts = compute_dashboard(db)
    if not (alerts or due_today or overdue):
        print("✅ No reminders right now. You are up to date!")
        return

    print("\n=== STARTUP REMINDERS ===")
    if alerts:
        print("\nAlerts:")
        for a in alerts:
            print(a)

    if overdue:
        print("\nOverdue:")
        for item in overdue[:10]:
            print("• " + item)
        if len(overdue) > 10:
            print(f"…and {len(overdue) - 10} more overdue items.")

    if due_today:
        print("\nDue Today:")
        for item in due_today:
            print("• " + item)


# ----------------------------
# Reports + Export (FR-10)
# ----------------------------

def action_weekly_summary_and_export(db: PlantBuddyDB) -> None:
    today = date.today()
    start_day = today - timedelta(days=7)
    start_dt = datetime.combine(start_day, datetime.min.time()).strftime("%Y-%m-%d %H:%M:%S")
    end_dt = datetime.combine(today + timedelta(days=1), datetime.min.time()).strftime("%Y-%m-%d %H:%M:%S")

    events = db.list_events_in_range(start_dt, end_dt)

    # Build summary lines
    summary_lines: List[str] = []
    summary_lines.append(f"PlantBuddy Weekly Summary ({start_day.isoformat()} to {today.isoformat()})")
    summary_lines.append("-" * 60)

    if not events:
        summary_lines.append("No care events logged in the last 7 days.")
    else:
        for event_id, plant_id, care_type, event_datetime, notes in events:
            plant_label = db.get_plant_label(plant_id)
            note_part = f" | notes: {notes}" if notes else ""
            summary_lines.append(f"{event_datetime} | {plant_label} | {care_type}{note_part}")

    print("\n=== WEEKLY SUMMARY ===")
    print("\n".join(summary_lines))

    export_choice = input_choice("\nExport? (CSV/TXT/N): ", ["CSV", "TXT", "N"])
    if export_choice == "N":
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if export_choice == "TXT":
        filename = f"plantbuddy_weekly_{timestamp}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(summary_lines) + "\n")
        print(f"✅ Exported weekly summary to {filename}")
        return

    # CSV export
    filename = f"plantbuddy_weekly_{timestamp}.csv"
    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["event_datetime", "plant", "care_type", "notes"])
        for _, plant_id, care_type, event_datetime, notes in events:
            writer.writerow([event_datetime, db.get_plant_label(plant_id), care_type, notes])
    print(f"✅ Exported weekly summary to {filename}")


# ----------------------------
# CLI Actions (FR-1, FR-2, FR-7)
# ----------------------------

def action_manage_rooms(db: PlantBuddyDB) -> None:
    while True:
        print("\n--- Rooms ---")
        print("1) List rooms")
        print("2) Add room")
        print("3) Edit room")
        print("0) Back")
        choice = input_choice("Choice: ", ["1", "2", "3", "0"])

        if choice == "1":
            rooms = db.list_rooms()
            if not rooms:
                print("No rooms yet.")
            for room in rooms:
                print(f"{room.room_id}) {room.name} | Light={room.light_level} | Humidity={room.humidity_level}")

        elif choice == "2":
            name = input_non_empty("Room name: ")
            light_level = input_choice("Light level (LOW/MEDIUM/BRIGHT): ", list(VALID_LIGHT_LEVELS))
            humidity_level = input_choice("Humidity level (LOW/NORMAL/HIGH): ", list(VALID_HUMIDITY_LEVELS))
            try:
                room_id = db.add_room(Room(None, name, light_level, humidity_level))
                print(f"✅ Room added (room_id={room_id})")
            except sqlite3.IntegrityError:
                print("❌ Room name already exists.")

        elif choice == "3":
            rooms = db.list_rooms()
            if not rooms:
                print("No rooms to edit.")
                continue
            for room in rooms:
                print(f"{room.room_id}) {room.name} (Light={room.light_level}, Humidity={room.humidity_level})")
            room_id = input_int("Enter room_id to edit: ")
            room = db.get_room(room_id)
            if not room:
                print("❌ Invalid room_id.")
                continue

            new_name = input_non_empty(f"New name [{room.name}]: ")
            new_light = input_choice(f"New light (LOW/MEDIUM/BRIGHT) [{room.light_level}]: ", list(VALID_LIGHT_LEVELS))
            new_humidity = input_choice(f"New humidity (LOW/NORMAL/HIGH) [{room.humidity_level}]: ", list(VALID_HUMIDITY_LEVELS))
            db.update_room(Room(room_id, new_name, new_light, new_humidity))
            print("✅ Room updated.")

            # Recompute schedules for plants in that room (FR-4)
            plants = [p for p in (db.get_plant(pid) for pid, *_ in db.list_plants()) if p and p.room_id == room_id]
            for plant in plants:
                rebuild_care_plans_for_plant(db, plant)
            print("ℹ️ Updated schedules for plants in this room.")

        elif choice == "0":
            return


def action_add_plant(db: PlantBuddyDB) -> None:
    if not db.list_rooms():
        print("❌ You must create at least one room first.")
        return

    nickname = input_non_empty("Plant nickname: ")
    plant_type = input_choice("Plant type (TROPICAL/SUCCULENT/FICUS): ", list(VALID_PLANT_TYPES))
    room_id = pick_room(db)
    if room_id == -1:
        return
    notes = input("Notes (optional): ").strip()

    plant_id = db.add_plant(Plant(None, nickname, plant_type, room_id, notes))
    plant = db.get_plant(plant_id)
    rebuild_care_plans_for_plant(db, plant)
    db.add_health_snapshot(plant_id, date.today().strftime("%Y-%m-%d"), HEALTH_MAX)

    print(f"✅ Plant added (plant_id={plant_id}). Schedules + health initialized.")


def action_list_plants(db: PlantBuddyDB) -> None:
    plants = db.list_plants()
    if not plants:
        print("No plants yet.")
        return
    print("\nPlants:")
    for plant_id, nickname, plant_type, room_id, room_name, notes in plants:
        health = db.get_latest_health(plant_id)
        print(f"{plant_id}) {nickname} [{plant_type}] in {room_name} | health={health} | notes={notes}")


def action_edit_plant(db: PlantBuddyDB) -> None:
    action_list_plants(db)
    plant_id = input_int("Enter plant_id to edit: ")
    plant = db.get_plant(plant_id)
    if not plant:
        print("❌ Invalid plant_id.")
        return

    new_nickname = input_non_empty(f"New nickname [{plant.nickname}]: ")
    new_type = input_choice(f"New type (TROPICAL/SUCCULENT/FICUS) [{plant.plant_type}]: ", list(VALID_PLANT_TYPES))
    print("Select new room:")
    new_room_id = pick_room(db)
    if new_room_id == -1:
        return
    new_notes = input(f"New notes [{plant.notes}]: ").strip() or plant.notes

    updated = Plant(plant_id, new_nickname, new_type, new_room_id, new_notes)
    db.update_plant(updated)
    rebuild_care_plans_for_plant(db, updated)
    print("✅ Plant updated and schedules rebuilt.")


def action_delete_plant(db: PlantBuddyDB) -> None:
    action_list_plants(db)
    plant_id = input_int("Enter plant_id to delete: ")
    plant = db.get_plant(plant_id)
    if not plant:
        print("❌ Invalid plant_id.")
        return
    confirm = input_choice(f"Delete '{plant.nickname}'? (Y/N): ", ["Y", "N"])
    if confirm == "Y":
        db.delete_plant(plant_id)
        print("✅ Plant deleted.")


def action_log_care_event(db: PlantBuddyDB) -> None:
    action_list_plants(db)
    plant_id = input_int("Enter plant_id to log care for: ")
    plant = db.get_plant(plant_id)
    if not plant:
        print("❌ Invalid plant_id.")
        return

    care_type = input_choice("Care type (WATER/FERTILIZE/REPOT): ", list(VALID_CARE_TYPES))
    notes = input("Event notes (optional): ").strip()
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.add_care_event(plant_id, care_type, now_iso, notes)

    plan = db.get_care_plan(plant_id, care_type)
    if plan is None:
        rebuild_care_plans_for_plant(db, plant)
        plan = db.get_care_plan(plant_id, care_type)

    db.upsert_care_plan(CarePlan(plant_id, care_type, plan.interval_days, date.today().strftime("%Y-%m-%d")))

    # Small health restore for doing care (FR-8)
    current_health = db.get_latest_health(plant_id)
    if current_health is None:
        current_health = HEALTH_MAX
    restored = min(HEALTH_MAX, current_health + 5)
    db.add_health_snapshot(plant_id, date.today().strftime("%Y-%m-%d"), restored)

    print("✅ Care event logged. Care plan updated. Health snapshot saved.")


# ----------------------------
# Main Program Loop
# ----------------------------

def main() -> None:
    db = PlantBuddyDB()

    try:
        print("Welcome to PlantBuddy (Console Edition)")
        # FR-6 reminders at startup
        print_startup_reminders(db)

        while True:
            print("\n--- Main Menu ---")
            print("1) Dashboard (Due/Overdue/Upcoming + Alerts)")
            print("2) List plants")
            print("3) Add plant")
            print("4) Edit plant")
            print("5) Delete plant")
            print("6) Manage rooms")
            print("7) Log care event")
            print("8) Weekly summary + Export (CSV/TXT)")
            print("0) Exit")

            choice = input_choice("Choice: ", ["1", "2", "3", "4", "5", "6", "7", "8", "0"])

            if choice == "1":
                print_dashboard(db)
            elif choice == "2":
                action_list_plants(db)
            elif choice == "3":
                action_add_plant(db)
            elif choice == "4":
                action_edit_plant(db)
            elif choice == "5":
                action_delete_plant(db)
            elif choice == "6":
                action_manage_rooms(db)
            elif choice == "7":
                action_log_care_event(db)
            elif choice == "8":
                action_weekly_summary_and_export(db)
            elif choice == "0":
                print("Goodbye!")
                break

    finally:
        db.close()


if __name__ == "__main__":
    main()
