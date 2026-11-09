"""Apply the approved Discord sidebar layout; preserve IDs and permissions."""
import json
import sys
import time
from datetime import datetime
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jobhunter import config, discord_sync

GUILD = '1561704898389606521'
CATEGORIES = [
    ('1561911025865986108', 'Pusat Informasi'),
    ('1561725076754399323', 'Bursa Lowongan'),
    ('1561704899165560872', 'Ruang Komunitas'),
    ('1561704899165560874', 'Ruang Suara'),
    ('1561729446375985273', 'Area Privat'),
]
CHANNELS = [
    ('1561911081948151808', '👋︱selamat-datang', 0),
    ('1561911782480683080', '🎭︱pilih-bidang', 0),
    ('1561725081095250023', '💻︱dev-it', 1),
    ('1561730155158966363', '🎨︱kreatif', 1),
    ('1561733022368407623', '🌍︱remote', 1),
    ('1562114975248416788', '📌︱loker-umum-manual', 1),
    ('1561704899165560875', '💬︱general', 2),
    ('1562100616396800071', '💡︱idea', 2),
    ('1562108654436749455', '🤬︱hujat-pemerintah', 2),
    ('1562117727316086855', '🦅︱random', 2),
    ('1562121192876408883', '🗑️︱dump', 2),
    ('1561704899165560876', '🔊︱General', 3),
]

def main():
    token, channel_id = discord_sync.credentials()
    session = requests.Session()
    session.headers.update({'Authorization': f'Bot {token}', 'User-Agent': 'jobhunter/0.1'})
    def call(method, path, **kwargs):
        for attempt in range(4):
            r = session.request(method, 'https://discord.com/api/v10'+path, timeout=25, **kwargs)
            if r.status_code == 429 and attempt < 3:
                time.sleep(min(float(r.json().get('retry_after', 2)), 30))
                continue
            if not r.ok:
                raise RuntimeError(f'{method} {path}: HTTP {r.status_code}')
            return r.json() if r.content else None
    selected = call('GET', f'/channels/{channel_id}')
    if selected.get('guild_id') != GUILD:
        raise RuntimeError('Configured server differs from approved target')
    before = call('GET', f'/guilds/{GUILD}/channels')
    by_id = {c['id']: c for c in before}
    changes = [(cid, {'name': name}) for cid, name in CATEGORIES]
    changes += [(cid, {'name': name, 'parent_id': CATEGORIES[group][0]}) for cid, name, group in CHANNELS]
    for cid, change in changes:
        if cid not in by_id:
            raise RuntimeError('Expected channel missing')
        print(by_id[cid]['name'], '->', change['name'])
    if '--apply' not in sys.argv:
        return
    backup = config.DATA_DIR / 'server-layout'
    backup.mkdir(exist_ok=True)
    path = backup / (datetime.now().strftime('%Y%m%d-%H%M%S') + '.json')
    path.write_text(json.dumps(before, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Backup:', path)
    for cid, change in changes:
        call('PATCH', f'/channels/{cid}', json=change)
    positions = [{'id': cid, 'position': i} for i, (cid, _) in enumerate(CATEGORIES)]
    positions += [{'id': cid, 'position': i} for i, (cid, _, _) in enumerate(CHANNELS)]
    call('PATCH', f'/guilds/{GUILD}/channels', json=positions)
    after = call('GET', f'/guilds/{GUILD}/channels')
    result = {c['id']: c for c in after}
    for cid, change in changes:
        for key, value in change.items():
            if result[cid].get(key) != value:
                raise RuntimeError(f'Verification failed: {cid} {key}')
        normalize = lambda c: sorted(c.get('permission_overwrites', []), key=lambda x: x['id'])
        if normalize(result[cid]) != normalize(by_id[cid]):
            raise RuntimeError(f'Permissions changed: {cid}; inspect backup')
    actual_categories = sorted((c for c in after if c['id'] in dict(CATEGORIES)), key=lambda c: c['position'])
    if [c['id'] for c in actual_categories] != [cid for cid, _ in CATEGORIES]:
        raise RuntimeError('Category order mismatch')
    print('VERIFIED: 5 categories, 12 channels; names, parents, category order and permissions.')

if __name__ == '__main__':
    main()
