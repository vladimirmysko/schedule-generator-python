# Data Directory

This directory contains configuration files used by the schedule parser system. These files define rooms, instructor constraints, subject requirements, and group preferences for schedule generation.

## Files Overview

| File                           | Format | Purpose                                     |
| ------------------------------ | ------ | ------------------------------------------- |
| `rooms.csv`                    | CSV    | Master list of all available rooms          |
| `instructor-prefixes.csv`      | CSV    | Academic title prefixes mapping (KZ → RU)   |
| `dead-groups.csv`              | CSV    | Groups that don't attend classes            |
| `subject-names-map.csv`        | CSV    | Bilingual subject name mappings (KZ → RU)   |
| `instructor-availability.json` | JSON   | Instructors unavailability time slots       |
| `instructor-rooms.json`        | JSON   | Instructors room preferences                |
| `instructor-days.json`         | JSON   | Day-based teaching constraints              |
| `subject-rooms.json`           | JSON   | Subject-specific room requirements          |
| `group-buildings.json`         | JSON   | Building preferences by specialty group     |
| `nearby-buildings.json`        | JSON   | Groups of buildings located near each other |

---

## rooms.csv

Master list of all available rooms with their capacities and building addresses.

### Format

```csv
name,capacity,address,is_special
```

### Fields

| Field        | Type    | Description                                            |
| ------------ | ------- | ------------------------------------------------------ |
| `name`       | string  | Room identifier (e.g., "А-пот", "201", "IT Group")     |
| `capacity`   | integer | Maximum number of students the room can hold           |
| `address`    | string  | Building address where the room is located             |
| `is_special` | boolean | If `true`, room is reserved for specific subjects only |

### Special Rooms

Rooms marked with `is_special=true` are external/partner venues that can only be used for their designated subjects:

| Room      | Purpose                             |
| --------- | ----------------------------------- |
| IT Group  | IT partner classes                  |
| Спорт зал | Physical education (Дене шынықтыру) |
| AVENCOM   | Partner organization classes        |
| БҚВҒЗС    | Partner organization classes        |

### Example

```csv
name,capacity,address,is_special
IT Group,100,"пр. Абулхаир хана, 44",true
А-пот,150,"пр. Н.Назарбаева, 208",
201,36,"ул. Жангир хана, 51/4",
112,12,"ул. Ихсанова, 44/1",
```

### Building Addresses

The system uses the following building addresses:

- `пр. Абулхаир хана, 44`
- `пр. Н.Назарбаева, 208`
- `ул. 8 Марта, 125/1`
- `ул. Айталиева, 8/1Б`
- `ул. Гагарина, 52/1`
- `ул. Жангир хана, 51/4`
- `ул. Ихсанова, 44/1`
- `ул. Победа, 137/1`
- `ул. Чапаева 69`

---

## instructor-prefixes.csv

Mapping of academic title prefixes from Kazakh to Russian. Used for parsing and normalizing instructor names from schedule files.

### Format

```csv
kz,ru
```

### Fields

| Field | Type   | Description               |
| ----- | ------ | ------------------------- |
| `kz`  | string | Kazakh prefix             |
| `ru`  | string | Corresponding Russian prefix |

### Values

| Kazakh (kz) | Russian (ru) | Meaning                                               |
| ----------- | ------------ | ----------------------------------------------------- |
| `о.`        | `п.`         | Lecturer (оқытушы / преподаватель)                    |
| `а.о.`      | `с.п.`       | Senior Lecturer (аға оқытушы / старший преподаватель) |
| `қ.проф.`   | `асс.проф.`  | Associate Professor                                   |
| `проф.`     | `проф.`      | Professor                                             |
| `д.`        | `д.`         | Doctor (доктор)                                       |
| `prof.`     | `prof.`      | Professor (English)                                   |

### Example

```csv
kz,ru
о.,п.
а.о.,с.п.
қ.проф.,асс.проф.
проф.,проф.
д.,д.
prof.,prof.
```

---

## dead-groups.csv

