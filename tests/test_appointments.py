from datetime import date

import pytest
from fastapi import HTTPException

from routers.appointments import _slot_start


def test_accepts_valid_wednesday_and_friday_slots():
    # Dates are intentionally far enough in the future for this feature test.
    assert _slot_start(date(2030, 1, 2), "06:00").strftime("%H:%M") == "06:00"
    assert _slot_start(date(2030, 1, 4), "12:00").strftime("%H:%M") == "12:00"


@pytest.mark.parametrize(("day", "slot_time"), [
    (date(2030, 1, 3), "06:00"),
    (date(2030, 1, 2), "05:30"),
    (date(2030, 1, 2), "12:30"),
    (date(2030, 1, 2), "06:15"),
])
def test_rejects_invalid_weekdays_and_times(day, slot_time):
    with pytest.raises(HTTPException):
        _slot_start(day, slot_time)
