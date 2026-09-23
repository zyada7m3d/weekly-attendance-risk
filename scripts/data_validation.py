"""
ATT Project — Data Analyst track
Step 2: Data Validation

Reads ATT_demo_dataset.xlsx and runs every check discussed:
  1. Load sheets + preview shape/head
  2. Fix date/timestamp dtypes
  3. Dtype report
  4. Missing values report
  5. Duplicate ID report
  6. Referential integrity report
  7. Value sanity checks (status values, present/absent timestamp logic,
     duplicate enrollments, duplicate attendance events)
  8. Writes a summary to docs/data_quality_report.md
  9. Saves the cleaned/converted sheets (with real datetime columns) to
     data/processed/ATT_demo_dataset_converted.xlsx

Run from the project root: python scripts/data_validation.py
(or from wherever IN_PATH resolves correctly)
"""

import pandas as pd

IN_PATH = "data/raw/ATT_demo_dataset.xlsx"
REPORT_PATH = "docs/data_quality_report.md"
OUT_PATH = "data/processed/ATT_demo_dataset_converted.xlsx"

# ---------------------------------------------------------------------
# 1. Load all sheets
# ---------------------------------------------------------------------
sheets = pd.read_excel(IN_PATH, sheet_name=None)

# ---------------------------------------------------------------------
# 2. Fix date/timestamp dtypes (loaded as string by default)
# ---------------------------------------------------------------------
sheets["AttendanceSessions"]["date"] = pd.to_datetime(sheets["AttendanceSessions"]["date"])
sheets["AttendanceEvents"]["timestamp"] = pd.to_datetime(sheets["AttendanceEvents"]["timestamp"])

# ---------------------------------------------------------------------
# 3. Preview: shape + head of every sheet
# ---------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 1: SHEET PREVIEW")
print("=" * 70)
for name, df in sheets.items():
    print(f"\n===== {name} =====")
    print("Shape:", df.shape)
    print(df.head())

# ---------------------------------------------------------------------
# 4. Dtype report
# ---------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 2: DTYPES")
print("=" * 70)
for name, df in sheets.items():
    print(f"\n===== {name} — dtypes =====")
    print(df.dtypes)

# ---------------------------------------------------------------------
# 5. Missing values report
# ---------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 3: MISSING VALUES")
print("=" * 70)
missing_report = {}
for name, df in sheets.items():
    missing = df.isnull().sum()
    missing = missing[missing > 0]
    missing_report[name] = missing
    if not missing.empty:
        print(f"\n===== {name} — missing values =====")
        print(missing)
    else:
        print(f"\n===== {name} — no missing values =====")

# ---------------------------------------------------------------------
# 6. Duplicate ID report
# ---------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 4: DUPLICATE IDs")
print("=" * 70)
key_columns = {
    "Rooms": "room_id",
    "Staff": "staff_id",
    "Courses": "course_code",
    "Sections": "section_id",
    "Students": "student_id",
    "Enrollment": "enrollment_id",
    "Timetable": "timetable_id",
    "AttendanceSessions": "session_id",
    "AttendanceEvents": "event_id",
}
dup_report = {}
for name, key in key_columns.items():
    df = sheets[name]
    dup_count = int(df[key].duplicated().sum())
    dup_report[name] = dup_count
    print(f"{name}: {dup_count} duplicate {key}")

# ---------------------------------------------------------------------
# 7. Referential integrity report
# ---------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 5: REFERENTIAL INTEGRITY")
print("=" * 70)
sections = sheets["Sections"]
courses = sheets["Courses"]
staff = sheets["Staff"]
enrollment = sheets["Enrollment"]
students = sheets["Students"]
timetable = sheets["Timetable"]
rooms = sheets["Rooms"]
sessions = sheets["AttendanceSessions"]
events = sheets["AttendanceEvents"]

