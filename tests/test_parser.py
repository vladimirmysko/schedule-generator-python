"""Tests for Form1Parser."""

from pathlib import Path

import pytest

from form1_parser.parser import Form1Parser


class TestForm1Parser:
    """Tests for Form1Parser class."""

    def test_parser_initialization_default_sheets(self):
        """Test parser initializes with default sheets."""
        parser = Form1Parser()
        assert len(parser.sheet_names) == 7
        assert "оод (2)" in parser.sheet_names

    def test_parser_initialization_custom_sheets(self):
        """Test parser initializes with custom sheets."""
        parser = Form1Parser(sheet_names=["test_sheet"])
        assert parser.sheet_names == ["test_sheet"]

    def test_parse_nonexistent_file(self, tmp_path):
        """Test parsing a nonexistent file."""
        parser = Form1Parser()
        result = parser.parse(tmp_path / "nonexistent.xlsx")

        assert len(result.errors) > 0
        assert "not found" in result.errors[0].lower()

    def test_validate_nonexistent_file(self, tmp_path):
        """Test validating a nonexistent file."""
        parser = Form1Parser()
        validation = parser.validate(tmp_path / "nonexistent.xlsx")

        assert validation["valid"] is False
        assert validation["file_exists"] is False

    def test_get_stats_empty_result(self):
        """Test getting stats from empty result."""
        from form1_parser.models import ParseResult

        parser = Form1Parser()
        result = ParseResult(
            file_path="test.xlsx",
            parse_date="2025-01-01",
        )

        stats = parser.get_stats(result)

        assert stats["total_subjects"] == 0
        assert stats["total_streams"] == 0
        assert stats["instructors_count"] == 0


class TestForm1ParserIntegration:
    """Integration tests for Form1Parser with actual Excel file."""

    @pytest.fixture
    def sample_excel_file(self, tmp_path):
        """Create a sample Excel file for testing."""
        import pandas as pd

        file_path = tmp_path / "test_form1.xlsx"

        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            # Create minimal test data that mimics Form-1 structure
            # Row 0-1: Headers
            # Row 2+: Data (starts with "1" in col 0)
            data = []

            # Header rows
            data.append([None] * 27)
            data.append(["Header"] * 27)

            # Data row with marker "1"
            row1 = [None] * 27
            row1[0] = "1"
            row1[1] = "Математика"
            row1[3] = "6В07302"
            row1[4] = "СТР-21 О"
            row1[6] = "каз"
            row1[7] = 25
            row1[8] = 15  # Lecture
            row1[9] = 23  # Practical
            row1[10] = 7  # Lab
            row1[25] = "Иванов А.О."
            data.append(row1)

            # Another data row
            row2 = [None] * 27
            row2[1] = "Математика"
            row2[3] = "6В07302"
            row2[4] = "СТР-22 О"
            row2[6] = "каз"
            row2[7] = 28
            row2[8] = 15
            row2[9] = 23
            row2[10] = 7
            row2[25] = "Иванов А.О."
            data.append(row2)

            df = pd.DataFrame(data)
            df.to_excel(writer, sheet_name="оод (2)", index=False, header=False)

        return file_path

    def test_parse_sample_file(self, sample_excel_file):
        """Test parsing a sample Excel file."""
        parser = Form1Parser(sheet_names=["оод (2)"])
        result = parser.parse(sample_excel_file)

        # Should have processed the sheet
        assert "оод (2)" in result.sheets_processed

        # Should have found the subject
        assert result.total_subjects >= 1

        # Should have extracted streams
        assert result.total_streams >= 1

    def test_validate_sample_file(self, sample_excel_file):
        """Test validating a sample Excel file."""
        parser = Form1Parser(sheet_names=["оод (2)"])
        validation = parser.validate(sample_excel_file)

        assert validation["valid"] is True
        assert validation["file_exists"] is True
        assert "оод (2)" in validation["sheets_found"]

    def test_stats_from_parsed_file(self, sample_excel_file):
        """Test getting stats from parsed file."""
        parser = Form1Parser(sheet_names=["оод (2)"])
        result = parser.parse(sample_excel_file)
        stats = parser.get_stats(result)

        assert stats["sheets_processed"] >= 1
        assert "streams_by_type" in stats
        assert "streams_by_sheet" in stats


class TestForm1ParserEdgeCases:
    """Edge case tests for Form1Parser."""

    def test_empty_sheet(self, tmp_path):
        """Test handling empty sheet."""
        import pandas as pd

        file_path = tmp_path / "empty.xlsx"

        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            df = pd.DataFrame()
            df.to_excel(writer, sheet_name="оод (2)", index=False)

        parser = Form1Parser(sheet_names=["оод (2)"])
        result = parser.parse(file_path)

        # Should handle gracefully with errors/warnings
        assert len(result.errors) > 0 or len(result.warnings) > 0

    def test_missing_expected_sheet(self, tmp_path):
        """Test handling missing expected sheet."""
        import pandas as pd

        file_path = tmp_path / "wrong_sheet.xlsx"

        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            df = pd.DataFrame({"col": [1, 2, 3]})
            df.to_excel(writer, sheet_name="wrong_name", index=False)

        parser = Form1Parser(sheet_names=["оод (2)"])
        result = parser.parse(file_path)

        # Should have warnings about missing sheet
        assert len(result.warnings) > 0
        assert "оод (2)" not in result.sheets_processed
