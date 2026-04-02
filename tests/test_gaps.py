import pytest
from booklet_reader.gaps import fill_gaps

PERFORMERS_CONFIG = [
    {
        "name": "Nagy Eszter",
        "instruments": [
            {
                "names": "hegedű / violin",
                "teachers": [
                    {"name": "Tóth Katalin", "from": "2020-09-01", "to": "2025-06-30"},
                    {"name": "Kovács Anna", "from": "2025-09-01"},
                ],
                "accompanists": [
                    {"name": "Fekete Mária", "from": "2023-09-01"},
                ],
            }
        ],
    }
]

class TestFillGaps:
    def test_leaves_existing_teacher(self):
        results = [{"performer": "Nagy Eszter", "instrument": "hegedű", "performance_date": "2024-03-15", "teacher": "Already Set", "accompanist": None}]
        filled = fill_gaps(results, PERFORMERS_CONFIG)
        assert filled[0]["teacher"] == "Already Set"
        assert filled[0]["accompanist"] == "Fekete Mária"

    def test_fills_teacher_by_date(self):
        results = [{"performer": "Nagy Eszter", "instrument": "hegedű", "performance_date": "2024-03-15", "teacher": None, "accompanist": None}]
        filled = fill_gaps(results, PERFORMERS_CONFIG)
        assert filled[0]["teacher"] == "Tóth Katalin"

    def test_fills_teacher_second_range(self):
        results = [{"performer": "Nagy Eszter", "instrument": "hegedű", "performance_date": "2025-11-01", "teacher": None, "accompanist": None}]
        filled = fill_gaps(results, PERFORMERS_CONFIG)
        assert filled[0]["teacher"] == "Kovács Anna"

    def test_no_match_leaves_null(self):
        results = [{"performer": "Unknown Player", "instrument": "hegedű", "performance_date": "2024-03-15", "teacher": None, "accompanist": None}]
        filled = fill_gaps(results, PERFORMERS_CONFIG)
        assert filled[0]["teacher"] is None

    def test_date_before_all_ranges(self):
        results = [{"performer": "Nagy Eszter", "instrument": "hegedű", "performance_date": "2019-01-01", "teacher": None, "accompanist": None}]
        filled = fill_gaps(results, PERFORMERS_CONFIG)
        assert filled[0]["teacher"] is None

    def test_instrument_alias_matching(self):
        results = [{"performer": "Nagy Eszter", "instrument": "hegedű", "performance_date": "2024-03-15", "teacher": None, "accompanist": None}]
        filled = fill_gaps(results, PERFORMERS_CONFIG)
        assert filled[0]["teacher"] == "Tóth Katalin"
