import os
import sys
from datetime import datetime

import pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from backend.VideoFrameHelper import VideoFrameHelper


@pytest.mark.parametrize("text,expected", [
    ("2025年1月30日 15:21", datetime(2025, 1, 30, 15, 21)),
    ("2024年5月1日 03:05:07", datetime(2024, 5, 1, 3, 5, 7)),
    ("2023年12月31日15：30：45", datetime(2023, 12, 31, 15, 30, 45)),
    ("2023年12月31日\n15:30", datetime(2023, 12, 31, 15, 30)),
])
def test_parse_timestamp_valid(text, expected):
    assert VideoFrameHelper._parse_timestamp(text) == expected


@pytest.mark.parametrize("text", [
    "not a timestamp",
    "",
    "2024年13月1日 15:00",
])
def test_parse_timestamp_invalid(text):
    assert VideoFrameHelper._parse_timestamp(text) is None
