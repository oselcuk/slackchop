from sqlite3 import connect
import re
import sys

#TODO: parameterize
CONTENT_CHANNEL = 'C1UJVTPTQ'
DATABASE = 'content_data.db'

with connect(DATABASE) as db:
    db.execute('''
        CREATE TABLE IF NOT EXISTS content (
            ts          INTEGER PRIMARY KEY,
            user_name   TEXT,
            content     TEXT,
            positive    INTEGER,
            negative    INTEGER,
            neutral     INTEGER
        )
    ''')

def process_new_content(url, user, ts):
    ts = ts_string_to_num(ts)
    with connect(DATABASE) as db:
        db.execute('INSERT INTO content VALUES (?,?,?,0,0,0)', (ts, user, url))

def process_karma(user, karma):
    with connect(DATABASE) as db:
        ts = db.execute('''
            SELECT ts
            FROM content
            WHERE user_name = ?
            ORDER BY ts DESC
            LIMIT 1
        ''', (user, )).fetchone()
        if not ts: return
        ts = ts[0]
        assert karma in ['positive', 'negative', 'neutral']
        content = db.execute('''
            UPDATE content
            SET {} = {} + 1
            WHERE ts = ?
        '''.format(karma, karma), (ts, ))

def user_id_to_name(client, user):
    res = client.api_call('users.info', user=user)
    return res['user']['profile']['display_name']

def ts_string_to_num(ts):
    if '.' in ts:
        l, r = ts.split('.')
        return 1_000_000 * int(l) + int(r)
    return 1_000_000 * int(ts)

def get_leaders(ts, limit=10, since=7*24*60*60):
    since = ts_string_to_num(ts) - since * 1_000_000
    with connect(DATABASE) as db:
        leaders = db.execute('''
            SELECT *
            FROM content
            WHERE ts > ?
            LIMIT ?
        ''', (since, limit)).fetchall()
    leaders = sorted(leaders, key=lambda x:x[4]-x[3])
    print(leaders, file=sys.stderr)
    result = []
    for idx, row in enumerate(leaders):
        _, name, content, pos, neg, pun = row
        result.append('#{:>2}({:=+3d}): @{} with {}'.format(idx+1, pos-neg, name, content))
    return '\n'.join(result)

def process_message(client, channel, user, text, ts, **kwargs):
    if text.strip() == '!dankest':
        client.api_call(
            'chat.postMessage',
            channel=channel,
            text=get_leaders(ts)
        )
        return
    if channel != CONTENT_CHANNEL: return
    match = re.search(r'<(http.*?)>', text, re.IGNORECASE)
    if match:
        url = match[1]
        process_new_content(url, user_id_to_name(client, user), ts)
    match = re.search(r'(<[A-Z0-9]+>|[\w.-]+)([+-]{2,})', text)
    if match:
        user, karma = match.groups()

        if user[0] == '<':
            user = user_id_to_name(client, user[1:-1])

        karma = set(karma)
        if len(karma) == 1:
            karma = 'positive' if karma.pop() == '+' else 'negative'
        else:
            karma = 'neutral'

        process_karma(user, karma)
