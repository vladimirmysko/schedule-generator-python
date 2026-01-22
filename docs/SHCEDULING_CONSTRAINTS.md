# University Course Scheduling System: Constraints Specification

## Document Overview

This document defines all hard and soft constraints for the automated course scheduling system designed for universities in Kazakhstan. The system must comply with the requirements of the Ministry of Science and Higher Education of the Republic of Kazakhstan and follow the State Compulsory Education Standards (GOSO RK).

The scheduling system uses configuration files that define rooms, instructor constraints, subject requirements, and group preferences. This document describes how these configurations translate into scheduling constraints.

---

## 1. Definitions and Terminology

| Term | Definition |
|------|------------|
| **Academic Hour** | A teaching unit of 50 minutes (standard in Kazakhstan) |
| **Slot** | A single time period for one lesson (50 minutes + 10-minute break) |
| **Lesson** | One class session occupying exactly one slot |
| **Stream (Поток)** | A group of student groups attending the same class session together. Even a single group alone is a stream of one. All classes are assigned to a stream. |
| **Stream Size** | Total number of students across all groups in the stream |
| **First Shift** | Morning/early afternoon classes (slots 1–5, 9:00–14:00) |
| **Second Shift** | Afternoon/evening classes (slots 6–13, 14:00–21:50) |
| **Window** | An empty slot between two scheduled classes in a group's daily schedule |
| **Group (Группа)** | A cohort of students enrolled in the same program and year |
| **Subgroup** | A division of a group for laboratory or practical sessions |
| **Dead Group** | A group that appears in schedules but has 0 students (doesn't affect capacity) |
| **Elective (Элективный курс)** | A course chosen by students from a list of options |
| **Special Room** | A room reserved exclusively for specific subjects (e.g., sports hall, partner venues) |
| **Nearby Buildings** | Buildings close enough that no travel gap is required between consecutive classes |

---

## 2. Configuration Files

The system uses the following configuration files:

| File | Format | Purpose |
|------|--------|---------|
| `rooms.csv` | CSV | Master list of all available rooms with capacities |
| `dead-groups.csv` | CSV | Groups that don't attend classes (student count = 0) |
| `groups-second-shift.csv` | CSV | Groups forced to second shift for practicals |
| `subject-names-map.csv` | CSV | Bilingual subject name mappings (KZ ↔ RU) |
| `instructor-prefixes.csv` | CSV | Academic title prefixes mapping (KZ → RU) |
| `instructor-availability.json` | JSON | Instructor unavailability time slots |
| `instructor-rooms.json` | JSON | Instructor room preferences |
| `instructor-days.json` | JSON | Day-based teaching constraints |
| `subject-rooms.json` | JSON | Subject-specific room requirements |
| `group-buildings.json` | JSON | Building preferences by specialty group |
| `nearby-buildings.json` | JSON | Groups of buildings located near each other |

---

## 3. Hard Constraints

Hard constraints are **mandatory requirements** that must never be violated. A schedule violating any hard constraint is considered invalid.

### 3.1 Resource Conflict Constraints

#### HC-01: Room Single Allocation
- **Description**: A room can only be assigned to one class at any given time slot.
- **Formula**: `∀ room r, time slot t: |classes assigned to (r, t)| ≤ 1`

#### HC-02: Instructor Single Allocation
- **Description**: An instructor can only teach one class at any given time slot.
- **Formula**: `∀ instructor i, time slot t: |classes assigned to (i, t)| ≤ 1`

#### HC-03: Student Group Single Allocation
- **Description**: A student group (or subgroup) can only attend one class at any given time slot.
- **Formula**: `∀ group g, time slot t: |classes assigned to (g, t)| ≤ 1`

### 3.2 Capacity and Facility Constraints

#### HC-04: Room Capacity
- **Description**: The number of students in a stream must not exceed the room's effective capacity.
- **Primary Rule**: If a room with sufficient capacity is available, it must be used: `capacity(r) ≥ stream_size`
- **Fallback — Capacity Buffer**: The buffer is used ONLY when no room with sufficient actual capacity is available.

| Stream Size | Buffer |
|-------------|--------|
| Small stream | 50% of stream size |
| Large stream | 20% of stream size |

- For intermediate sizes, the buffer is calculated proportionally (linear interpolation).
- When using the buffer, select the room with the **largest capacity** among available options.

**Example:**
- Stream: 30 students
- Available rooms: capacities 18, 16, 14, 12 (no room ≥ 30)
- Buffer (small stream) = 50% of 30 = 15 students
- Room 18: effective capacity = 18 + 15 = 33 → 30 ≤ 33 ✓
- Room 16: effective capacity = 16 + 15 = 31 → 30 ≤ 31 ✓
- **Selected: Room with capacity 18** (largest available)

- **Dead Groups**: Groups listed in `dead-groups.csv` have student count = 0 and do not contribute to stream size calculations.

#### HC-05: Special Room Restrictions
- **Description**: Rooms marked with `is_special=true` in `rooms.csv` can only be used for their designated subjects.
- **Special Rooms**:
  - `IT Group` — IT partner classes only
  - `Спорт зал` — Physical education (Дене шынықтыру) only
  - `AVENCOM` — Partner organization classes only
  - `БҚВҒЗС` — Partner organization classes only
- **Rule**: Special rooms cannot be assigned to general classes.

#### HC-06: Subject-Specific Room Requirements
- **Description**: If a subject has room restrictions defined in `subject-rooms.json`, classes must be assigned to one of the specified rooms.
- **Configurations**:
  - `locations` — All class types must use specified rooms
  - `lecture` — Only lecture sessions are restricted
  - `practice` — Only practice/lab sessions are restricted
  - `lab` — Only laboratory sessions are restricted
- **Note**: If only `practice` is specified, lectures have no room restrictions.

#### HC-07: Equipment Requirements
- **Description**: If a class requires specific equipment (projector, specialized software, lab equipment), the assigned room must have that equipment.
- **Examples**: Chemistry lab equipment (room 112), computer labs (rooms 401, 403, 404, 407), physics lab (room 306)

### 3.3 Time-Related Constraints

#### HC-08: Working Hours
- **Description**: All classes must be scheduled within the defined working hours.
- **Rule**: Classes can only be scheduled in **Slots 1–13** (9:00 – 21:50)
- **No classes may be scheduled outside these hours**

#### HC-09: Working Days
- **Description**: Classes can only be scheduled on valid working days.
- **Rule**: The academic week runs from **Monday to Friday** (5 days)
- **No classes are scheduled on Saturday or Sunday**

#### HC-10: One Lesson = One Slot
- **Description**: Each lesson occupies exactly one time slot (50 minutes).
- **Rule**: Lessons cannot span multiple slots or be split across non-consecutive slots.

#### HC-11: Shift Assignment
- **Description**: Each group should have classes in **only one shift** per day — either first shift or second shift, not both.
- **Shift Definitions**:

| Shift | Time Range | Slots |
|-------|------------|-------|
| First Shift | 9:00 – 14:00 | Slots 1–5 |
| Second Shift | 14:00 – 21:50 | Slots 6–13 |

- **Assignment by Year**:

| Year | Shift | Notes |
|------|-------|-------|
| **1st year** | First shift | Always, no exceptions |
| **2nd year** | Second shift | Always, no exceptions |
| **3rd year** | First shift | Per-day exceptions possible (see below) |
| **4th year** | Automatic | Algorithm selects optimal shift per group |
| **5th year** | Automatic | Algorithm selects optimal shift per group |

- **Third-Year Exception**: If it's impossible to schedule a 3rd-year group for first shift on a given day, that **entire day** is transferred to second shift. The exception applies per day, not per individual lesson.
- **Fourth/Fifth-Year**: Shift is selected automatically by the algorithm based on the group's workload. Once selected, the entire group studies in that shift.
- **Source**: Groups listed in `groups-second-shift.csv` override default assignment.

#### HC-12: Shift Boundary Flexibility
- **Description**: If it's impossible to schedule all first-shift classes before 14:00, the shift boundary can be extended.
- **Standard boundary**: 14:00 (Slot 5 ends at 13:50)
- **Extended boundary**: 16:00 (up to 2 additional slots: Slots 6 and 7)
- **Rule**: This flexibility should be used sparingly and only when standard first-shift slots are insufficient.

#### HC-13: Instructor Availability
- **Description**: Classes can only be assigned to time slots when the instructor is available.
- **Source**: `instructor-availability.json` defines `weekly_unavailable` slots per instructor.
- **Format**: Each instructor has a map of days to unavailable time slots (e.g., `"friday": ["09:00", "10:00", ...]`)
- **Rule**: The scheduler must never assign classes during unavailable times.

#### HC-14: Instructor Day Constraints
- **Description**: Some instructors can only teach certain student years on specific days.
- **Source**: `instructor-days.json` defines `year_days` mapping.
- **Example**: If instructor has `{"1": ["tuesday"], "2": ["monday"]}`, they can only teach 1st-year students on Tuesday and 2nd-year students on Monday.
- **Optional**: `one_day_per_week: true` requires all of an instructor's classes to be on the same day.

### 3.4 Academic Constraints

#### HC-15: No Duplicate Lessons
- **Description**: The same lesson (same course, same activity type, same group) cannot be scheduled more than once in the same slot.

#### HC-16: Daily Load per Group
- **Description**: Each student group must have a balanced number of lessons per day.
- **Constraints**:

| Constraint | Value |
|------------|-------|
| **Minimum** | 2 lessons per day |
| **Preferred** | 3 lessons per day |
| **Maximum** | 6 lessons per day |

- Groups should not be scheduled for only 1 lesson per day (inefficient for students)
- Groups should not exceed 6 lessons per day (excessive load)

#### HC-17: Building Change Time
- **Description**: When consecutive classes are scheduled in **different buildings**, there must be one free slot (window) between them to allow students to travel.
- **Example — Different buildings**:

| Slot | Location | Valid? |
|------|----------|--------|
| 2 | ул. Ихсанова, 44/1 | |
| 3 | — (travel time) | ✓ Required gap |
| 4 | ул. Жангир хана, 51/4 | |

- **Exception**: Buildings defined as "nearby" in `nearby-buildings.json` do not require a gap. Classes in nearby buildings can be scheduled back-to-back.
- **Example — Nearby buildings (no gap required)**:

| Slot | Location | Valid? |
|------|----------|--------|
| 2 | ул. Ихсанова, 44/1 | |
| 3 | пр. Н.Назарбаева, 208 | ✓ No gap needed (nearby) |

#### HC-18: Maximum Windows per Day
- **Description**: Each student group should have **at most one window (free slot)** per day between their first and last class.
- A "window" is an empty slot between two scheduled classes
- Windows may be necessary for building changes (see HC-17)
- Additional windows beyond one are undesirable and should be avoided

**Valid schedule (1 window):**
| Slot 1 | Slot 2 | Slot 3 | Slot 4 | Slot 5 |
|--------|--------|--------|--------|--------|
| Math | Physics | — | Chemistry | Biology |

**Invalid schedule (2 windows):**
| Slot 1 | Slot 2 | Slot 3 | Slot 4 | Slot 5 |
|--------|--------|--------|--------|--------|
| Math | — | Physics | — | Chemistry |

#### HC-19: Assignment Completeness
- **Description**: For each scheduled session, the assignment must be complete with:
  - A qualified instructor
  - An appropriate room
  - A valid time slot

### 3.5 Subgroup Constraints

#### HC-20: No "Walking" Subgroups
- **Description**: When a group is split into subgroups (e.g., for labs or practicals), both subgroups must have a lesson scheduled in the same slot. No subgroup should be left idle ("walking") while the other subgroup is in class.

**Invalid schedule:**
| Slot | Subgroup 1 | Subgroup 2 |
|------|------------|------------|
| 3 | Chemistry Lab | — (idle) |

**Valid schedule:**
| Slot | Subgroup 1 | Subgroup 2 |
|------|------------|------------|
| 3 | Chemistry Lab | Physics Lab |

#### HC-21: Shared Instructor Between Subgroups
- **Description**: If both subgroups of a course share the same instructor, they cannot have lessons scheduled in parallel.
- **Preferred solution**: Assign one subgroup a different lesson (from another course that is also divided into subgroups), allowing both subgroups to be occupied simultaneously
- **Fallback solution**: Schedule the subgroup lessons at the **beginning or end of the day**, so the idle subgroup can arrive later or leave early (rather than waiting between classes)

**Example — Shared instructor fallback (start of day):**
| Slot | Subgroup 1 | Subgroup 2 |
|------|------------|------------|
| 1 | Chemistry Lab (Instructor A) | — (can arrive at Slot 2) |
| 2 | — (can leave) | Chemistry Lab (Instructor A) |

**Example — Shared instructor fallback (end of day):**
| Slot | Subgroup 1 | Subgroup 2 |
|------|------------|------------|
| 12 | Chemistry Lab (Instructor A) | — (can leave) |
| 13 | — (already left) | Chemistry Lab (Instructor A) |

### 3.6 Special Program Constraints

#### HC-22: Physical Education Requirements
- **Description**: Physical education classes require sports facilities and must be scheduled according to facility availability.
- **Rule**: PE classes (Дене шынықтыру) must be assigned to `Спорт зал` at `ул. 8 Марта, 125/1`.

#### HC-23: Language Group Separation
- **Description**: For courses taught in multiple languages (Kazakh, Russian, English), groups must be separated appropriately, and instructors must be assigned based on their language of instruction capability.
- **Support**: `subject-names-map.csv` provides bilingual subject name mappings (Kazakh ↔ Russian) for matching across documents.

#### HC-24: Specialty Building Exclusivity
- **Description**: Certain buildings are reserved exclusively for specific specialty groups. Groups with these specialties MUST be assigned to their designated buildings, and groups with OTHER specialties CANNOT use these buildings.
- **Source**: `group-buildings.json` defines exclusive building assignments.
- **Current Assignments**:
  - `ВЕТ` (Veterinary) → `ул. Жангир хана, 51/4` (exclusive)
  - `СТР` (Construction) → `ул. Чапаева 69` (exclusive)
  - `АРХ` (Architecture) → `ул. Чапаева 69` (exclusive)
  - `ЗК` (Land Cadastre) → `ул. Чапаева 69` (exclusive)
  - `ЮР` (Legal) → `ул. Победа, 137/1` (exclusive)
- **Rules**:
  1. Classes for ВЕТ groups can ONLY be scheduled at `ул. Жангир хана, 51/4`
  2. Classes for СТР, АРХ, ЗК groups can ONLY be scheduled at `ул. Чапаева 69`
  3. Classes for ЮР groups can ONLY be scheduled at `ул. Победа, 137/1`
  4. Groups with other specialties CANNOT be scheduled at these addresses
- **Stream Condition**: This constraint applies ONLY when the entire stream (поток) consists of groups from the same specialty. If a stream contains mixed specialties (e.g., ВЕТ + non-ВЕТ groups), the building exclusivity constraint does NOT apply, and the class may be scheduled at any suitable location.
- **Priority**: Subject-specific room requirements (`subject-rooms.json`) have HIGHER priority than specialty building assignments. If a subject requires a specific room (e.g., computer lab at `ул. Ихсанова, 44/1`), that requirement overrides the specialty building constraint.

---

## 4. Soft Constraints

Soft constraints are **preferences** that should be satisfied when possible. Violations result in penalty scores but do not invalidate the schedule. The system should minimize the total penalty.

### 4.1 Curriculum Soft Targets

#### SC-01: Required Sessions Target
- **Description**: The system aims to schedule as many required sessions as possible, but 100% completion is not required.
- **Target**: 80–90% of required sessions successfully scheduled is considered a success
- **Rule**: If a course requires *n* lectures, *m* practices, and *k* labs per week, the system attempts to schedule all of them
- **Reporting**: Unscheduled sessions are reported for manual resolution
- **Weight**: HIGH

### 4.2 Student-Centered Constraints

#### SC-02: Minimize Student Idle Time (Gaps)
- **Description**: Minimize gaps between consecutive classes for student groups.
- **Penalty**: Points per gap hour in a student's daily schedule.
- **Weight**: HIGH

#### SC-03: Balanced Daily Load
- **Description**: Distribute classes evenly across the week for each student group.
- **Penalty**: Points for days with significantly more/fewer classes than average.
- **Weight**: MEDIUM

#### SC-04: Avoid Early Morning Classes After Late Classes
- **Description**: If a group has classes ending late (after 18:00), avoid scheduling their first class before 09:00 the next day.
- **Penalty**: Points per violation.
- **Weight**: MEDIUM

#### SC-05: Class Start Time Consistency
- **Description**: Prefer consistent start times for the first class of the day for student groups.
- **Penalty**: Points for variation in daily start times.
- **Weight**: LOW

#### SC-06: Minimize Building Transitions
- **Description**: When consecutive classes are in different buildings, allow adequate travel time unless buildings are in the same nearby group.
- **Source**: `nearby-buildings.json` defines groups of buildings that are close together.
- **Rule**: 
  - Buildings in the same nearby group: No gap required (back-to-back scheduling allowed)
  - Buildings in different groups or not grouped: Standard 1-slot gap required
- **Current Nearby Group**: `ул. Ихсанова, 44/1` and `пр. Н.Назарбаева, 208` are nearby
- **Penalty**: Points for tight transitions (< 1 slot) between non-nearby buildings.
- **Weight**: HIGH

### 4.3 Instructor-Centered Constraints

#### SC-07: Minimize Instructor Idle Time
- **Description**: Minimize gaps between classes in an instructor's daily schedule.
- **Penalty**: Points per gap hour.
- **Weight**: MEDIUM

#### SC-08: Instructor Time Preferences
- **Description**: Respect instructor preferences for teaching times (morning/afternoon/evening).
- **Penalty**: Points per class scheduled outside preferred times.
- **Weight**: MEDIUM

#### SC-09: Instructor Day Preferences
- **Description**: Respect instructor preferences for specific teaching days.
- **Penalty**: Points per class on non-preferred days.
- **Weight**: LOW

#### SC-10: Maximum Daily Teaching Load
- **Description**: Prefer not to exceed 6 academic hours of teaching per day for instructors.
- **Penalty**: Points per hour over the limit.
- **Weight**: MEDIUM

#### SC-11: Consecutive Classes for Part-Time Instructors
- **Description**: Group classes for part-time instructors to minimize their required campus visits.
- **Penalty**: Points per additional day a part-time instructor must visit.
- **Weight**: HIGH

#### SC-12: Instructor Room Preferences
- **Description**: Assign instructors to their preferred rooms when specified in `instructor-rooms.json`.
- **Configurations**:
  - `locations` — Preferred rooms for all class types
  - `lecture` — Preferred rooms for lecture sessions only
  - `practice` — Preferred rooms for practice sessions only
- **Example**: Instructor Бурахта В.А. prefers `Г-пот` for lectures and room `112` for practice.
- **Penalty**: Points for not using preferred room.
- **Weight**: MEDIUM

### 4.4 Room Utilization Constraints

#### SC-13: Room Capacity Fit
- **Description**: Prefer rooms where capacity closely matches class size to avoid wasting space.
- **Penalty**: Points proportional to unused capacity percentage (wasted space)
- **Note**: When using capacity buffer (see HC-04), select the room with the largest capacity among available options.
- **Weight**: LOW

#### SC-14: Minimize Room Fragmentation
- **Description**: Prefer consecutive bookings in the same room to reduce setup/cleanup overhead.
- **Penalty**: Points for single-slot gaps in room schedules.
- **Weight**: LOW

### 4.5 Pedagogical Constraints

#### SC-15: Lecture Before Practical/Seminar
- **Description**: Prefer scheduling lecture sessions earlier in the week than their corresponding practical/seminar sessions.
- **Penalty**: Points if practical precedes lecture for the same topic.
- **Weight**: MEDIUM

#### SC-16: Laboratory Distribution
- **Description**: Prefer spreading laboratory sessions throughout the week rather than clustering them.
- **Penalty**: Points for consecutive lab sessions on the same day (beyond single 4-hour lab).
- **Weight**: MEDIUM

#### SC-17: Difficult Subject Timing
- **Description**: Prefer scheduling mathematically or cognitively intensive subjects in morning hours when students are more alert.
- **Penalty**: Points for difficult subjects scheduled after 16:00.
- **Weight**: LOW

### 4.6 Administrative Constraints

#### SC-18: Department Meeting Blocks
- **Description**: Reserve common time slots (e.g., Wednesday afternoon) for departmental meetings.
- **Penalty**: Points for classes scheduled during meeting blocks for department staff.
- **Weight**: MEDIUM

#### SC-19: Elective Course Accessibility
- **Description**: Elective courses should be scheduled to minimize conflicts with required courses.
- **Penalty**: Points for elective/required course conflicts affecting student choice.
- **Weight**: HIGH

#### SC-20: Course Section Balance
- **Description**: For courses with multiple sections, balance enrollment and schedule times equitably.
- **Penalty**: Points for significant imbalance in section sizes or timing.
- **Weight**: LOW

### 4.7 Kazakhstan-Specific Constraints

#### SC-21: State Language Priority
- **Description**: For courses offered in both Kazakh and Russian, prefer optimal time slots for Kazakh-language sections as per state language promotion policies.
- **Penalty**: Points if Russian sections have significantly better time slots.
- **Weight**: LOW (institution-dependent)

#### SC-22: Climate Considerations
- **Description**: In winter months, prefer not to start classes too early (before 09:00) due to harsh continental climate conditions affecting commute.
- **Penalty**: Points for early classes during winter semester (January–February).
- **Weight**: LOW

---

## 5. Constraint Priority and Room Assignment

### 5.1 Room Assignment Priority

When the scheduler assigns rooms, constraints are applied in this order (highest to lowest priority):

1. **Subject rooms** (`subject-rooms.json`) — Required rooms for specific subjects (e.g., chemistry lab, computer labs) — highest priority
2. **Specialty building exclusivity** (`group-buildings.json`) — Hard constraint: specialty groups must use their designated buildings (only when entire stream is same specialty)
3. **Instructor rooms** (`instructor-rooms.json`) — Preferred rooms for specific instructors
4. **General room pool** (`rooms.csv`) — Any available room meeting capacity requirements

### 5.2 Time Constraint Priority

Time constraints are handled in this order:

1. **Instructor availability** (`instructor-availability.json`) — Hard constraint, never schedule during unavailable times
2. **Instructor days** (`instructor-days.json`) — Restrict which days instructors can teach certain years
3. **Shift assignment** — First/second shift based on year and `groups-second-shift.csv` exceptions

---

## 6. Constraint Weights and Prioritization

### 6.1 Weight Categories

| Category | Weight Range | Description |
|----------|--------------|-------------|
| CRITICAL | N/A | Hard constraints – must not be violated |
| HIGH | 100–200 points | Significant impact on schedule quality |
| MEDIUM | 50–99 points | Moderate impact, should be respected |
| LOW | 10–49 points | Minor preference, optimize if possible |

### 6.2 Default Weight Configuration

```
# Hard Constraints (Infinite penalty / Rejection)
HC-01 to HC-24: MANDATORY

# Soft Constraints
SC-01 (Required Sessions Target): 180
SC-02 (Student Gaps): 150
SC-03 (Balanced Load): 60
SC-04 (Late-Early Sequence): 70
SC-05 (Start Consistency): 30
SC-06 (Building Transitions): 120
SC-07 (Instructor Gaps): 80
SC-08 (Instructor Time Pref): 60
SC-09 (Instructor Day Pref): 40
SC-10 (Daily Teaching Load): 70
SC-11 (Part-Time Grouping): 100
SC-12 (Instructor Room Pref): 75
SC-13 (Room Capacity Fit): 30
SC-14 (Room Fragmentation): 20
SC-15 (Lecture-Practical Order): 75
SC-16 (Lab Distribution): 65
SC-17 (Difficult Subject Timing): 45
SC-18 (Meeting Blocks): 55
SC-19 (Elective Accessibility): 100
SC-20 (Section Balance): 35
SC-21 (State Language Priority): 20
SC-22 (Climate Considerations): 15
```

---

## 7. Input Data Requirements

### 7.1 Configuration Files

The system requires the following configuration files:

1. **rooms.csv** — Master list of all available rooms
   - Fields: `name`, `capacity`, `address`, `is_special`
   - Special rooms (`is_special=true`) are reserved for specific subjects

2. **dead-groups.csv** — Groups that don't attend classes
   - Field: `name`
   - These groups appear in output but have student count = 0

3. **groups-second-shift.csv** — Groups forced to second shift
   - Field: `name`
   - Override default year-based shift assignment

4. **subject-names-map.csv** — Bilingual subject mappings
   - Fields: Kazakh Name; Russian Name (semicolon delimiter)
   - Used for matching subjects across documents

5. **instructor-prefixes.csv** — Academic title mappings
   - Fields: `kz`, `ru`
   - Maps Kazakh prefixes to Russian equivalents

6. **instructor-availability.json** — Instructor unavailability
   - Structure: `[{name, weekly_unavailable: {day: [times]}}]`

7. **instructor-rooms.json** — Instructor room preferences
   - Structure: `{name: {locations/lecture/practice: [{address, room}]}}`

8. **instructor-days.json** — Day-based teaching constraints
   - Structure: `[{name, year_days: {year: [days]}, one_day_per_week}]`

9. **subject-rooms.json** — Subject room requirements
   - Structure: `{subject: {locations/lecture/practice/lab: [{address, room}]}}`

10. **group-buildings.json** — Specialty building preferences
    - Structure: `{specialty: {addresses: [{address, rooms?}]}}`

11. **nearby-buildings.json** — Building proximity groups
    - Structure: `{groups: [{addresses: [address, ...]}]}`

### 7.2 Required Data Entities

1. **Courses (Дисциплины)**
   - Course code and name (in Kazakh and Russian via `subject-names-map.csv`)
   - Credit hours (ECTS credits)
   - Contact hours breakdown (lecture/seminar/lab)
   - Required room type and equipment
   - Department ownership
   - Language of instruction

2. **Instructors (Преподаватели)**
   - Full name and ID
   - Academic title prefix (via `instructor-prefixes.csv`)
   - Department affiliation
   - Employment type (full-time/part-time/visiting)
   - Courses qualified to teach
   - Language proficiency
   - Availability schedule (via `instructor-availability.json`)
   - Room preferences (via `instructor-rooms.json`)
   - Day constraints (via `instructor-days.json`)

3. **Student Groups (Учебные группы)**
   - Group code and name (e.g., "ВЕТ-31 О", "СТР-21 ОК")
   - Program and year (extracted from group code)
   - Number of students (0 for dead groups)
   - Subgroup divisions
   - Language track (Kazakh/Russian)
   - Specialty prefix (for building preferences)
   - Shift override (via `groups-second-shift.csv`)

4. **Rooms (Аудитории)** — from `rooms.csv`
   - Room number and building address
   - Capacity
   - Special room flag
   - Subject restrictions (via `subject-rooms.json`)

5. **Time Slots**
   - Day of week (Monday–Friday)
   - Slot number (1–13)
   - Shift assignment (1–5 first shift, 6–13 second shift)
   - Start and end time
   - Semester/term association

6. **Curriculum Requirements**
   - Required courses per program/year
   - Elective options
   - Prerequisites
   - Co-requisites

---

## 8. Output Requirements

### 8.1 Schedule Output Format

The generated schedule must provide:

1. **Master Schedule**: Complete timetable for all groups, instructors, and rooms
2. **Group Schedule (Расписание группы)**: Individual timetable per student group
3. **Instructor Schedule (Расписание преподавателя)**: Individual timetable per instructor
4. **Room Schedule (Расписание аудитории)**: Booking timetable per room
5. **Conflict Report**: Any unresolved soft constraint violations with penalty scores
6. **Statistics Report**: Utilization rates, constraint satisfaction metrics

### 8.2 Validation Requirements

Before finalizing, the schedule must pass:

1. All hard constraint checks (zero violations)
2. Soft constraint penalty below acceptable threshold
3. Manual review checkpoints for department heads
4. Cross-reference with academic calendar

---

## 9. Regulatory Compliance

### 9.1 Kazakhstan Ministry Requirements

The scheduling system must comply with:

- **GOSO RK**: State Compulsory Education Standards
- **Rules for Academic Process Organization** (Order of the Minister of Education)
- **Credit Technology Requirements** (ECTS-compatible system)
- **Accessibility Standards** for students with disabilities

### 9.2 Documentation Requirements

Generated schedules must be exportable in formats required for:

- Internal university information systems (typically 1C, Platonus, or similar)
- Ministry of Education reporting
- Student portal publication
- Official printable formats (Kazakh and Russian)

---

## 10. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-22 | Data Engineering Team | Initial specification |
| 1.1 | 2026-01-22 | Data Engineering Team | Adapted to configuration files structure |
| 1.2 | 2026-01-22 | Data Engineering Team | Updated with detailed constraints from CONSTRAINTS.md and SLOTS.md |

---

## 11. Appendices

### Appendix A: Time Slot Configuration

Each lesson lasts **50 minutes** with a **10-minute break** between consecutive slots.

| Slot # | Time | Shift |
|--------|------|-------|
| 1 | 9:00 → 9:50 | First |
| 2 | 10:00 → 10:50 | First |
| 3 | 11:00 → 11:50 | First |
| 4 | 12:00 → 12:50 | First |
| 5 | 13:00 → 13:50 | First |
| 6 | 14:00 → 14:50 | Second |
| 7 | 15:00 → 15:50 | Second |
| 8 | 16:00 → 16:50 | Second |
| 9 | 17:00 → 17:50 | Second |
| 10 | 18:00 → 18:50 | Second |
| 11 | 19:00 → 19:50 | Second |
| 12 | 20:00 → 20:50 | Second |
| 13 | 21:00 → 21:50 | Second |

**Total**: 13 slots per day

**Shifts**:
- **First Shift**: Slots 1–5 (9:00 – 14:00)
- **Second Shift**: Slots 6–13 (14:00 – 21:50)
- **Shift Boundary Flexibility**: First shift can extend to Slot 7 (16:00) if necessary

**Shift Assignment by Year**:

| Year | Shift | Notes |
|------|-------|-------|
| 1st year | First shift | Always, no exceptions |
| 2nd year | Second shift | Always, no exceptions |
| 3rd year | First shift | Per-day exceptions possible |
| 4th year | Automatic | Algorithm selects per group |
| 5th year | Automatic | Algorithm selects per group |

### Appendix B: Building Addresses

The system uses the following building addresses:

| Address | Notes | Exclusive To |
|---------|-------|--------------|
| `пр. Абулхаир хана, 44` | IT Group partner venue | — |
| `пр. Н.Назарбаева, 208` | Main building (nearby to Ихсанова) | — |
| `ул. 8 Марта, 125/1` | Sports facility | — |
| `ул. Айталиева, 8/1Б` | AVENCOM partner venue | — |
| `ул. Гагарина, 52/1` | БҚВҒЗС partner venue | — |
| `ул. Жангир хана, 51/4` | Veterinary building | **ВЕТ only** |
| `ул. Ихсанова, 44/1` | Main academic building | — |
| `ул. Победа, 137/1` | Legal studies building | **ЮР only** |
| `ул. Чапаева 69` | Construction/Architecture building | **СТР, АРХ, ЗК only** |

**Note**: Buildings marked as "exclusive" can only be used by the specified specialty groups, and only when the entire stream consists of that specialty. Subject-specific room requirements (`subject-rooms.json`) take priority over building exclusivity (see HC-22).

### Appendix C: Specialty Codes

Specialty prefixes extracted from group names:

| Code | Specialty (EN) | Specialty (RU) |
|------|----------------|----------------|
| ВЕТ | Veterinary | Ветеринария |
| СТР | Construction | Строительство |
| АРХ | Architecture | Архитектура |
| ЮР | Legal | Юриспруденция |
| ЗК | Land Cadastre | Земельный кадастр |
| НД | — | — |
| ЭЛ | Electrical | Электротехника |
| БЖД | Life Safety | Безопасность жизнедеятельности |
| АУ | — | — |

### Appendix D: Academic Title Prefixes

| Kazakh (kz) | Russian (ru) | Meaning |
|-------------|--------------|---------|
| о. | п. | Lecturer (оқытушы / преподаватель) |
| а.о. | с.п. | Senior Lecturer (аға оқытушы / старший преподаватель) |
| қ.проф. | асс.проф. | Associate Professor |
| проф. | проф. | Professor |
| д. | д. | Doctor |
| prof. | prof. | Professor (English) |

### Appendix E: Glossary of Academic Terms

| English | Russian | Kazakh |
|---------|---------|--------|
| Schedule | Расписание | Сабақ кестесі |
| Lecture | Лекция | Дәріс |
| Seminar | Семинар | Семинар |
| Practice | Практика | Практика |
| Laboratory | Лабораторная работа | Зертханалық жұмыс |
| Instructor | Преподаватель | Оқытушы |
| Student | Студент | Студент |
| Group | Группа | Топ |
| Course | Дисциплина | Пән |
| Credit | Кредит | Кредит |
| Classroom | Аудитория | Аудитория |
| First Shift | Первая смена | Бірінші ауысым |
| Second Shift | Вторая смена | Екінші ауысым |
| Dead Group | Нулевая группа | Нөлдік топ |
