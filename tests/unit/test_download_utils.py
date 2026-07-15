"""
Unit tests for bronze download utilities
- resolve_month_key: folder/zip naming
- combine_csvs: combining multiple files and keep only first file's header

Run with: pytest tests/unit/test_download_utils.py -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.bronze.download_utils import resolve_month_key, combine_csvs

class TestResolveMonthKey:

    def test_2020_plus_style_input(self):
        """2020+ style: folder name already starts with YYYYMM."""
        result = resolve_month_key("202001-citibike-tripdata", "2020")
        assert result == "202001"

    def test_pre_2020_month_name_style(self):
        """Pre-2020 style: i.e. 1_January."""
        result = resolve_month_key("1_January", "2016")
        assert result == "201601"

    def test_two_digit_month_name_style(self):
        """Pre-2020 style: i.e. 12_December."""
        result = resolve_month_key("12_December", "2018")
        assert result == "201812"

    def test_unrecognized_folder_name(self):
        """A folder name matching neither convention should return None."""
        result = resolve_month_key("readme", "2016")
        assert result is None

    def test_case_insensitivity(self):
        """
        Month names are lowercased internally so this test resolves regardless of input casing
        """
        result = resolve_month_key("1_jaNUAry", "2016")
        assert result == "201601"

    def test_malformed_month_number_out_of_range(self):
        """
        Month 13 doesn't exist. The function should return None since 13 fails to match the number or month
        """
        result = resolve_month_key("13_December", "2016")
        assert result is None

    # Additional edge cases
    def test_zero_padexists_already(self):
        """Two-digit month number should not be double-padded."""
        result = resolve_month_key("05_May", "2019")
        assert result == "201905"

    def test_empty_string_input(self):
        """Empty input should return None, not raise an exception."""
        result = resolve_month_key("", "2016")
        assert result is None

    def test_month_name_only_no_number(self):
        """A month name with no leading number prefix doesn't match either
        convention and should return None."""
        result = resolve_month_key("January", "2016")
        assert result is None


class TestCombineCsvs:

    def _write_csv(self, path, header, rows):
        """Helper: write a simple CSV file with a given header and rows."""
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write(",".join(header) + "\n")
            for row in rows:
                f.write(",".join(row) + "\n")

    def test_single_file_header_preserved(self, tmp_path):
        """One input file with header and rows should pass through with no changes."""
        csv_path = tmp_path / "file1.csv"
        self._write_csv(
            csv_path,
            header=["tripduration", "starttime", "stoptime"],
            rows=[["100", "2016-01-01", "2016-01-01"], ["200", "2016-01-02", "2016-01-02"]]
        )

        output_path = tmp_path / "combined.csv"
        result = combine_csvs([str(csv_path)], str(output_path))

        assert result is True

        with open(output_path) as f:
            lines = f.readlines()

        assert len(lines) == 3  # 1 header + 2 data rows
        assert lines[0].strip() == "tripduration,starttime,stoptime"

    def test_multiple_files_only_first_header_kept(self, tmp_path):
        """
        Two files with identical headers: combined output should have
        exactly one header line, followed by all data rows from both files.
        """
        file1 = tmp_path / "file1.csv"
        file2 = tmp_path / "file2.csv"

        self._write_csv(
            file1,
            header=["tripduration", "starttime"],
            rows=[["100", "2016-01-01"]]
        )
        self._write_csv(
            file2,
            header=["tripduration", "starttime"],
            rows=[["200", "2016-01-02"], ["300", "2016-01-03"]]
        )

        output_path = tmp_path / "combined.csv"
        result = combine_csvs([str(file1), str(file2)], str(output_path))

        assert result is True

        with open(output_path) as f:
            lines = [line.strip() for line in f.readlines()]

        # Exactly one header line total
        header_lines = [line for line in lines if line == "tripduration,starttime"]
        assert len(header_lines) == 1

        # All 3 data rows present (1 from file1, 2 from file2)
        assert len(lines) == 4  # 1 header + 3 data rows total
        assert "100,2016-01-01" in lines
        assert "200,2016-01-02" in lines
        assert "300,2016-01-03" in lines

    def test_empty_file_list_returns_false(self, tmp_path):
        """No input files: should return False, not raise or create a file."""
        output_path = tmp_path / "combined.csv"
        result = combine_csvs([], str(output_path))

        assert result is False
        assert not output_path.exists()

    def test_deterministic_ordering_regardless_of_input_order(self, tmp_path):
        """
        Feeding files in different input orders should always produce the
        same combined output, since combine_csvs sorts paths internally.
        """
        file_a = tmp_path / "a_file.csv"
        file_b = tmp_path / "b_file.csv"
        file_c = tmp_path / "c_file.csv"

        self._write_csv(file_a, header=["col1"], rows=[["A"]])
        self._write_csv(file_b, header=["col1"], rows=[["B"]])
        self._write_csv(file_c, header=["col1"], rows=[["C"]])

        # Run 1: files given in order [c, a, b]
        output_1 = tmp_path / "combined_1.csv"
        combine_csvs([str(file_c), str(file_a), str(file_b)], str(output_1))

        # Run 2: files given in a different order [b, c, a]
        output_2 = tmp_path / "combined_2.csv"
        combine_csvs([str(file_b), str(file_c), str(file_a)], str(output_2))

        with open(output_1) as f:
            content_1 = f.read()
        with open(output_2) as f:
            content_2 = f.read()

        # Regardless of input order, both outputs should be identical,
        # since combine_csvs sorts paths before processing
        assert content_1 == content_2

        # And specifically, rows should appear in sorted filename order: A, B, C
        lines = [line.strip() for line in content_1.strip().split("\n")]
        assert lines == ["col1", "A", "B", "C"]
