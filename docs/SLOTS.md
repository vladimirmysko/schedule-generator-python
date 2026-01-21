# Time Slots

This document defines the time slot structure used for scheduling university classes.

## Overview

Time slots are the fundamental units of scheduling in the university timetable system. Each slot represents a period during which a class session can be scheduled. All scheduling operations reference these slots when assigning activities to specific times.

## Slot Duration

Each activity (lecture, practice, or lab) lasts **50 minutes**. One lesson (class) corresponds to exactly one slot.

## Break Duration

Between consecutive slots, there is a **10-minute break** to allow students and instructors to move between classrooms and prepare for the next session.

## Schedule Range

Classes begin at **9:00** and the last class of the day starts at **20:00**.

## Shifts

The day is divided into two shifts:

| Shift | Time Range | Slots |
|-------|------------|-------|
| **First Shift** | 9:00 – 14:00 | Slots 1–5 |
| **Second Shift** | 14:00 – 21:50 | Slots 6–13 |

- **First Shift**: Covers morning classes from 9:00 until 14:00 (Slots 1 through 5)
- **Second Shift**: Covers afternoon and evening classes from 14:00 until the end of the day (Slots 6 through 13)

### Shift Assignment by Year

| Year | Shift | Notes |
|------|-------|-------|
| 1st year | First shift | Always |
| 2nd year | Second shift | Always |
| 3rd year | First shift | Per-day exceptions possible |
| 4th year | Automatic | Selected per group based on workload |
| 5th year | Automatic | Selected per group based on workload |

Each group should have classes in **only one shift** per day.

### Shift Boundary Flexibility

If necessary, the first shift boundary can be extended by up to 2 slots (until 16:00) when standard first-shift slots are insufficient.

## Available Slots

The following slots are available for scheduling:

1. **Slot 1**: 9:00 → 9:50
2. **Slot 2**: 10:00 → 10:50
3. **Slot 3**: 11:00 → 11:50
4. **Slot 4**: 12:00 → 12:50
5. **Slot 5**: 13:00 → 13:50
6. **Slot 6**: 14:00 → 14:50
7. **Slot 7**: 15:00 → 15:50
8. **Slot 8**: 16:00 → 16:50
9. **Slot 9**: 17:00 → 17:50
10. **Slot 10**: 18:00 → 18:50
11. **Slot 11**: 19:00 → 19:50
12. **Slot 12**: 20:00 → 20:50
13. **Slot 13**: 21:00 → 21:50

**Total**: 13 slots per day

## Slot Pattern

The slot pattern follows a consistent structure:

- Each slot starts on the hour (e.g., 9:00, 10:00, 11:00)
- Each slot ends 50 minutes later (e.g., 9:50, 10:50, 11:50)
- A 10-minute break occurs between the end of one slot and the start of the next

For example:

- 9:00 → 9:50 (activity)
- 9:50 → 10:00 (10-minute break)
- 10:00 → 10:50 (next activity)
- 10:50 → 11:00 (10-minute break)
- 11:00 → 11:50 (next activity)
- And so on...