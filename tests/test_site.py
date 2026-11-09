import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from jobhunter import db, site
from jobhunter.model import Job

NOW = datetime(2026, 11, 9, 3, 0, tzinfo=timezone.utc)


class PublicSiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'jobs.db'
        patcher = patch('jobhunter.db.db_path', return_value=self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

        recent = (NOW - timedelta(hours=5)).isoformat()
        old = (NOW - timedelta(days=60)).isoformat()
        week = (NOW - timedelta(days=7)).isoformat()
        jobs = [
            Job(source='jobstreet', company='PT Contoh <Jaya>', title='Junior Web Developer',
                url='https://example.com/a', location='Surabaya', salary='Rp 5.000.000', posted_at=recent),
            Job(source='jobstreet', company='', title='Web Developer',
                url='https://example.com/anon', location='Jakarta', posted_at=recent),
            Job(source='kalibrr', company='PT Lama', title='Web Developer',
                url='https://example.com/old', location='Jakarta', posted_at=old),
            Job(source='kalibrr', company='PT Gaji Palsu', title='Graphic Designer',
                url='https://example.com/c', location='Jakarta', salary='1', posted_at=week),
            Job(source='jobstreet', company='PT Lain', title='Head Chef',
                url='https://example.com/chef', location='Jakarta', posted_at=recent),
        ]
        conn = db.connect()
        db.upsert(conn, [j.as_row() for j in jobs])
        conn.execute("UPDATE jobs SET status='applied', notes='catatan pribadi', score_reason='rahasia'")
        db.save_analysis(conn, jobs[0].id, {'fit': 91, 'gaps': ['gap pribadi']})
        conn.close()

    def test_selection_and_privacy(self):
        out = Path(self.tmp.name) / 'site'
        with patch('jobhunter.site.datetime') as clock:
            clock.now.return_value = NOW
            clock.fromtimestamp = datetime.fromtimestamp
            page, count = site.build(out, min_score=0)
        html = page.read_text(encoding='utf-8')
        data = json.loads((out / 'jobs.json').read_text(encoding='utf-8'))
        titles = {j['company'] for j in data['jobs']}

        self.assertEqual(titles, {'PT Contoh <Jaya>', 'PT Gaji Palsu'})
        self.assertEqual(count, 2)
        by_company = {j['company']: j for j in data['jobs']}
        self.assertTrue(by_company['PT Contoh <Jaya>']['new'])
        self.assertFalse(by_company['PT Gaji Palsu']['new'])
        self.assertEqual(by_company['PT Gaji Palsu']['salary'], '')

        for secret in ('catatan pribadi', 'rahasia', 'gap pribadi', '"fit"', 'applied'):
            self.assertNotIn(secret, html)
            self.assertNotIn(secret, json.dumps(data))
        self.assertIn('PT Contoh &lt;Jaya&gt;', html)
        self.assertNotIn('—', html)

    def test_empty_board_renders_message(self):
        html = site.render([], 'Job Hunter', NOW)
        self.assertIn('Belum ada lowongan', html)
        self.assertIn('belum memuat lowongan', html)


if __name__ == '__main__':
    unittest.main()
