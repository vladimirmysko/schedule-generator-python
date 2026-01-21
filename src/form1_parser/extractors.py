"""Stream extraction using Strategy pattern.

Each data entry pattern (1a, 1b, implicit_subgroup, explicit_subgroup)
gets its own extractor class.
"""

from abc import ABC, abstractmethod

import pandas as pd

from .constants import (
    PATTERN_1A,
    PATTERN_1B,
    PATTERN_EXPLICIT_SUBGROUP,
    PATTERN_IMPLICIT_SUBGROUP,
)
from .models import Stream, StreamType, WeeklyHours
from .utils import (
    clean_instructor_name,
    generate_stream_id,
    has_explicit_subgroup,
    normalize_group_name,
    safe_int,
    safe_str,
)


class BaseExtractor(ABC):
    """Base class for stream extractors."""

    def __init__(self, subject: str, sheet: str):
        """Initialize extractor.

        Args:
            subject: Subject name
            sheet: Sheet name
        """
        self.subject = subject
        self.sheet = sheet
        self.stream_counter = 0

    @abstractmethod
    def extract(self, data: pd.DataFrame) -> list[Stream]:
        """Extract streams from subject data.

        Args:
            data: DataFrame containing rows for a single subject

        Returns:
            List of extracted streams
        """
        pass

    def _create_stream(
        self,
        stream_type: StreamType,
        instructor: str,
        language: str,
        hours: int,
        groups: list[str],
        student_count: int,
        rows: list[int],
        is_subgroup: bool = False,
        is_implicit_subgroup: bool = False,
    ) -> Stream:
        """Create a Stream object.

        Args:
            stream_type: Type of stream
            instructor: Instructor name
            language: Language code
            hours: Total semester hours
            groups: List of group names
            student_count: Number of students
            rows: Source row numbers
            is_subgroup: Whether this is an explicit subgroup
            is_implicit_subgroup: Whether this is an implicit subgroup

        Returns:
            Stream object
        """
        self.stream_counter += 1
        stream_id = generate_stream_id(
            self.subject, stream_type.value, instructor, self.stream_counter
        )

        return Stream(
            id=stream_id,
            subject=self.subject,
            stream_type=stream_type,
            instructor=clean_instructor_name(instructor),
            language=safe_str(language),
            hours=WeeklyHours.from_total(hours),
            groups=groups,
            student_count=student_count,
            sheet=self.sheet,
            rows=rows,
            is_subgroup=is_subgroup,
            is_implicit_subgroup=is_implicit_subgroup,
        )

    def _extract_lecture_streams(self, data: pd.DataFrame) -> list[Stream]:
        """Extract lecture streams using sequential merge logic.

        Row with lecture hours > 0 starts a new stream.
        Rows with NO hours at all (no lecture, no practical, no lab) merge into
        the current lecture stream. Rows with practical/lab hours are NOT merged.

        Args:
            data: Subject data

        Returns:
            List of lecture streams
        """
        streams = []

        current_groups: list[str] = []
        current_instructor: str | None = None
        current_language: str | None = None
        current_hours: int = 0
        current_students: int = 0
        current_rows: list[int] = []

        for idx, row in data.iterrows():
            lec_hours = safe_int(row["lecture"])
            prac_hours = safe_int(row["practical"])
            lab_hours = safe_int(row["lab"])
            group = safe_str(row["group"])
            instructor = safe_str(row["instructor"])

            if lec_hours > 0:
                # Save previous stream if exists
                if current_groups and current_instructor:
                    streams.append(
                        self._create_stream(
                            stream_type=StreamType.LECTURE,
                            instructor=current_instructor,
                            language=current_language or "",
                            hours=current_hours,
                            groups=current_groups,
                            student_count=current_students,
                            rows=current_rows,
                        )
                    )

                # Start new lecture stream
                current_groups = [normalize_group_name(group)] if group else []
                current_instructor = instructor
                current_language = safe_str(row["language"])
                current_hours = lec_hours
                current_students = safe_int(row.get("students", 0))
                current_rows = [idx]
            else:
                # No lecture hours on this row
                if current_groups and group:
                    normalized = normalize_group_name(group)
                    is_new_group = normalized not in current_groups

                    if is_new_group:
                        # NEW group: add to lecture stream (even if has prac/lab hours)
                        # All groups in the lecture block should be included
                        current_groups.append(normalized)
                        current_students += safe_int(row.get("students", 0))
                        current_rows.append(idx)
                    # DUPLICATE group with prac/lab hours: skip (it's a practical/lab row)
                    # DUPLICATE group without hours: also skip (just a continuation row)

        # Don't forget last stream
        if current_groups and current_instructor:
            streams.append(
                self._create_stream(
                    stream_type=StreamType.LECTURE,
                    instructor=current_instructor,
                    language=current_language or "",
                    hours=current_hours,
                    groups=current_groups,
                    student_count=current_students,
                    rows=current_rows,
                )
            )

        return streams