List of group names that don't attend classes (also known as "dead groups"). These groups are included in documents but their student counts are set to 0 when generating schedules, so they don't affect room capacity calculations.

### Format

```csv
name
```

### Fields

| Field  | Type   | Description                                  |
| ------ | ------ | -------------------------------------------- |
| `name` | string | Full group name (e.g., "НД-23 О", "НД-25 О") |

### Behavior

- Dead groups are **included** in the schedule output (unlike remote groups which are skipped)
- Student count is set to **0** for dead groups during schedule generation
- This means dead groups:
  - Still appear in output documents
  - Don't contribute to room capacity requirements
  - Don't affect stream grouping calculations
  - Are sorted last in priority (lowest student count)

### Example

```csv
name
НД-23 О
НД-25 О
НД-27 О
НД-29 О
НД-33 О
...
ЭЛ-33 О
ЭЛ-43 О
БЖД-33 О
...
```

Note: The file contains 20+ entries covering various specialties (НД, ЭЛ, БЖД, АУ, ЮР).

---

## subject-names-map.csv

Bilingual mapping of subject names from Kazakh to Russian. Used for matching and normalizing subject names across different document sources.

### Format

```csv
Kazakh Name;Russian Name
```

Note: This file uses semicolon (`;`) as a delimiter, not comma.

### Fields

| Field        | Type   | Description                |
| ------------ | ------ | -------------------------- |
| Kazakh Name  | string | Subject name in Kazakh     |
| Russian Name | string | Subject name in Russian    |

### Example

```csv
Электрмен жабдықтау жүйелерінің сенімділігі;Нaдежнoсть систем электрoснaбжения
Электрлік сұлбалар және ақпараттық өлшеуіш аспаптар;Электрические схемы и информационно – измерительные приборы
ЭТН 1;ТОЭ 1
Электр қамту жүйесіндегі өтпелі процестер;Перехoдные прoцессы в СЭС
Химия;Химия
Физика;Физика
```

### Usage

The file contains 300+ subject name mappings covering all academic disciplines. It's used to:

- Match subjects when they appear in different languages across documents
- Normalize subject names for consistent reporting
- Link schedule entries with course catalogs

---

## instructor-availability.json

Defines time slots when instructors are **NOT** available to teach. The scheduler will avoid assigning classes to instructors during their unavailable times.

### Format

Array of instructor availability objects.

### Structure

```json
[
  {
    "name": "Instructor Name",
    "weekly_unavailable": {
      "day_name": ["HH:MM", "HH:MM", ...]
    }
  }
]
```

### Fields

| Field                | Type   | Description                                 |
| -------------------- | ------ | ------------------------------------------- |
| `name`               | string | Instructor name (without academic prefix)   |
| `weekly_unavailable` | object | Map of days to unavailable time slots       |

### Day Names

Days use English lowercase names:

- `monday`
- `tuesday`
- `wednesday`
- `thursday`
- `friday`

### Time Format

Times are in 24-hour format: `"HH:MM"` (e.g., `"09:00"`, `"14:00"`)

### Example

```json
[
  {
    "name": "Чурикова Л.А.",
    "weekly_unavailable": {
      "friday": [
        "09:00",
        "10:00",
        "11:00",
        "12:00",
        "13:00",
        "14:00",
        "15:00",
        "16:00",
        "17:00",
        "18:00",
        "19:00",
        "20:00"
      ]
    }
  },
  {
    "name": "Рахметов Т.Х.",
    "weekly_unavailable": {
      "monday": ["13:00", "14:00"],
      "tuesday": ["13:00", "14:00"],
      "wednesday": [
        "09:00",
        "10:00",
        "11:00",
        "12:00",
        "13:00",
        "14:00",
        "15:00",
        "16:00",
        "17:00",
        "18:00",
        "19:00",
        "20:00"
      ],
      "thursday": ["13:00", "14:00"],
      "friday": ["13:00", "14:00"]
    }
  }
]
```

---

## instructor-rooms.json

Defines preferred or required rooms for specific instructors. Supports both general location preferences and class-type-specific room assignments.

### Format

Object keyed by instructor name.

