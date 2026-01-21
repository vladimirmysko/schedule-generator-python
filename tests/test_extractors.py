"""Tests for stream extractors."""

import pandas as pd
import pytest

from form1_parser.constants import (
    PATTERN_1A,
    PATTERN_1B,
    PATTERN_EXPLICIT_SUBGROUP,
    PATTERN_IMPLICIT_SUBGROUP,
)
from form1_parser.extractors import (
    ExplicitSubgroupExtractor,
    ImplicitSubgroupExtractor,
    Pattern1aExtractor,
    Pattern1bExtractor,
    get_extractor,
)
from form1_parser.models import StreamType


class TestPattern1aExtractor:
    """Tests for Pattern1aExtractor."""

    def test_extract_lecture_streams(self, sample_pattern_1a_data):
        """Test extracting lecture streams."""
        extractor = Pattern1aExtractor("Math", "оод (2)")
        streams = extractor.extract(sample_pattern_1a_data)

        lecture_streams = [s for s in streams if s.stream_type == StreamType.LECTURE]

        # With sequential merge logic, each row with lecture hours starts a new stream
        # Row 0: Иванов, Row 1: Иванов, Row 2: Петров = 3 streams
        # But rows without hours would merge, so we have 3 rows each with hours
        assert len(lecture_streams) == 3

        # Check instructors
        instructors = [s.instructor for s in lecture_streams]
        assert instructors.count("Иванов А.О.") == 2
        assert instructors.count("Петров С.П.") == 1

    def test_extract_practical_streams(self, sample_pattern_1a_data):
        """Test extracting practical streams."""
        extractor = Pattern1aExtractor("Math", "оод (2)")
        streams = extractor.extract(sample_pattern_1a_data)

        practical_streams = [s for s in streams if s.stream_type == StreamType.PRACTICAL]

        # Each row with Prac > 0 = 1 stream, so 3 streams
        assert len(practical_streams) == 3

    def test_extract_lab_streams(self, sample_pattern_1a_data):
        """Test extracting lab streams."""
        extractor = Pattern1aExtractor("Math", "оод (2)")
        streams = extractor.extract(sample_pattern_1a_data)

        lab_streams = [s for s in streams if s.stream_type == StreamType.LAB]

        # Each row with Lab > 0 = 1 stream, so 3 streams
        assert len(lab_streams) == 3

    def test_stream_groups(self, sample_pattern_1a_data):
        """Test that each practical/lab stream has exactly one group."""
        extractor = Pattern1aExtractor("Math", "оод (2)")
        streams = extractor.extract(sample_pattern_1a_data)

        for stream in streams:
            if stream.stream_type in (StreamType.PRACTICAL, StreamType.LAB):
                assert len(stream.groups) == 1


class TestPattern1bExtractor:
    """Tests for Pattern1bExtractor."""

    def test_extract_merged_practical_streams(self, sample_pattern_1b_data):
        """Test extracting merged practical streams."""
        extractor = Pattern1bExtractor("Chemistry", "оод (2)")
        streams = extractor.extract(sample_pattern_1b_data)

        practical_streams = [s for s in streams if s.stream_type == StreamType.PRACTICAL]

        # Should have 2 practical streams (rows 0-1 merge, rows 2-3 merge)
        assert len(practical_streams) == 2

        # First stream should have groups БЖД-11 О and ВЕТ-11 О
        first_stream = practical_streams[0]
        assert "БЖД-11 О" in first_stream.groups
        assert "ВЕТ-11 О" in first_stream.groups

    def test_extract_merged_lab_streams(self, sample_pattern_1b_data):
        """Test extracting merged lab streams."""
        extractor = Pattern1bExtractor("Chemistry", "оод (2)")
        streams = extractor.extract(sample_pattern_1b_data)

        lab_streams = [s for s in streams if s.stream_type == StreamType.LAB]

        # Should have 2 lab streams
        assert len(lab_streams) == 2


class TestImplicitSubgroupExtractor:
    """Tests for ImplicitSubgroupExtractor."""

    def test_practical_first_occurrence_only(self, sample_implicit_subgroup_data):
        """Test that practical uses only first occurrence per group."""
        extractor = ImplicitSubgroupExtractor("Physics", "стр")
        streams = extractor.extract(sample_implicit_subgroup_data)

        practical_streams = [s for s in streams if s.stream_type == StreamType.PRACTICAL]

        # Only 1 practical stream (first occurrence)
        assert len(practical_streams) == 1

    def test_lab_every_row(self, sample_implicit_subgroup_data):
        """Test that every row with Lab > 0 creates a stream."""
        extractor = ImplicitSubgroupExtractor("Physics", "стр")
        streams = extractor.extract(sample_implicit_subgroup_data)

        lab_streams = [s for s in streams if s.stream_type == StreamType.LAB]

        # 2 lab streams (both rows have Lab > 0)
        assert len(lab_streams) == 2

        # All should be marked as implicit subgroups
        for stream in lab_streams:
            assert stream.is_implicit_subgroup is True


class TestExplicitSubgroupExtractor:
    """Tests for ExplicitSubgroupExtractor."""

    def test_extract_subgroup_streams(self, sample_explicit_subgroup_data):
        """Test extracting explicit subgroup streams."""
        extractor = ExplicitSubgroupExtractor("Biology", "юр")
        streams = extractor.extract(sample_explicit_subgroup_data)

        practical_streams = [s for s in streams if s.stream_type == StreamType.PRACTICAL]

        # 2 practical streams (one per subgroup)
        assert len(practical_streams) == 2

        # All should be marked as subgroups
        for stream in practical_streams:
            assert stream.is_subgroup is True

    def test_preserves_subgroup_notation(self, sample_explicit_subgroup_data):
        """Test that group names preserve subgroup notation."""
        extractor = ExplicitSubgroupExtractor("Biology", "юр")
        streams = extractor.extract(sample_explicit_subgroup_data)

        practical_streams = [s for s in streams if s.stream_type == StreamType.PRACTICAL]

        # Group names should contain /1/ and /2/
        all_groups = []
        for stream in practical_streams:
            all_groups.extend(stream.groups)

        assert any("/1/" in g for g in all_groups)
        assert any("/2/" in g for g in all_groups)


class TestGetExtractor:
    """Tests for get_extractor factory function."""

    def test_get_pattern_1a_extractor(self):
        """Test getting Pattern1aExtractor."""
        extractor = get_extractor(PATTERN_1A, "Math", "оод (2)")
        assert isinstance(extractor, Pattern1aExtractor)

    def test_get_pattern_1b_extractor(self):
        """Test getting Pattern1bExtractor."""
        extractor = get_extractor(PATTERN_1B, "Math", "оод (2)")
        assert isinstance(extractor, Pattern1bExtractor)

    def test_get_implicit_subgroup_extractor(self):
        """Test getting ImplicitSubgroupExtractor."""
        extractor = get_extractor(PATTERN_IMPLICIT_SUBGROUP, "Math", "оод (2)")
        assert isinstance(extractor, ImplicitSubgroupExtractor)

    def test_get_explicit_subgroup_extractor(self):
        """Test getting ExplicitSubgroupExtractor."""
        extractor = get_extractor(PATTERN_EXPLICIT_SUBGROUP, "Math", "оод (2)")
        assert isinstance(extractor, ExplicitSubgroupExtractor)

    def test_unknown_pattern_defaults_to_1a(self):
        """Test unknown pattern defaults to Pattern1aExtractor."""
        extractor = get_extractor("unknown", "Math", "оод (2)")
        assert isinstance(extractor, Pattern1aExtractor)
