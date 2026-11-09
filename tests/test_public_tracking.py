import tempfile
import unittest
import requests
from pathlib import Path
from unittest.mock import patch

from jobhunter import bot, cli, db, discord_sync
from jobhunter.model import Job


class PublicTrackingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'jobs.db'
        self.patcher = patch('jobhunter.db.db_path', return_value=self.path)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.job = Job(source='jobstreet', company='Example', title='Junior Graphic Designer',
                       url='https://example.com/job', location='Jakarta', salary='IDR 5m')
        conn = db.connect()
        db.upsert(conn, [self.job.as_row()])
        db.record_deliveries(conn, [self.job.id], 'channel', 'message')
        conn.execute('UPDATE jobs SET score=5')
        db.save_analysis(conn, self.job.id, {'fit': 1})
        conn.close()

    def sync(self, dry_run=False):
        messages = [{'id': 'message', 'reactions': [
            {'emoji': {'name': '✅'}, 'count': 1},
            {'emoji': {'name': '🔖'}, 'count': 1}]}]
        with patch.object(discord_sync, 'credentials', return_value=('token', 'channel')), \
             patch.object(discord_sync, 'channel_ids', return_value=['channel']), \
             patch.object(discord_sync, 'fetch_messages', return_value=messages), \
             patch.object(discord_sync, 'fetch_reactors', create=True,
                          side_effect=lambda channel, message, emoji, token: [{'id': 'alice' if emoji == '✅' else 'bob'}]):
            return discord_sync.sync(dry_run=dry_run)

    def test_reactions_are_private_and_sync_is_idempotent(self):
        self.assertTrue(self.sync()['ok'])
        conn = db.connect()
        self.addCleanup(conn.close)
        self.assertEqual(conn.execute('SELECT status FROM jobs').fetchone()[0], 'new')
        rows = conn.execute('SELECT user_id,status FROM user_job_status ORDER BY user_id').fetchall()
        self.assertEqual([tuple(r) for r in rows], [('alice', 'applied'), ('bob', 'shortlist')])
        conn.close()
        self.assertEqual(self.sync()['changed'], [])
        self.assertEqual(bot.search('Graphic', user_id='alice'), [])
        self.assertEqual(len(bot.search('Graphic', user_id='bob')), 1)

    def test_dry_run_does_not_save_user_status(self):
        self.sync(dry_run=True)
        conn = db.connect()
        self.addCleanup(conn.close)
        self.assertEqual(conn.execute('SELECT count(*) FROM user_job_status').fetchone()[0], 0)
        conn.close()

    def test_legacy_default_channel_delivery_still_tracks(self):
        conn = db.connect()
        conn.execute("UPDATE deliveries SET channel='discord'")
        conn.commit()
        conn.close()
        self.assertEqual(len(self.sync()['changed']), 2)

    def test_public_feed_ignores_personal_fit_and_status(self):
        conn = db.connect()
        conn.execute("UPDATE jobs SET status='applied'")
        conn.commit()
        conn.close()
        args = cli.build_parser().parse_args(['discord', '--public', '--dry-run', '--min-fit', '70'])
        from io import StringIO
        from rich.console import Console
        out = StringIO()
        with patch.object(cli, 'console', Console(file=out, width=200)):
            self.assertEqual(cli.cmd_discord(args), 0)
        self.assertIn('Graphic Designer', out.getvalue())
        self.assertEqual(len(bot.search('Graphic')), 1)

    def test_api_failure_does_not_save_partial_results(self):
        messages = [{'id': 'message', 'reactions': [{'emoji': {'name': '✅'}, 'count': 1}]}]
        with patch.object(discord_sync, 'credentials', return_value=('token', 'channel')), \
             patch.object(discord_sync, 'channel_ids', return_value=['channel', 'broken']), \
             patch.object(discord_sync, 'fetch_messages', side_effect=[messages, requests.ConnectionError()]), \
             patch.object(discord_sync, 'fetch_reactors', return_value=[{'id': 'alice'}]):
            result = discord_sync.sync()
        self.assertFalse(result['ok'])
        self.assertEqual(result['changed'], [])
        conn = db.connect()
        self.addCleanup(conn.close)
        self.assertEqual(conn.execute('SELECT count(*) FROM user_job_status').fetchone()[0], 0)

    def test_reactor_pagination_excludes_bots(self):
        from unittest.mock import Mock
        first = Mock()
        first.json.return_value = [{'id': str(i), 'bot': i == 0} for i in range(100)]
        second = Mock()
        second.json.return_value = [{'id': '100'}]
        with patch.object(discord_sync.requests, 'get', side_effect=[first, second]):
            users = discord_sync.fetch_reactors('channel', 'message', '✅', 'token')
        self.assertEqual([u['id'] for u in users], [str(i) for i in range(1, 101)])

    def test_conflicting_reactions_have_stable_precedence(self):
        messages = [{'id': 'message', 'reactions': [
            {'emoji': {'name': '🏆'}, 'count': 1}, {'emoji': {'name': '✅'}, 'count': 1}]}]
        with patch.object(discord_sync, 'credentials', return_value=('token', 'channel')), \
             patch.object(discord_sync, 'channel_ids', return_value=['channel']), \
             patch.object(discord_sync, 'fetch_messages', return_value=messages), \
             patch.object(discord_sync, 'fetch_reactors', return_value=[{'id': 'alice'}, {'id': 'bot', 'bot': True}]):
            discord_sync.sync()
            self.assertEqual(discord_sync.sync()['changed'], [])
        conn = db.connect()
        self.addCleanup(conn.close)
        self.assertEqual([tuple(r) for r in conn.execute('SELECT user_id,status FROM user_job_status')], [('alice', 'offer')])


if __name__ == '__main__':
    unittest.main()

