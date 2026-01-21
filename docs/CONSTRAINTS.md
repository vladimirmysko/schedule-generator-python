# Constraints for Schedule Generation

This document defines the constraints that must be satisfied when generating the university timetable. These constraints are **mandatory** and cannot be violated under any circumstances.

## Overview

Сonstraints represent absolute requirements for a valid schedule. A schedule that violates any constraint is considered **infeasible** and must be rejected. The scheduling algorithm must ensure all constraints are satisfied before considering soft constraints or optimization criteria.

## Context

These constraints apply to the scheduling system of the University of the Republic of Kazakhstan.

---

## Key Concept: Streams

A **stream** is a group of student groups that attend the same class session together. Streams exist for all activity types:

- **Lectures** (дәрістер)
- **Practicals** (практикалық сабақ)
- **Laboratories** (зертханалық сабақ)

**Important:** Even a single group attending a class alone is considered a stream of one. All classes in the scheduling system are assigned to a stream.

The **stream size** is the total number of students across all groups in the stream.

---

## 1. Resource Conflict Constraints

### 1.1 Instructor Conflict

An instructor cannot be assigned to more than one class at the same time.

- Each instructor can teach at most **one lesson per slot** across all days
- This applies to all activity types (lectures, practices, labs)

### 1.2 Student Group Conflict

A student group cannot attend more than one class at the same time.

- Each student group can be scheduled for at most **one lesson per slot**
- Subgroups of the same group cannot have overlapping schedules

### 1.3 Room Conflict

A room cannot host more than one class at the same time.

- Each room can accommodate at most **one lesson per slot**
- This applies to all room types (lecture halls, classrooms, laboratories)

---

## 2. Room Constraints

### 2.1 Room Capacity

The number of students in a stream must not exceed the room's effective capacity.

#### Primary Rule

If a room with sufficient capacity is available, it must be used:
- Room capacity ≥ Stream size (total students in the stream)

#### Fallback: Capacity Buffer

The capacity buffer is only used **when no room with sufficient actual capacity is available**. It allows placing streams in rooms even when the official room capacity is slightly below the number of students.

| Stream Size | Buffer |
|-------------|--------|
| Small stream | 50% of stream size |
| Large stream | 20% of stream size |

For intermediate sizes, the buffer is calculated proportionally (linear interpolation).

#### Room Selection with Buffer

When using the buffer, the system selects the room with the **largest capacity** among available options (closest to the actual need).

**Example:**
- Stream: 30 students (single group or multiple groups combined)
- Available rooms: capacities 18, 16, 14, 12 (no room ≥ 30)
- Buffer (small stream) = 50% of 30 = 15 students
- Room 18: effective capacity = 18 + 15 = 33 → 30 ≤ 33 ✓
- Room 16: effective capacity = 16 + 15 = 31 → 30 ≤ 31 ✓
- **Selected: Room with capacity 18** (largest available)

#### Dead Groups