class Pattern1aExtractor(BaseExtractor):
    """Extractor for Pattern 1a: Horizontal - Individual.

    Each row has its own Practical/Lab hours.
    Row with hours starts new stream; rows without hours merge into current
    stream (rare case where groups merge with same instructor).
    """

    def extract(self, data: pd.DataFrame) -> list[Stream]:
        """Extract streams from Pattern 1a data."""
        streams = []

        # Extract lecture streams (common logic)
        streams.extend(self._extract_lecture_streams(data))

        # Practical streams: use merging logic for rare cases
        streams.extend(self._extract_merged_streams(data, "practical", StreamType.PRACTICAL))

        # Lab streams: use merging logic for rare cases
        streams.extend(self._extract_merged_streams(data, "lab", StreamType.LAB))

        return streams

    def _extract_merged_streams(
        self, data: pd.DataFrame, hours_col: str, stream_type: StreamType
    ) -> list[Stream]:
        """Extract streams with merged groups.

        Row with hours > 0 starts new stream.
        Rows without hours merge into current stream (same instructor).

        Args:
            data: Subject data
            hours_col: Column name for hours (practical or lab)
            stream_type: Type of stream

        Returns:
            List of streams
        """
        streams = []

        current_groups: list[str] = []
        current_instructor: str | None = None
        current_language: str | None = None
        current_hours: int = 0
        current_students: int = 0
        current_rows: list[int] = []

        for idx, row in data.iterrows():
            hours = safe_int(row[hours_col])
            group = safe_str(row["group"])
            instructor = safe_str(row["instructor"])

            if hours > 0:
                # Save previous stream if exists
                if current_groups and current_instructor:
                    streams.append(
                        self._create_stream(
                            stream_type=stream_type,
                            instructor=current_instructor,
                            language=current_language or "",
                            hours=current_hours,
                            groups=current_groups,
                            student_count=current_students,
                            rows=current_rows,
                        )
                    )

                # Start new stream
                current_groups = [normalize_group_name(group)] if group else []
                current_instructor = instructor
                current_language = safe_str(row["language"])
                current_hours = hours
                current_students = safe_int(row.get("students", 0))
                current_rows = [idx]
            else:
                # Merge into current stream if same instructor
                if current_groups and group and instructor == current_instructor:
                    normalized = normalize_group_name(group)
                    if normalized not in current_groups:
                        current_groups.append(normalized)
                    current_students += safe_int(row.get("students", 0))
                    current_rows.append(idx)

        # Don't forget last stream
        if current_groups and current_instructor:
            streams.append(
                self._create_stream(
                    stream_type=stream_type,
                    instructor=current_instructor,
                    language=current_language or "",
                    hours=current_hours,
                    groups=current_groups,
                    student_count=current_students,
                    rows=current_rows,
                )
            )

        return streams


