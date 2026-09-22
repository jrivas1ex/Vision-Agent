"""
ShiftSchedule / ShiftWindow -- per LEAME.txt:
    Turno 1: 06:00 a 16:00
    Turno 2: 16:00 a 01:00 del dia siguiente
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta


@dataclass(frozen=True)
class ShiftWindow:
    number: int
    start: time
    end: time  # may be past midnight, handled in `contains`

    def contains(self, moment: datetime) -> bool:
        t = moment.time()
        if self.start <= self.end:
            return self.start <= t < self.end
        # wraps past midnight (Turno 2: 16:00 -> 01:00 next day)
        return t >= self.start or t < self.end

    def window_for(self, moment: datetime) -> tuple[datetime, datetime]:
        """Concrete [start, end) datetimes for the shift that contains `moment`."""
        if self.start <= self.end:
            start_dt = datetime.combine(moment.date(), self.start)
            end_dt = datetime.combine(moment.date(), self.end)
        else:
            if moment.time() >= self.start:
                start_dt = datetime.combine(moment.date(), self.start)
                end_dt = datetime.combine(moment.date() + timedelta(days=1), self.end)
            else:
                start_dt = datetime.combine(moment.date() - timedelta(days=1), self.start)
                end_dt = datetime.combine(moment.date(), self.end)
        return start_dt, end_dt


DEFAULT_SHIFTS = [
    ShiftWindow(1, time(6, 0), time(16, 0)),
    ShiftWindow(2, time(16, 0), time(1, 0)),
]


class ShiftSchedule:
    def __init__(self, shifts: list[ShiftWindow] | None = None):
        self.shifts = shifts or DEFAULT_SHIFTS

    def current_shift(self, moment: datetime | None = None) -> ShiftWindow:
        moment = moment or datetime.now()
        for shift in self.shifts:
            if shift.contains(moment):
                return shift
        return self.shifts[0]

    def is_working_time(self, moment: datetime | None = None) -> bool:
        """IsWorkingTime: True whenever `moment` falls in *some* configured
        shift (both shifts together cover 06:00->01:00; 01:00-06:00 is
        outside any shift)."""
        moment = moment or datetime.now()
        return any(s.contains(moment) for s in self.shifts)