ref_checks = [
    ("Sections.course_code -> Courses", sections["course_code"], courses["course_code"]),
    ("Sections.staff_id -> Staff", sections["staff_id"], staff["staff_id"]),
    ("Enrollment.student_id -> Students", enrollment["student_id"], students["student_id"]),
    ("Enrollment.section_id -> Sections", enrollment["section_id"], sections["section_id"]),
    ("Timetable.section_id -> Sections", timetable["section_id"], sections["section_id"]),
    ("Timetable.room_id -> Rooms", timetable["room_id"], rooms["room_id"]),
    ("Sessions.section_id -> Sections", sessions["section_id"], sections["section_id"]),
    ("Sessions.room_id -> Rooms", sessions["room_id"], rooms["room_id"]),
    ("Sessions.opened_by_staff_id -> Staff", sessions["opened_by_staff_id"], staff["staff_id"]),
    ("Events.session_id -> Sessions", events["session_id"], sessions["session_id"]),
    ("Events.student_id -> Students", events["student_id"], students["student_id"]),
]

ref_report = {}
for label, child_col, parent_col in ref_checks:
    bad_count = int((~child_col.isin(parent_col)).sum())
    ref_report[label] = bad_count
    print(f"{label}: {bad_count} broken references")

# ---------------------------------------------------------------------
# 8. Value sanity checks
# ---------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 6: VALUE SANITY CHECKS")
print("=" * 70)

valid_statuses = {"present", "late", "absent", "rejected_expired", "rejected_duplicate"}
bad_status_count = int((~events["status"].isin(valid_statuses)).sum())
print("Invalid status values:", bad_status_count)

bad_present_count = int(
    (events["status"].isin(["present", "late"]) & events["timestamp"].isnull()).sum()
)
print("Present/late with no timestamp:", bad_present_count)

bad_absent_count = int(
    ((events["status"] == "absent") & events["timestamp"].notnull()).sum()
)
print("Absent with a timestamp:", bad_absent_count)

dup_enroll_count = int(enrollment.duplicated(subset=["student_id", "section_id"]).sum())
print("Duplicate enrollments (same student+section):", dup_enroll_count)

dup_events_count = int(events.duplicated(subset=["session_id", "student_id"]).sum())
print("Duplicate attendance events (same session+student):", dup_events_count)

# ---------------------------------------------------------------------
# 9. Write the quality report
# ---------------------------------------------------------------------
import os

os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)

total_missing = sum(m.sum() for m in missing_report.values())
total_dupes = sum(dup_report.values())
total_broken_refs = sum(ref_report.values())

with open(REPORT_PATH, "w", encoding="utf-8") as f:
    f.write("# Data Quality Report — ATT_demo_dataset.xlsx\n\n")
    f.write("## Summary\n")
    f.write(f"- Total sheets checked: {len(sheets)}\n")
    f.write(f"- Duplicate IDs found: {total_dupes}\n")
    f.write(f"- Broken references found: {total_broken_refs}\n")
    f.write(f"- Missing values (total cells): {total_missing}\n")
    f.write(f"- Invalid status values: {bad_status_count}\n")
    f.write(f"- Present/late with no timestamp: {bad_present_count}\n")
    f.write(f"- Absent with a timestamp: {bad_absent_count}\n")
    f.write(f"- Duplicate enrollments: {dup_enroll_count}\n")
    f.write(f"- Duplicate attendance events (idempotency check): {dup_events_count}\n\n")

    f.write("## Notes\n")
    f.write(
        "- `date` / `timestamp` columns are loaded as string by pandas by "
        "default and are explicitly cast to datetime in this script. No "
        "issue for current week_number-based logic; revisit if date "
        "arithmetic is needed later.\n\n"
    )

    f.write("## Conclusion\n")
    if total_dupes == 0 and total_broken_refs == 0 and bad_status_count == 0 and dup_events_count == 0:
        f.write("Dataset is clean and ready for analysis.\n")
    else:
        f.write("Dataset needs fixes before use — see counts above.\n")

print(f"\nSaved report to: {REPORT_PATH}")

# ---------------------------------------------------------------------
# 10. Save the converted sheets (real datetime dtypes) as a new file
# ---------------------------------------------------------------------
os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)

with pd.ExcelWriter(OUT_PATH, engine="openpyxl") as writer:
    for name, df in sheets.items():
        df.to_excel(writer, sheet_name=name, index=False)

print(f"Saved converted dataset to: {OUT_PATH}")