### Structure

```json
{
  "Instructor Name": {
    "locations": [{ "address": "building address", "room": "room number" }]
  }
}
```

Or with class-type-specific assignments:

```json
{
  "Instructor Name": {
    "lecture": [{ "address": "...", "room": "..." }],
    "practice": [{ "address": "...", "room": "..." }],
    "lab": [{ "address": "...", "room": "..." }]
  }
}
```

### Fields

| Field       | Type  | Description                                 |
| ----------- | ----- | ------------------------------------------- |
| `locations` | array | General room preferences for any class type |
| `lecture`   | array | Rooms allowed only for lectures             |
| `practice`  | array | Rooms allowed only for practice sessions    |
| `lab`       | array | Rooms allowed only for lab sessions         |

**Note**: `locations` and class-type arrays (`lecture`, `practice`, `lab`) are mutually exclusive. Use either `locations` OR the class-type arrays, not both.

### Location Object

| Field     | Type   | Description                               |
| --------- | ------ | ----------------------------------------- |
| `address` | string | Building address (must match `rooms.csv`) |
| `room`    | string | Room number/name (must match `rooms.csv`) |

### Example

```json
{
  "Чурикова Л.А.": {},
  "Байтлесов Е.У.": {
    "locations": [{ "address": "ул. Жангир хана, 51/4", "room": "206" }]
  },
  "Бурахта В.А.": {
    "lecture": [{ "address": "ул. Ихсанова, 44/1", "room": "Г-пот" }],
    "practice": [{ "address": "ул. Ихсанова, 44/1", "room": "112" }]
  }
}
```

---

## instructor-days.json

Defines day-based teaching constraints for instructors. Some instructors can only teach certain years on specific days, or must have all their classes on a single day.

### Format

Array of instructor constraint objects.

### Structure

```json
[
  {
    "name": "Instructor Name",
    "year_days": {
      "year_number": ["day", "day", ...]
    }
  }
]
```

Or for single-day constraints:

```json
[
  {
    "name": "Instructor Name",
    "one_day_per_week": true
  }
]
```

### Fields

| Field              | Type    | Description                                          |
| ------------------ | ------- | ---------------------------------------------------- |
| `name`             | string  | Instructor name                                      |
| `year_days`        | object  | Map of year numbers (as strings) to allowed weekdays |
| `one_day_per_week` | boolean | If true, all classes must be on the same day         |

### Day Names

Same as `instructor-availability.json`: `monday`, `tuesday`, `wednesday`, `thursday`, `friday`

### Example

```json
[
  {
    "name": "Серикбекова С.Б.",
    "year_days": {
      "1": ["tuesday"],
      "2": ["monday"]
    }
  }
]
```

In this example, Серикбекова can only teach 1st-year students on Tuesday and 2nd-year students on Monday.

Note: The `one_day_per_week` field is supported but currently not used in the data. When set to `true`, all of the instructor's classes must be scheduled on the same day.

---

## subject-rooms.json

Defines room restrictions for specific subjects. Used for subjects that require specialized rooms (e.g., computer labs, chemistry labs).

### Format

Object keyed by subject name.

### Structure

```json
{
  "Subject Name": {
    "locations": [{ "address": "building address", "room": "room number" }]
  }
}
```

Or with class-type-specific restrictions:

```json
{
  "Subject Name": {
    "practice": [{ "address": "building address", "room": "room number" }]
  }
}
```

### Fields

| Field       | Type  | Description                                      |
| ----------- | ----- | ------------------------------------------------ |
| `locations` | array | Rooms allowed for any class type of this subject |
| `practice`  | array | Rooms allowed only for practice/lab sessions     |

**Note**: If only `practice` is specified, lectures have no room restrictions.

### Example

