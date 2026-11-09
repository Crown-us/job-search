import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jobhunter import discord_notify


class RoleMentionsTests(unittest.TestCase):
    def test_public_job_pings_only_matching_role(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            Path(folder, 'role_picker.json').write_text(json.dumps({'roles': {'🎨': '123', '💻': '456'}}), encoding='utf-8')
            with patch.object(discord_notify.config, 'DATA_DIR', Path(folder)):
                row = {'title': 'Graphic Designer', 'id': 'job', 'url': 'https://example.com'}
                public = discord_notify.build_single(row, public=True)
                self.assertIn('<@&123>', public['content'])
                self.assertNotIn('<@&456>', public['content'])
                self.assertNotIn('<@&', discord_notify.build_single(row)['content'])

    def test_missing_picker_does_not_break_delivery(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            with patch.object(discord_notify.config, 'DATA_DIR', Path(folder)):
                payload = discord_notify.build_single({'title': 'Graphic Designer'}, public=True)
                self.assertNotIn('<@&', payload['content'])
