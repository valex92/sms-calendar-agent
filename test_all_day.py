import unittest
from unittest.mock import MagicMock, patch
import datetime
from calendar_service import _is_date_only, _format_event_time, create_event, update_event

class TestAllDayEventFormatting(unittest.TestCase):

    def test_is_date_only(self):
        self.assertTrue(_is_date_only("2026-09-07"))
        self.assertTrue(_is_date_only(" 2026-12-31 "))
        self.assertFalse(_is_date_only("2026-09-07T09:00:00-04:00"))
        self.assertFalse(_is_date_only("invalid-date"))
        self.assertFalse(_is_date_only(None))
        self.assertFalse(_is_date_only(""))

    def test_format_single_day_all_day(self):
        # When end_time is the next day (exclusive)
        start, end = _format_event_time("2026-09-07", "2026-09-08", all_day=True)
        self.assertEqual(start, {"date": "2026-09-07"})
        self.assertEqual(end, {"date": "2026-09-08"})

    def test_format_all_day_same_date_auto_adjusts(self):
        # If LLM produces same start and end date for all-day event, auto-adjust to +1 day
        start, end = _format_event_time("2026-09-07", "2026-09-07", all_day=True)
        self.assertEqual(start, {"date": "2026-09-07"})
        self.assertEqual(end, {"date": "2026-09-08"})

    def test_format_all_day_missing_end_time(self):
        # If end_time is None, auto-set to start_date + 1 day
        start, end = _format_event_time("2026-09-07", None, all_day=True)
        self.assertEqual(start, {"date": "2026-09-07"})
        self.assertEqual(end, {"date": "2026-09-08"})

    def test_format_multi_day_all_day(self):
        # Multi-day event: start Sept 7, ends Sept 10
        start, end = _format_event_time("2026-09-07", "2026-09-10", all_day=True)
        self.assertEqual(start, {"date": "2026-09-07"})
        self.assertEqual(end, {"date": "2026-09-10"})

    def test_format_all_day_from_iso_strings(self):
        # If LLM passed ISO timestamps with all_day=True
        start, end = _format_event_time("2026-09-07T00:00:00-04:00", "2026-09-07T23:59:59-04:00", all_day=True)
        self.assertEqual(start, {"date": "2026-09-07"})
        self.assertEqual(end, {"date": "2026-09-08"})

    def test_format_date_only_string_inferred_as_all_day(self):
        # If all_day was False or not passed, but start_time is YYYY-MM-DD
        start, end = _format_event_time("2026-09-07", "2026-09-08", all_day=False)
        self.assertEqual(start, {"date": "2026-09-07"})
        self.assertEqual(end, {"date": "2026-09-08"})

    def test_format_timed_event(self):
        # Timed event remains unchanged with dateTime and timezone
        start, end = _format_event_time("2026-09-07T14:00:00-04:00", "2026-09-07T15:00:00-04:00", all_day=False)
        self.assertEqual(start, {"dateTime": "2026-09-07T14:00:00-04:00", "timeZone": "America/New_York"})
        self.assertEqual(end, {"dateTime": "2026-09-07T15:00:00-04:00", "timeZone": "America/New_York"})

class TestCreateAndUpdateEventMocked(unittest.TestCase):

    @patch("calendar_service.get_calendar_service")
    def test_create_all_day_event(self, mock_get_svc):
        mock_svc = MagicMock()
        mock_get_svc.return_value = mock_svc
        mock_insert = MagicMock()
        mock_svc.events().insert.return_value = mock_insert
        mock_insert.execute.return_value = {"htmlLink": "https://calendar.google.com/test", "id": "test_id"}

        success, msg = create_event(
            title="Primrose Closed",
            start_time="2026-09-07",
            end_time="2026-09-08",
            attendees=["attendee@example.com"],
            all_day=True
        )

        self.assertTrue(success)
        mock_svc.events().insert.assert_called_once()
        call_kwargs = mock_svc.events().insert.call_args.kwargs
        body = call_kwargs["body"]
        self.assertEqual(body["summary"], "Primrose Closed")
        self.assertEqual(body["start"], {"date": "2026-09-07"})
        self.assertEqual(body["end"], {"date": "2026-09-08"})
        self.assertNotIn("dateTime", body["start"])
        self.assertNotIn("dateTime", body["end"])
        self.assertEqual(body["attendees"], [{"email": "attendee@example.com"}])

    @patch("calendar_service.get_calendar_service")
    def test_update_timed_to_all_day(self, mock_get_svc):
        mock_svc = MagicMock()
        mock_get_svc.return_value = mock_svc
        mock_get = MagicMock()
        mock_svc.events().get.return_value = mock_get
        mock_get.execute.return_value = {
            "id": "evt123",
            "summary": "Existing Event",
            "start": {"dateTime": "2026-09-07T09:00:00-04:00", "timeZone": "America/New_York"},
            "end": {"dateTime": "2026-09-07T10:00:00-04:00", "timeZone": "America/New_York"}
        }
        mock_patch = MagicMock()
        mock_svc.events().patch.return_value = mock_patch
        mock_patch.execute.return_value = {"htmlLink": "https://calendar.google.com/test"}

        success, msg = update_event(
            event_id="evt123",
            new_title="Updated All Day Event",
            new_start="2026-09-07",
            new_end="2026-09-08",
            all_day=True
        )

        self.assertTrue(success)
        mock_svc.events().patch.assert_called_once()
        body = mock_svc.events().patch.call_args.kwargs["body"]
        self.assertEqual(body["summary"], "Updated All Day Event")
        self.assertEqual(body["start"], {"date": "2026-09-07"})
        self.assertEqual(body["end"], {"date": "2026-09-08"})
        self.assertNotIn("dateTime", body["start"])
        self.assertNotIn("dateTime", body["end"])

if __name__ == "__main__":
    unittest.main()
