"""Attendance-session logic: temporal confirmation, duplicate prevention,
enrolment checks and audit of unrecognised faces."""
from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime

import config
from core.database import Database
from core.face_engine import Detection


class AttendanceSession:
    def __init__(self, db: Database, engine, course_id: int, lecturer_id: int, actor: str = "system",
                 confirm_frames: int | None = None, now=datetime.now, clock=time.monotonic):
        self.db, self.engine = db, engine
        self.course_id, self.lecturer_id, self.actor = course_id, lecturer_id, actor
        self.confirm = config.CONFIRM_FRAMES if confirm_frames is None else confirm_frames
        self._now, self._clock = now, clock
        self.enrolled = db.enrolled_ids(course_id)
        self.counts: dict[int, int] = defaultdict(int)
        self.marked: dict[int, dict] = {}          # student_id -> record shown in the GUI
        self.unknown_events = 0
        self.not_enrolled = 0
        self.frames = 0
        self.started = now()
        self._last_unknown = float("-inf")
        course = db.get_course(course_id)
        self.course_code = course["course_code"] if course else str(course_id)
        db.log(actor, "SESSION_START", f"{self.course_code} - {len(self.enrolled)} students enrolled")

    # public API --------------------------------------------------------
    def process(self, frame):
        """Detect + recognise in one call (used by tests and the benchmark)."""
        return self.update(self.engine.process_frame(frame))

    def update(self, detections: list[Detection]):
        """Apply one frame's detections. Returns (detections, newly_marked_records)."""
        self.frames += 1
        seen, newly = set(), []
        unknown_present = False
        for det in detections:
            if not det.recognised:
                unknown_present = True
                continue
            sid = det.student_id
            if sid not in self.enrolled:
                det.note = "Not registered for this course"
                self.not_enrolled += 1
                continue
            seen.add(sid)
            if sid in self.marked:
                det.note = "Already recorded"
                continue
            self._sighting(det, newly)
        for sid in list(self.counts):                   # a face must be seen in consecutive frames
            if sid not in seen:
                self.counts[sid] = 0
        if unknown_present and self._clock() - self._last_unknown >= config.UNKNOWN_LOG_INTERVAL:
            self._last_unknown = self._clock()
            self.unknown_events += 1
            self.db.log(self.actor, "RECOGNITION_FAILED", f"Unrecognised face during {self.course_code}")
        return detections, newly

    def _sighting(self, det: Detection, newly: list) -> None:
        """Count one more consecutive sighting; write the record once the confirmation threshold is reached."""
        sid = det.student_id
        self.counts[sid] += 1
        if self.counts[sid] < self.confirm:
            return
        when = self._now()
        record = {"time": when.strftime("%H:%M:%S"), "matric": det.matric, "name": det.name,
                  "distance": det.distance, "student_id": sid}
        if self.db.mark_attendance(sid, self.course_id, self.lecturer_id, when):
            newly.append(record)
        else:                                           # already recorded earlier today
            record["time"] = "earlier"
        self.marked[sid] = record

    def end(self) -> dict:
        summary = {"course": self.course_code, "present": len(self.marked), "enrolled": len(self.enrolled),
                   "unknown_events": self.unknown_events, "frames": self.frames}
        self.db.log(self.actor, "SESSION_END",
                    f"{self.course_code}: {summary['present']}/{summary['enrolled']} present")
        return summary
