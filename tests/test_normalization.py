"""Tests for instructor name normalization."""

import pytest

from form1_parser.normalization import normalize_instructor_name


class TestNormalizeInstructorName:
    """Tests for normalize_instructor_name function."""

    def test_ao_without_space(self):
        """Test 'а.о.' prefix without space is removed."""
        result = normalize_instructor_name("а.о.Шалаев Б.Б.")
        assert result == "Шалаев Б.Б."

    def test_ao_with_space(self):
        """Test 'а.о. ' prefix with space is removed."""
        result = normalize_instructor_name("а.о. Шалаев Б.Б.")
        assert result == "Шалаев Б.Б."

    def test_ao_variations_produce_same_result(self):
        """Test that both 'а.о.' and 'а.о. ' produce identical output."""
        without_space = normalize_instructor_name("а.о.Шалаев Б.Б.")
        with_space = normalize_instructor_name("а.о. Шалаев Б.Б.")
        assert without_space == with_space

    def test_sp_prefix(self):
        """Test 'с.п.' prefix is removed."""
        result = normalize_instructor_name("с.п. Иванов И.И.")
        assert result == "Иванов И.И."

    def test_sp_double_period(self):
        """Test 'с.п..' (typo with double period) is handled."""
        result = normalize_instructor_name("с.п.. Петров П.П.")
        assert result == "Петров П.П."

    def test_docent_prefix(self):
        """Test 'доцент' prefix is removed."""
        result = normalize_instructor_name("доцент Козлов К.К.")
        assert result == "Козлов К.К."

    def test_prof_abbreviated_prefix(self):
        """Test 'проф.' prefix is removed."""
        result = normalize_instructor_name("проф. Сидоров С.С.")
        assert result == "Сидоров С.С."

    def test_professor_full_prefix(self):
        """Test 'профессор' prefix is removed."""
        result = normalize_instructor_name("профессор Михайлов М.М.")
        assert result == "Михайлов М.М."

    def test_kaz_associate_prof_prefix(self):
        """Test 'қ.проф.' (Kazakh associate professor) prefix is removed."""
        result = normalize_instructor_name("қ.проф. Ахметов А.А.")
        assert result == "Ахметов А.А."

    def test_ass_prof_prefix(self):
        """Test 'асс.проф.' prefix is removed."""
        result = normalize_instructor_name("асс.проф. Николаев Н.Н.")
        assert result == "Николаев Н.Н."

    def test_st_prep_prefix(self):
        """Test 'ст.преп.' prefix is removed."""
        result = normalize_instructor_name("ст.преп. Волков В.В.")
        assert result == "Волков В.В."

    def test_prepodavatel_full_prefix(self):
        """Test 'преподаватель' prefix is removed."""
        result = normalize_instructor_name("преподаватель Федоров Ф.Ф.")
        assert result == "Федоров Ф.Ф."

    def test_english_prof_prefix(self):
        """Test 'prof.' (English) prefix is removed."""
        result = normalize_instructor_name("prof. Smith J.")
        assert result == "Smith J."

    def test_english_dr_prefix(self):
        """Test 'Dr' prefix is removed."""
        result = normalize_instructor_name("Dr Johnson M.")
        assert result == "Johnson M."

    def test_empty_string(self):
        """Test empty string returns empty string."""
        result = normalize_instructor_name("")
        assert result == ""

    def test_none_value(self):
        """Test None value returns empty string."""
        result = normalize_instructor_name(None)
        assert result == ""

    def test_whitespace_normalization(self):
        """Test extra whitespace is collapsed."""
        result = normalize_instructor_name("  Иванов   И.И.  ")
        assert result == "Иванов И.И."

    def test_name_without_prefix(self):
        """Test name without prefix is returned unchanged (except whitespace)."""
        result = normalize_instructor_name("Иванов И.И.")
        assert result == "Иванов И.И."

    def test_case_insensitive(self):
        """Test prefix matching is case-insensitive."""
        result = normalize_instructor_name("А.О. Шалаев Б.Б.")
        assert result == "Шалаев Б.Б."

    def test_d_abbreviated_prefix(self):
        """Test 'д.' (abbreviated доцент) prefix is removed."""
        result = normalize_instructor_name("д. Кузнецов К.К.")
        assert result == "Кузнецов К.К."

    def test_p_abbreviated_prefix(self):
        """Test 'п.' (abbreviated преподаватель) prefix is removed."""
        result = normalize_instructor_name("п. Смирнов С.С.")
        assert result == "Смирнов С.С."

    def test_o_prefix(self):
        """Test 'о.' prefix is removed."""
        result = normalize_instructor_name("о. Попов П.П.")
        assert result == "Попов П.П."

    def test_ao_no_period_with_space(self):
        """Test 'а.о ' (no period after о, with space) prefix is removed."""
        result = normalize_instructor_name("а.о Тестов Т.Т.")
        assert result == "Тестов Т.Т."

    def test_sp_no_period_with_space(self):
        """Test 'с.п ' (no period after п, with space) prefix is removed."""
        result = normalize_instructor_name("с.п Образцов О.О.")
        assert result == "Образцов О.О."


class TestNormalizationConsistency:
    """Tests for consistency across different variations."""

    @pytest.mark.parametrize(
        "input_name",
        [
            "а.о.Шалаев Б.Б.",
            "а.о. Шалаев Б.Б.",
            "а.о.  Шалаев Б.Б.",
            "  а.о.Шалаев Б.Б.  ",
            "А.О.Шалаев Б.Б.",
        ],
    )
    def test_ao_variations_all_normalize_same(self, input_name):
        """Test all а.о. variations normalize to same result."""
        result = normalize_instructor_name(input_name)
        assert result == "Шалаев Б.Б."

    @pytest.mark.parametrize(
        "input_name",
        [
            "с.п.Иванов И.И.",
            "с.п. Иванов И.И.",
            "с.п..Иванов И.И.",
            "с.п.. Иванов И.И.",
            "С.П.Иванов И.И.",
        ],
    )
    def test_sp_variations_all_normalize_same(self, input_name):
        """Test all с.п. variations normalize to same result."""
        result = normalize_instructor_name(input_name)
        assert result == "Иванов И.И."