class Pattern1bExtractor(BaseExtractor):
    """Extractor for Pattern 1b: Horizontal - Merged.

    NaN in Prac/Lab means "merged with previous group's stream".
    Row with hours starts new stream; following NaN rows merge into it.
    """

    def extract(self, data: pd.DataFrame) -> list[Stream]:
        """Extract streams from Pattern 1b data."""
        streams = []

        # Extract lecture streams (common logic)
        streams.extend(self._extract_lecture_streams(data))

        # Practical streams: sequential merge
        streams.extend(self._extract_merged_streams(data, "practical", StreamType.PRACTICAL))

        # Lab streams: same logic
        streams.extend(self._extract_merged_streams(data, "lab", StreamType.LAB))

        return streams

    def _extract_merged_streams(
        self, data: pd.DataFrame, hours_col: str, stream_type: StreamType
    ) -> list[Stream]:
        """Extract streams with merged groups.

        Args:
            data: Subject data
            hours_col: Column name for hours (practical or lab)
            stream_type: Type of stream

        Returns:
            List of streams
        """
        streams = []

        current_groups: list[str] = []
        current_instructor: str | None = None
        current_language: str | None = None
        current_hours: int = 0
        current_students: int = 0
        current_rows: list[int] = []

        for idx, row in data.iterrows():
            hours = safe_int(row[hours_col])
            group = safe_str(row["group"])
            instructor = safe_str(row["instructor"])

            if hours > 0:
                # Save previous stream if exists
                if current_groups and current_instructor:
                    streams.append(
                        self._create_stream(
                            stream_type=stream_type,
                            instructor=current_instructor,
                            language=current_language or "",
                            hours=current_hours,
                            groups=current_groups,
                            student_count=current_students,
                            rows=current_rows,
                        )
                    )

                # Start new stream
                current_groups = [normalize_group_name(group)] if group else []
                current_instructor = instructor
                current_language = safe_str(row["language"])
                current_hours = hours
                current_students = safe_int(row.get("students", 0))
                current_rows = [idx]
            else:
                # Merge into current stream
                if current_groups and group:
                    normalized = normalize_group_name(group)
                    if normalized not in current_groups:
                        current_groups.append(normalized)
                    current_students += safe_int(row.get("students", 0))
                    current_rows.append(idx)

        # Don't forget last stream
        if current_groups and current_instructor:
            streams.append(
                self._create_stream(
                    stream_type=stream_type,
                    instructor=current_instructor,
                    language=current_language or "",
                    hours=current_hours,
                    groups=current_groups,
                    student_count=current_students,
                    rows=current_rows,
                )
            )

        return streams


class ImplicitSubgroupExtractor(BaseExtractor):
    """Extractor for implicit subgroups.

    Same group name appears multiple times without explicit subgroup notation.
    - Practical: Use merging logic (row with hours starts stream, NaN rows merge)
    - Lab: EVERY row with Lab > 0 (each is separate stream)
    """

    def extract(self, data: pd.DataFrame) -> list[Stream]:
        """Extract streams from implicit subgroup data."""
        streams = []

        # Extract lecture streams (common logic)
        streams.extend(self._extract_lecture_streams(data))

        # Practical streams: use merging logic (like Pattern 1b)
        streams.extend(self._extract_merged_practical_streams(data))

        # Lab streams: EVERY row with Lab > 0 (each is separate subgroup stream)
        for idx, row in data.iterrows():
            hours = safe_int(row["lab"])
            if hours > 0:
                group = safe_str(row["group"])
                instructor = safe_str(row["instructor"])
                language = safe_str(row["language"])
                students = safe_int(row.get("students", 0))

                if group and instructor:
                    streams.append(
                        self._create_stream(
                            stream_type=StreamType.LAB,
                            instructor=instructor,
                            language=language,
                            hours=hours,
                            groups=[normalize_group_name(group)],
                            student_count=students,
                            rows=[idx],
                            is_implicit_subgroup=True,
                        )
                    )

        return streams

    def _extract_merged_practical_streams(self, data: pd.DataFrame) -> list[Stream]:
        """Extract practical streams with merged groups.

        Row with practical hours > 0 starts new stream.
        Rows with no practical hours merge into current stream.
        Row with lecture hours > 0 ends current stream (new lecture block).
        """
        streams = []

        current_groups: list[str] = []
        current_instructor: str | None = None
        current_language: str | None = None
        current_hours: int = 0
        current_students: int = 0
        current_rows: list[int] = []

        for idx, row in data.iterrows():
            lec_hours = safe_int(row["lecture"])
            prac_hours = safe_int(row["practical"])
            group = safe_str(row["group"])
            instructor = safe_str(row["instructor"])

            # First: check if new lecture block starts
            if lec_hours > 0:
                # New lecture block starts - save current practical stream and reset
                if current_groups and current_instructor:
                    streams.append(
                        self._create_stream(
                            stream_type=StreamType.PRACTICAL,
                            instructor=current_instructor,
                            language=current_language or "",
                            hours=current_hours,
                            groups=current_groups,
                            student_count=current_students,
                            rows=current_rows,
                        )
                    )
                # Reset state
                current_groups = []
                current_instructor = None
                current_language = None
                current_hours = 0
                current_students = 0
                current_rows = []

            # Then: check if this row has practical hours
            if prac_hours > 0:
                # Save previous stream if exists
                if current_groups and current_instructor:
                    streams.append(
                        self._create_stream(
                            stream_type=StreamType.PRACTICAL,
                            instructor=current_instructor,
                            language=current_language or "",
                            hours=current_hours,
                            groups=current_groups,
                            student_count=current_students,
                            rows=current_rows,
                        )
                    )

                # Start new stream
                current_groups = [normalize_group_name(group)] if group else []
                current_instructor = instructor
                current_language = safe_str(row["language"])
                current_hours = prac_hours
                current_students = safe_int(row.get("students", 0))
                current_rows = [idx]
            else:
                # Merge into current stream (if group is new)
                if current_groups and group:
                    normalized = normalize_group_name(group)
                    if normalized not in current_groups:
                        current_groups.append(normalized)
                        current_students += safe_int(row.get("students", 0))
                        current_rows.append(idx)

        # Don't forget last stream
        if current_groups and current_instructor:
            streams.append(
                self._create_stream(
                    stream_type=StreamType.PRACTICAL,
                    instructor=current_instructor,
                    language=current_language or "",
                    hours=current_hours,
                    groups=current_groups,
                    student_count=current_students,
                    rows=current_rows,
                )
            )

        return streams


