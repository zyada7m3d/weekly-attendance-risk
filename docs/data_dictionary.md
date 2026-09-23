# Data Dictionary — ATT_demo_dataset.xlsx

**Project:** Smart Attendance & Classroom Verification (ATT)
**Owner:** Data Analyst track
**Source:** Synthetic seed data (no real student records), 9 sheets in one Excel workbook
**Last validated:** see `docs/data_quality_report.md` (0 duplicate IDs, 0 broken references)

---

## 1. Rooms
Physical rooms/labs where sessions can be held.

| Column | Type | Description |
|---|---|---|
| `room_id` | string (PK) | Unique room identifier |
| `room_name` | string | Display name (e.g. "Room 204") |
| `building` | string | Building name |
| `capacity` | int | Maximum number of students the room holds |
| `room_type` | string | e.g. lecture hall, lab |

---

## 2. Staff
Lecturers/TAs who can open sessions.

| Column | Type | Description |
|---|---|---|
| `staff_id` | string (PK) | Unique staff identifier |
| `name` | string | Full name |
| `email` | string | Contact email |
| `role` | string | e.g. lecturer, TA |
| `department` | string | Academic department |

---

## 3. Courses
Course catalog.

| Column | Type | Description |
|---|---|---|
| `course_code` | string (PK) | Unique course code (e.g. "CS101") |
| `course_name` | string | Full course title |
| `credit_hours` | int | Number of credit hours |
| `department` | string | Owning department |

---

## 4. Sections
A specific offering of a course, taught by one staff member in one semester.

| Column | Type | Description |
|---|---|---|
| `section_id` | string (PK) | Unique section identifier |
| `course_code` | string (FK → Courses) | Which course this section belongs to |
| `staff_id` | string (FK → Staff) | Lecturer/TA teaching this section |
| `semester` | string | e.g. "Fall-2026" |
| `capacity` | int | Max enrolled students |

---

## 5. Students
Student roster.

| Column | Type | Description |
|---|---|---|
| `student_id` | string (PK) | Unique student identifier |
| `name` | string | Full name |
| `email` | string | Contact email |
| `year_level` | int | Academic year (1–4) |
| `department` | string | Student's department |

---

## 6. Enrollment
Which students are registered in which sections. One row = one student in one section.

| Column | Type | Description |
|---|---|---|
| `enrollment_id` | string (PK) | Unique enrollment record ID |
| `student_id` | string (FK → Students) | The enrolled student |
| `section_id` | string (FK → Sections) | The section they're enrolled in |

**Note:** no duplicate (student_id, section_id) pairs exist in the validated dataset — a student cannot be enrolled twice in the same section.

---

## 7. Timetable
Weekly recurring time slots for each section.

| Column | Type | Description |
|---|---|---|
| `timetable_id` | string (PK) | Unique slot identifier |
| `section_id` | string (FK → Sections) | Which section this slot belongs to |
| `room_id` | string (FK → Rooms) | Where the session is held |
| `day_of_week` | string | Day the session recurs on |
| `start_time` | string (HH:MM) | Slot start time |
| `end_time` | string (HH:MM) | Slot end time |

---

## 8. AttendanceSessions
One actual instance of a scheduled session (a specific date, not the recurring weekly slot).

| Column | Type | Description |
|---|---|---|
| `session_id` | string (PK) | Unique session identifier |
| `section_id` | string (FK → Sections) | Which section this session belongs to |
| `timetable_id` | string (FK → Timetable) | Which recurring slot it was generated from |
| `room_id` | string (FK → Rooms) | Room used (may differ from the default timetable room) |
| `date` | datetime | Calendar date of this session |
| `week_number` | int | Week of the semester (1, 2, 3…) — used for weekly trend analysis |
| `opened_by_staff_id` | string (FK → Staff) | Who opened the session |
| `start_time` | string | Actual start time |
| `end_time` | string | Actual end time |

**Note:** `date` is loaded as text by pandas by default and must be explicitly converted with `pd.to_datetime()` — see `data_validation.py`.

---

## 9. AttendanceEvents
One row per student's attendance outcome for one session. This is the core transactional table everything else aggregates from.

| Column | Type | Description |
|---|---|---|
| `event_id` | string (PK) | Unique event identifier |
| `session_id` | string (FK → AttendanceSessions) | Which session this event belongs to |
| `student_id` | string (FK → Students) | Which student this event belongs to |
| `timestamp` | datetime (nullable) | When the scan happened. **Null when `status = absent`** — this is expected, not missing data. |
| `status` | string (enum) | One of: `present`, `late`, `absent`, `rejected_expired`, `rejected_duplicate` |

**Uniqueness constraint:** one (session_id, student_id) pair per row — enforced in the source data (idempotency check passed with 0 violations, matching ATT-FR-05's requirement).

**Status meaning:**
- `present` / `late` → counted as "attended" in all KPI/flag calculations
- `absent` → no timestamp by design
- `rejected_expired` → student scanned an expired QR token
- `rejected_duplicate` → student scanned again after already having a recorded event

---

## Derived / Output Files (produced by this track's scripts, not part of the source workbook)

| File | Produced by | Description |
|---|---|---|
| `data/processed/ATT_demo_dataset_converted.xlsx` | `data_validation.py` | Same 9 sheets, with `date`/`timestamp` as real datetime columns |
| `data/processed/fact_attendance.csv` | `build_fact_table.py` | AttendanceEvents joined with Sessions, Sections, Courses, Students — one row per event, 24 columns |
| `outputs/kpi_by_section.csv` | `04_dashboard_kpis.py` | Attendance rate, late rate, absent count per section |
| `outputs/kpi_by_student.csv` | `04_dashboard_kpis.py` | Same metrics per student |
| `outputs/low_attendance_warnings.csv` | `04_dashboard_kpis.py` | Students below the 75% attendance threshold |
| `outputs/weekly_features_and_flags.xlsx` | `05_rule_based_flags.py` | Per (student, section, week): cumulative features + rule-based risk flags + a lookahead label for later AI model evaluation |

---

## Known Gaps (data not yet available for the full rule-based flag set)

Per `ATT_User_Stories.md` (US-17), two rule-based flag types are not yet implementable with the current dataset:
- **Impossible-timing duplicates** — requires raw scan-attempt logs, not just the final recorded status per (session, student)
- **Abnormal correction volume** — requires a `CorrectionRequests` table (student correction requests with their state history), which does not exist yet in `ATT_demo_dataset.xlsx`

Both require the Backend track to extend the seed generator before these flags can be built.
