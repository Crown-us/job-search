import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from jobhunter import liveness

NOW = datetime(2026, 11, 10, tzinfo=timezone.utc)


def reply(status=200, url="", text="", data=None):
    resp = MagicMock(status_code=status, url=url, text=text)
    resp.json.return_value = data or {}
    return resp


class LivenessTests(unittest.TestCase):
    def run_check(self, source, url, resp):
        with patch.object(liveness.SESSION, "get", return_value=resp):
            return liveness.check(source, url, NOW)[0]

    def test_gone_status_closes(self):
        self.assertEqual(self.run_check("jobicy", "https://x/1", reply(410)), "closed")
        self.assertEqual(self.run_check("jobstreet", "https://x/1", reply(404)), "closed")

    def test_blocked_or_down_is_unknown(self):
        self.assertEqual(self.run_check("himalayas", "https://x/1", reply(403)), "unknown")
        self.assertEqual(self.run_check("remoteok", "https://x/1", reply(503)), "unknown")
        with patch.object(liveness.SESSION, "get", side_effect=TimeoutError):
            self.assertEqual(liveness.check("remoteok", "https://x/1", NOW)[0], "unknown")

    def test_jobstreet_expired_flag(self):
        u = "https://id.jobstreet.com/id/job/1"
        self.assertEqual(self.run_check("jobstreet", u, reply(url=u, text='"isExpired":true')), "closed")
        self.assertEqual(self.run_check("jobstreet", u, reply(url=u, text='"isExpired":false')), "open")

    def test_greenhouse_redirects(self):
        u = "https://job-boards.greenhouse.io/gitlab/jobs/8716179002"
        self.assertEqual(self.run_check("greenhouse", u, reply(url="https://job-boards.greenhouse.io/gitlab?error=true")), "closed")
        u = "https://jobs.dropbox.com/listing/7172713?gh_jid=7172713"
        self.assertEqual(self.run_check("greenhouse", u, reply(url="https://www.dropbox.jobs/en/jobs/7172713/x/")), "open")
        self.assertEqual(self.run_check("greenhouse", u, reply(url="https://www.dropbox.jobs/en/jobs/")), "closed")

    def test_kalibrr_deadline_and_visibility(self):
        u = "https://www.kalibrr.com/jobs/271112/x"
        past = {"application_end_date": "2026-11-06T10:15:59+00:00", "visibility": "public"}
        future = {"application_end_date": "2026-12-06T10:15:59+00:00", "visibility": "public"}
        hidden = {"application_end_date": "2027-01-01T00:00:00+00:00", "visibility": "unlisted"}
        self.assertEqual(self.run_check("kalibrr", u, reply(data=past)), "closed")
        self.assertEqual(self.run_check("kalibrr", u, reply(data=future)), "open")
        self.assertEqual(self.run_check("kalibrr", u, reply(data=hidden)), "closed")


if __name__ == "__main__":
    unittest.main()
