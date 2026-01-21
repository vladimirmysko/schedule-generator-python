"""Test fixtures for Form-1 parser tests."""

import pandas as pd
import pytest


@pytest.fixture
def sample_pattern_1a_data():
    """Sample data for Pattern 1a (Horizontal - Individual)."""
    return pd.DataFrame(
        {
            "subject": ["Math", "Math", "Math"],
            "group": ["СТР-21 О", "СТР-22 О", "СТР-23 О"],
            "language": ["каз", "каз", "орыс"],
            "students": [25, 28, 30],
            "lecture": [15, 15, 15],
            "practical": [23, 23, 23],
            "lab": [7, 7, 7],
            "instructor": ["Иванов А.О.", "Иванов А.О.", "Петров С.П."],
            "original_index": [10, 11, 12],
        }
    )


@pytest.fixture
def sample_pattern_1b_data():
    """Sample data for Pattern 1b (Horizontal - Merged)."""
    return pd.DataFrame(
        {
            "subject": ["Chemistry", "Chemistry", "Chemistry", "Chemistry"],
            "group": ["БЖД-11 О", "ВЕТ-11 О", "ТБПП-11 О", "ЗК-11 О"],
            "language": ["каз", "каз", "каз", "каз"],
            "students": [20, 22, 18, 25],
            "lecture": [30, 0, 0, 0],
            "practical": [8, 0, 8, 0],
            "lab": [7, 0, 7, 0],
            "instructor": ["Сидоров А.О.", "Сидоров А.О.", "Сидоров А.О.", "Сидоров А.О."],
            "original_index": [20, 21, 22, 23],
        }
    )


@pytest.fixture
def sample_implicit_subgroup_data():
    """Sample data for implicit subgroups."""
    return pd.DataFrame(
        {
            "subject": ["Physics", "Physics"],
            "group": ["СТР-21 О", "СТР-21 О"],
            "language": ["каз", "каз"],
            "students": [25, 25],
            "lecture": [30, 0],
            "practical": [8, 0],
            "lab": [7, 7],
            "instructor": ["Козлов Доц.", "Козлов Доц."],
            "original_index": [30, 31],
        }
    )


@pytest.fixture
def sample_explicit_subgroup_data():
    """Sample data for explicit subgroups."""
    return pd.DataFrame(
        {
            "subject": ["Biology", "Biology"],
            "group": ["АРХ-11 О /1/", "АРХ-11 О /2/"],
            "language": ["орыс", "орыс"],
            "students": [15, 15],
            "lecture": [15, 0],
            "practical": [45, 45],
            "lab": [0, 0],
            "instructor": ["Новикова Асс.", "Новикова Асс."],
            "original_index": [40, 41],
        }
    )


@pytest.fixture
def sample_dataframe_with_header():
    """Sample DataFrame simulating raw sheet data with header rows."""
    data = [
        [None, None, None, None, None, None, None, None, None, None, None],
        [None, "Header", None, None, None, None, None, None, None, None, None],
        ["1", "Subject", None, "Code", "Group", None, "Lang", "Stud", "Lec", "Prac", "Lab"],
        ["1", "Math", None, "6В07302", "СТР-21 О", None, "каз", 25, 15, 23, 7],
        [None, None, None, None, "СТР-22 О", None, "каз", 28, 15, 23, 7],
    ]
    return pd.DataFrame(data)


@pytest.fixture
def form1_test_file(tmp_path):
    """Create a temporary test Excel file."""
    file_path = tmp_path / "test_form1.xlsx"

    # Create a minimal test workbook
    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        # Create a simple sheet with test data
        data = {
            0: [None, None, "1", None, None],
            1: [None, "Header", "Math", "Math", "Physics"],
            2: [None, None, None, None, None],
            3: [None, None, "6В07302", "6В07302", "6В07303"],
            4: [None, None, "СТР-21 О", "СТР-22 О", "СТР-21 О"],
            5: [None, None, 5, 5, 4],
            6: [None, None, "каз", "каз", "орыс"],
            7: [None, None, 25, 28, 30],
            8: [None, None, 15, 15, 30],
            9: [None, None, 23, 23, 15],
            10: [None, None, 7, 7, 8],
            # ... columns up to instructor
            25: [None, None, "Иванов А.О.", "Иванов А.О.", "Петров Доц."],
        }
        df = pd.DataFrame(data)
        df.to_excel(writer, sheet_name="оод (2)", index=False, header=False)

    return file_path