class ExplicitSubgroupExtractor(BaseExtractor):
    """Extractor for explicit subgroups.

    Groups have explicit subgroup notation (/1/, \\1\\, -1).
    Row with hours starts new stream; rows without hours merge into current
    stream (rare case where groups/subgroups merge with same instructor).
    """

    def extract(self, data: pd.DataFrame) -> list[Stream]:
        """Extract streams from explicit subgroup data."""
        streams = []

        # Extract lecture streams (common logic)
        streams.extend(self._extract_lecture_streams(data))

        # Practical streams: use merging logic
        streams.extend(self._extract_merged_streams(data, "practical", StreamType.PRACTICAL))

        # Lab streams: use merging logic
        streams.extend(self._extract_merged_streams(data, "lab", StreamType.LAB))

        return streams

    def _extract_merged_streams(
        self, data: pd.DataFrame, hours_col: str, stream_type: StreamType
    ) -> list[Stream]:
        """Extract streams with merged groups.

        Row with hours > 0 starts new stream.
        Rows without hours merge into current stream (same instructor).

        Args:
            data: Subject data
            hours_col: Column name for hours (practical or lab)
            stream_type: Type of stream

        Returns:
            List of streams
        """
        streams = []

        current_groups: list[str] = []
        current_instructor: str | None = None
        current_language: str | None = None
        current_hours: int = 0
        current_students: int = 0
        current_rows: list[int] = []
        current_has_subgroup: bool = False

        for idx, row in data.iterrows():
            hours = safe_int(row[hours_col])
            group = safe_str(row["group"])
            instructor = safe_str(row["instructor"])

            if hours > 0:
                # Save previous stream if exists
                if current_groups and current_instructor:
                    streams.append(
                        self._create_stream(
                            stream_type=stream_type,
                            instructor=current_instructor,
                            language=current_language or "",
                            hours=current_hours,
                            groups=current_groups,
                            student_count=current_students,
                            rows=current_rows,
                            is_subgroup=current_has_subgroup,
                        )
                    )

                # Start new stream
                current_groups = [group] if group else []
                current_instructor = instructor
                current_language = safe_str(row["language"])
                current_hours = hours
                current_students = safe_int(row.get("students", 0))
                current_rows = [idx]
                current_has_subgroup = has_explicit_subgroup(group) if group else False
            else:
                # Merge into current stream if same instructor
                if current_groups and group and instructor == current_instructor:
                    if group not in current_groups:
                        current_groups.append(group)
                        if has_explicit_subgroup(group):
                            current_has_subgroup = True
                    current_students += safe_int(row.get("students", 0))
                    current_rows.append(idx)

        # Don't forget last stream
        if current_groups and current_instructor:
            streams.append(
                self._create_stream(
                    stream_type=stream_type,
                    instructor=current_instructor,
                    language=current_language or "",
                    hours=current_hours,
                    groups=current_groups,
                    student_count=current_students,
                    rows=current_rows,
                    is_subgroup=current_has_subgroup,
                )
            )

        return streams


def get_extractor(pattern: str, subject: str, sheet: str) -> BaseExtractor:
    """Get the appropriate extractor for a pattern.

    Args:
        pattern: Pattern name
        subject: Subject name
        sheet: Sheet name

    Returns:
        Extractor instance
    """
    extractors = {
        PATTERN_1A: Pattern1aExtractor,
        PATTERN_1B: Pattern1bExtractor,
        PATTERN_IMPLICIT_SUBGROUP: ImplicitSubgroupExtractor,
        PATTERN_EXPLICIT_SUBGROUP: ExplicitSubgroupExtractor,
    }

    extractor_class = extractors.get(pattern, Pattern1aExtractor)
    return extractor_class(subject, sheet)
