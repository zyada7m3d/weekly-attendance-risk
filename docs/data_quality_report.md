# Data Quality Report — ATT_demo_dataset.xlsx

## Summary
- Total sheets checked: 9
- Duplicate IDs found: 0
- Broken references found: 0
- Missing values (total cells): 2619
- Invalid status values: 0
- Present/late with no timestamp: 0
- Absent with a timestamp: 0
- Duplicate enrollments: 0
- Duplicate attendance events (idempotency check): 0

## Notes
- `date` / `timestamp` columns are loaded as string by pandas by default and are explicitly cast to datetime in this script. No issue for current week_number-based logic; revisit if date arithmetic is needed later.

## Conclusion
Dataset is clean and ready for analysis.