**Dead groups** (groups that don't attend classes) have their student count set to 0 and do not affect stream size calculations.

### 2.2 Special Room Restrictions

Rooms marked as `is_special=true` can only be used for their designated subjects.

| Room | Allowed Usage |
|------|---------------|
| IT Group | IT partner classes only |
| Спорт зал | Physical education (Дене шынықтыру) only |
| AVENCOM | Partner organization classes only |
| БҚВҒЗС | Partner organization classes only |

### 2.3 Subject-Specific Room Requirements

Certain subjects must be scheduled in specific rooms (defined in `subject-rooms.json`).

- If a subject has room restrictions, classes can only be assigned to rooms from the allowed list
- Room restrictions may apply to all class types or only to specific types (e.g., practice sessions)
- Example: Chemistry (Химия) must be held in room 112 at ул. Ихсанова, 44/1

---

## 3. Time Constraints

### 3.1 Working Hours

All classes must be scheduled within the defined working hours.

- Classes can only be scheduled in **Slots 1–13** (9:00 – 21:50)
- No classes may be scheduled outside these hours

### 3.2 Working Days

Classes can only be scheduled on valid working days.

- The academic week runs from **Monday to Friday** (5 days)
- No classes are scheduled on **Saturday or Sunday**

### 3.3 One Lesson = One Slot

Each lesson occupies exactly one time slot (50 minutes). Lessons cannot span multiple slots or be split across non-consecutive slots.

---

## 4. Instructor Constraints

### 4.1 Instructor Availability

Classes can only be scheduled when the assigned instructor is available (defined in `instructor-availability.json`).

- Instructors specify time slots when they are **NOT** available
- The scheduler must never assign classes during unavailable times
- Unavailability is defined per weekday and time slot

### 4.2 Instructor Day Constraints

Some instructors have day-based teaching restrictions (defined in `instructor-days.json`).

- **Year-Day Constraints**: An instructor may only teach specific year levels on specific days
  - Example: Instructor X can only teach 1st-year students on Tuesday and 2nd-year students on Monday
- **One-Day-Per-Week Constraints**: All classes for an instructor must be scheduled on the same day

---

## 5. Curriculum Constraints

### 5.1 Required Sessions (Soft Target)

The system aims to schedule as many required sessions as possible, but **100% completion is not required**.

- **Target:** 80–90% of required sessions successfully scheduled is considered a success
- If a course requires *n* lectures, *m* practices, and *k* labs per week, the system attempts to schedule all of them
- Unscheduled sessions are reported for manual resolution

### 5.2 Course Assignment Completeness

For each scheduled session, the assignment must be complete:

- A qualified instructor
- An appropriate room
- A valid time slot

**Note:** Not all sessions may be schedulable due to resource constraints (room availability, instructor conflicts, etc.). The system prioritizes maximizing the number of successfully scheduled sessions.

---

## 6. Shift Constraints

### 6.1 Shift Definitions

| Shift | Time Range | Slots |
|-------|------------|-------|
| First Shift | 9:00 – 14:00 | Slots 1–5 |
| Second Shift | 14:00 – 21:50 | Slots 6–13 |

**Important:** Each group should have classes in **only one shift** — either first shift or second shift, not both.

### 6.2 Shift Assignment by Year

| Year | Shift | Notes |
|------|-------|-------|
| **1st year** | First shift | Always |
| **2nd year** | Second shift | Always |
| **3rd year** | First shift | Exceptions possible (see below) |
| **4th year** | Automatic | Algorithm selects optimal shift per group |
| **5th year** | Automatic | Algorithm selects optimal shift per group |

#### First-Year Students
- Always scheduled in **first shift**
- No exceptions

#### Second-Year Students
- Always scheduled in **second shift**
- No exceptions

#### Third-Year Students
- Default: **first shift**
- **Exception:** If it's impossible to schedule a group for first shift on a given day, that **entire day** is transferred to second shift
- The exception applies per day, not per individual lesson

#### Fourth and Fifth-Year Students
- Shift is selected **automatically** by the algorithm based on the group's workload
- The algorithm determines the optimal shift for each group individually
- Once selected, the **entire group** studies in that shift (first or second)
- The goal is to find the shift that best accommodates all of the group's classes

### 6.3 Shift Boundary Flexibility

If it's impossible to schedule all first-shift classes before 14:00, the shift boundary can be extended:

- **Standard boundary:** 14:00 (Slot 5 ends at 13:50)
- **Extended boundary:** 16:00 (up to 2 additional slots)

This means first-shift groups may use Slots 6 and 7 (14:00–15:50) when necessary.

**Note:** This flexibility should be used sparingly and only when standard first-shift slots are insufficient.

---

## 7. Academic Constraints

### 7.1 No Duplicate Lessons

The same lesson (same course, same activity type, same group) cannot be scheduled more than once in the same slot.

### 7.2 Daily Load per Group

Each student group must have a balanced number of lessons per day:

| Constraint | Value |
|------------|-------|
| **Minimum** | 2 lessons per day |
| **Preferred** | 3 lessons per day |
| **Maximum** | 6 lessons per day |

- Groups should not be scheduled for only 1 lesson per day (inefficient for students)
- Groups should not exceed 6 lessons per day (excessive load)

### 7.3 Building Change Time

When consecutive classes are scheduled in **different buildings**, there must be one free slot (window) between them to allow students to travel between locations.

**Example — Different buildings:**
| Slot | Location | Valid? |
|------|----------|--------|
| 2 | ул. Ихсанова, 44/1 | |
| 3 | — (travel time) | ✓ Required gap |
| 4 | ул. Жангир хана, 51/4 | |

**Exception:** Buildings defined as "nearby" in `nearby-buildings.json` do not require a gap. Classes in nearby buildings can be scheduled back-to-back.

**Example — Nearby buildings (no gap required):**
| Slot | Location | Valid? |
|------|----------|--------|
| 2 | ул. Ихсанова, 44/1 | |
| 3 | пр. Н.Назарбаева, 208 | ✓ No gap needed (nearby) |

### 7.4 Maximum Windows per Day

Each student group should have **at most one window (free slot)** per day between their first and last class.

- A "window" is an empty slot between two scheduled classes
- Windows may be necessary for building changes (see C-7.3)
- Additional windows beyond one are undesirable and should be avoided

**Valid schedule (1 window):**
| Slot 1 | Slot 2 | Slot 3 | Slot 4 | Slot 5 |
|--------|--------|--------|--------|--------|
| Math | Physics | — | Chemistry | Biology |

**Invalid schedule (2 windows):**
| Slot 1 | Slot 2 | Slot 3 | Slot 4 | Slot 5 |
|--------|--------|--------|--------|--------|
| Math | — | Physics | — | Chemistry |

### 7.5 Dead Groups

Groups listed in `dead-groups.csv` are included in schedules but:

- Their student count is set to **0**
- They do not contribute to room capacity requirements
- They do not affect stream grouping calculations

---

## 8. Subgroup Scheduling Constraints

### 8.1 No "Walking" Subgroups

When a group is split into subgroups (e.g., for labs or practicals), both subgroups must have a lesson scheduled in the same slot. No subgroup should be left idle ("walking") while the other subgroup is in class.

**Invalid schedule:**
| Slot | Subgroup 1 | Subgroup 2 |
|------|------------|------------|
| 3 | Chemistry Lab | — (idle) |

**Valid schedule:**
| Slot | Subgroup 1 | Subgroup 2 |
|------|------------|------------|
| 3 | Chemistry Lab | Physics Lab |

### 8.2 Shared Instructor Between Subgroups

If both subgroups of a course share the same instructor, they cannot have lessons scheduled in parallel. In such cases:

1. **Preferred solution:** Assign one subgroup a different lesson (from another course that is also divided into subgroups), allowing both subgroups to be occupied simultaneously

2. **Fallback solution:** If no suitable parallel lesson is available, schedule the subgroup lessons at the **beginning or end of the day**, so the idle subgroup can arrive later or leave early (rather than waiting between classes)

**Example — Shared instructor fallback:**
| Slot | Subgroup 1 | Subgroup 2 |
|------|------------|------------|
| 1 | Chemistry Lab (Instructor A) | — (can arrive at Slot 2) |
| 2 | — (can leave) | Chemistry Lab (Instructor A) |

Or at end of day:
| Slot | Subgroup 1 | Subgroup 2 |
|------|------------|------------|
| 12 | Chemistry Lab (Instructor A) | — (can leave) |
| 13 | — (already left) | Chemistry Lab (Instructor A) |

---

## Summary Table

| Constraint ID | Constraint Name | Description |
|---------------|-----------------|-------------|
| C-1.1 | Instructor Conflict | No instructor teaches two classes simultaneously |
| C-1.2 | Student Group Conflict | No group attends two classes simultaneously |
| C-1.3 | Room Conflict | No room hosts two classes simultaneously |
| C-2.1 | Room Capacity | Room capacity ≥ class size; buffer used only as fallback |
| C-2.2 | Special Room Restrictions | Special rooms used only for designated subjects |
| C-2.3 | Subject Room Requirements | Subjects with room restrictions use allowed rooms only |
| C-3.1 | Working Hours | Classes within Slots 1–13 only |
| C-3.2 | Working Days | Monday–Friday only |
| C-3.3 | Slot Duration | One lesson = one slot |
| C-4.1 | Instructor Availability | Instructor available at scheduled time |
| C-4.2 | Instructor Day Constraints | Year-day and one-day-per-week rules respected |
| C-5.1 | Required Sessions | Target 80–90% of sessions scheduled (soft target) |
| C-5.2 | Assignment Completeness | Each scheduled session fully assigned |
| C-6.1 | Shift Definitions | Groups attend only one shift (first or second) |
| C-6.2 | Shift by Year | 1st→first, 2nd→second, 3rd→first*, 4th/5th→auto |
| C-6.3 | Shift Boundary Flexibility | First shift can extend by 2 slots if needed |
| C-7.1 | No Duplicates | No duplicate lessons in same slot |
| C-7.2 | Daily Load per Group | Min 2 (prefer 3), max 6 lessons per day |
| C-7.3 | Building Change Time | One free slot required between different buildings |
| C-7.4 | Maximum Windows | At most one window per group per day |
| C-7.5 | Dead Groups | Dead groups included with zero student count |
| C-8.1 | No Walking Subgroups | Both subgroups must have lessons in parallel |
| C-8.2 | Shared Instructor Subgroups | Use alternate lessons or schedule at day boundaries |

---

## Related Configuration Files

| File | Purpose |
|------|---------|
| `rooms.csv` | Room definitions with capacity and special flags |
| `instructor-availability.json` | Instructor unavailable time slots |
| `instructor-days.json` | Day-based teaching constraints |
| `subject-rooms.json` | Subject-specific room requirements |
| `dead-groups.csv` | Groups that don't attend classes |
| `nearby-buildings.json` | Groups of buildings located near each other |

---

## Notes

- Violations of constraints result in an **invalid schedule**
- The scheduling system must verify all constraints before finalizing any timetable
- Any proposed schedule modification must be checked against all constraints