```json
{
  "Алгоритмдеу және бағдарламалау": {
    "locations": [
      { "address": "ул. Ихсанова, 44/1", "room": "401" },
      { "address": "ул. Ихсанова, 44/1", "room": "403" },
      { "address": "ул. Ихсанова, 44/1", "room": "404" },
      { "address": "ул. Ихсанова, 44/1", "room": "407" }
    ]
  },
  "Химия": {
    "locations": [{ "address": "ул. Ихсанова, 44/1", "room": "112" }]
  },
  "Ақпараттық-коммуникациялық технологиялар": {
    "practice": [
      { "address": "ул. Ихсанова, 44/1", "room": "401" },
      { "address": "ул. Ихсанова, 44/1", "room": "403" }
    ]
  }
}
```

---

## group-buildings.json

Defines building preferences for specialty groups. These are **soft preferences** that the scheduler tries to honor, but subject-specific room requirements take priority.

### Format

Object keyed by specialty prefix.

### Structure

```json
{
  "SPECIALTY": {
    "addresses": [
      { "address": "building address" }
    ]
  }
}
```

Or with specific room restrictions:

```json
{
  "SPECIALTY": {
    "addresses": [
      { "address": "building address", "rooms": ["room1", "room2"] }
    ]
  }
}
```

### Fields

| Field       | Type  | Description                                               |
| ----------- | ----- | --------------------------------------------------------- |
| `years`     | array | Year numbers this preference applies to                   |
| `addresses` | array | Preferred building addresses                              |
| `rooms`     | array | (Optional) Specific room restrictions within the building |

### Specialty Prefixes

Extracted from group names like "ВЕТ-31 О", "СТР-21 ОК":

- `ВЕТ` - Veterinary
- `СТР` - Construction
- `АРХ` - Architecture
- `ЮР` - Legal
- `ТБПП` - Food Technology

### Example

```json
{
  "ВЕТ": {
    "addresses": [{ "address": "ул. Жангир хана, 51/4" }]
  },
  "СТР": {
    "addresses": [{ "address": "ул. Чапаева 69" }]
  },
  "АРХ": {
    "addresses": [{ "address": "ул. Чапаева 69" }]
  },
  "ЮР": {
    "addresses": [{ "address": "ул. Победа, 137/1" }]
  }
}
```

### Priority Rules

1. Subject-specific rooms (`subject-rooms.json`) take highest priority
2. Instructor room preferences (`instructor-rooms.json`) come next
3. Group building preferences (`group-buildings.json`) are considered last

---

## nearby-buildings.json

Defines groups of building addresses that are located near each other. When classes are scheduled in buildings from the same nearby group, the scheduler does not require a gap between consecutive classes, allowing back-to-back scheduling.

### Format

Object with a `groups` array.

### Structure

```json
{
  "groups": [
    {
      "addresses": ["building address 1", "building address 2"]
    }
  ]
}
```

### Fields

| Field       | Type  | Description                                                         |
| ----------- | ----- | ------------------------------------------------------------------- |
| `groups`    | array | Array of nearby building groups                                     |
| `addresses` | array | List of building addresses that are considered nearby to each other |

### Semantics

- All addresses within a group are considered "nearby" to each other
- If two consecutive classes are in buildings from the same group, no gap is required
- If buildings are in different groups (or not in any group), the standard 1-slot gap is required
- Addresses must match exactly as they appear in `rooms.csv` (case-sensitive)

### Example

```json
{
  "groups": [
    {
      "addresses": ["ул. Ихсанова, 44/1", "пр. Н.Назарбаева, 208"]
    }
  ]
}
```

In this example, classes scheduled in rooms at "ул. Ихсанова, 44/1" and "пр. Н.Назарбаева, 208" can be scheduled back-to-back without requiring a gap slot for travel time.

---

## Constraint Priority Summary

When the scheduler assigns rooms, constraints are applied in this order:

1. **Subject rooms** - Required rooms for specific subjects (e.g., chemistry lab)
2. **Instructor rooms** - Preferred rooms for specific instructors
3. **Group buildings** - Soft building preferences by specialty/year
4. **General room pool** - Any available room from `rooms.csv`

Time constraints are handled separately:

1. **Instructor availability** - Hard constraint, never schedule during unavailable times
2. **Instructor days** - Restrict which days instructors can teach certain years
3. **Instructor substitutions** - Use substitute's availability when applicable
