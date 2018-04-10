import io
import json
import os
import random
import re
import requests
import sqlite3
import time
from sys import stderr
from itertools import islice
from threading import Thread

import praw
from datetime import datetime, timedelta
from flask import Flask, request, make_response, g
from slackclient import SlackClient

from meme_maker import make_meme

##########
from datastore import DataStore

############## Initialize flask and the global flask environment ##############
app = Flask(__name__)
g.d = DataStore()
g.admin = g.d.authed_users['ADMIN']
g.bot = g.d.authed_users['BOT']

###### move to relevant file
reddit = praw.Reddit(
    client_id=reddit_client_id,
    client_secret=reddit_client_secret,
    user_agent='Slackchop'
)

# this is an infinite random bit generator. shitty but it works
randbits = iter(lambda: random.getrandbits(1), 2)
def randstream(i):
    return iter(lambda: random.randrange(i), i)

def p(*args, **kwargs):
    print(*args, **kwargs, file = stderr)

youtube_url = 'https://www.youtube.com'
youtube_vid_regex = '/watch\?v=[^"]+'
google_search_base = 'https://www.google.com/search'
fake_mobile_agent = '''Mozilla/5.0 (iPhone; U; CPU iPhone OS 4_0 like Mac OS X; en-us) AppleWebKit/532.9 (KHTML, like Gecko) Versio  n/4.0.5 Mobile/8A293 Safari/6531.22.7'''
shake = {'?': 'question',
         '.': 'period',
         '~': 'tilde',
         '+': 'plus',
         '-': 'minus',
         '/': 'slash',
         '=': 'equals',
         ',': 'comma',
         '!': 'exclamation',
         '#': 'octothorpe',
         '$': 'dollar',
         '*': 'asterisk'}

##########

def send_message(*args, **kwargs):
    g.bot.do('chat.postMessage', *args, **kwargs)

def handle_message(slack_event, message):
    channel = slack_event['event']['channel']
    match = re.match(r'!youtube\s+(.+)', message)
    if match:
        res = requests.get(youtube_url + '/results',
            params={'search_query':match[1]})
        vids = re.findall(youtube_vid_regex, res.text)
        send_message(channel=channel, text=youtube_url+vids[0])
        return

    match = re.match(r'!(gif|image)\s+(.+)', message)
    if match:
        t, q = match[1], match[2]
        #TODO: Normalize messages before passing them to modules
        q = re.sub(r'<[^\|]*\|([^>]+)>', r'\1', q)
        params = {'tbm':'isch', 'q':q, 'safe':''}
        if t == 'gif': params['tbs'] = 'itp:animated'
        response = requests.get(google_search_base,
            params=params, headers={"User-agent": fake_mobile_agent})
        links = re.findall(r'imgurl\\x3d([^\\]+)\\', response.text)
        send_message(channel=channel, text=random.choice(links),
            unfurl_links=True, unfurl_media=True)

    match = re.match(r'!roll\s+(\d*|an?)\s*[dD]\s*(\d+)', message)
    if match:
        n, d = match[1], match[2]
        n = 1 if 'a' in n else int(n)
        d = int(d)
        reply = ', '.join([str(random.randrange(d)+1) for i in range(n)])
        send_message(channel=channel, text=reply);
        return
    if message.rstrip() == '!flip':
        reply = 'heads' if random.getrandbits(1) else 'tails'
        send_message(channel=channel, text=reply);
        return
    match = re.match(r'!shuffle\s+(\S.*)', message)
    if match:
        items = list(map(str.strip, (match[1].split(',') if ',' in match[1] else match[1].split())))
        random.shuffle(items)
        reply = ', '.join(items) if ',' in match[1] else ' '.join(items)
        send_message(channel=channel, text=reply);
        return

    match = re.match(r'!emoji\s+(\d+)\s*', message)
    if match:
        num = int(match[1])
        if num == 0: return
        reply = ':{}:'.format('::'.join(random.choices(g.emojis, k=num)))
        send_message(channel=channel, text=truncate_message(reply))
        return
    match = re.match(r'!emoji\s+(:[^:]+:)(?:[\*xX\s])?(\d+)', message)
    if match and int(match[2]) > 0 and match[1][1:-1] in g.emojis:
        send_message(channel=channel, text=truncate_message(match[1]*int(match[2])))
        return
    match = re.match(r'!emoji\s+(\S+)\s*', message)
    if match:
        es = [x for x in g.emojis if re.search(match[1], x)]
        if len(es) == 0: return
        reply = ':{}:'.format('::'.join(es))
        send_message(channel=channel, text=truncate_message(reply))
        return

    match = re.match(r'!shake\s+(\S.*)', message)
    if match:
        pattern = 'shake_{}'
        words = []
        for word in match[1].split():
            parts = []
            for letter in word.lower():
                if letter.isalnum():
                    parts.append(pattern.format(letter))
                elif letter in shake:
                    parts.append(pattern.format(shake[letter]))
            words.append(':' + '::'.join(parts) + ':')
        reply = ':space:'.join(words)
        send_message(channel=channel, text=truncate_message(reply))
        return

    match = re.match(r'!waho\s+(\S.*)', message)
    if match:
        pattern = '{}-waho'
        words = []
        for word in match[1].split():
            parts = []
            for letter in word.lower():
                if letter in 'wafflehouse':
                    parts.append(pattern.format(letter))
                else:
                    parts.append('waffle')
            words.append(':' + '::'.join(parts) + ':')
        reply = ':space:'.join(words)
        send_message(channel=channel, text=truncate_message(reply))
        return

    if message.startswith('!emojify'):
        words = message.split(' ')[1:]
        pattern = ':{}:'
        if words[0].startswith('`') and words[0].endswith('`'):
            pattern = words[0][1:-1]
            words = words[1:]
        if len(words) == 1:
            words = words[0]
        ems = list(map(lambda x: pattern.format(x), words))
        send_message(channel=channel, text=''.join(ems))
        return

    match = re.match(r'!meme(?:\s+"([^"]*)")(?:\s+"([^"]*)")?(?:\s+"([^"]*)")?', message)
    if match:
        image = make_meme(*match.groups())
        data = io.BytesIO()
        image.save(data, 'jpeg')
        bot.api_call('files.upload', channels=[channel], file=data.getvalue())
        return

    take = lambda x: not x.stickied and not x.is_self
    match = re.match(r'!randfeld\s+(.*)', message)
    if match:
        sub = choose(filter(take,
            reddit.subreddit('seinfeldgifs').search(match[1]+' self:no')), 50)
        send_message(channel=channel, text=sub.url,
            unfurl_links=True, unfurl_media=True, icon_emoji=':jerry:')
        return
    if message.startswith('!randfeld'):
        sub = choose(filter(take,
            reddit.subreddit('seinfeldgifs').hot(limit=50)))
        send_message(channel=channel, text=sub.url,
            unfurl_links=True, unfurl_media=True, icon_emoji=':jerry:')
        return

    if message.startswith('!gridtext '):
        text = message.split(' ', 1)[1]
        if len(text) > 80: text = text[:80]
        res = []
        n = len(text)
        for i in range(n):
            res.append(' '.join(text))
            text = text[-1] + text[:-1]
        reply = '```{}```'.format('\n'.join(res))
        send_message(channel=channel, text=reply)
        return

def choose(seq, limit=None):
    if limit: seq = islice(seq, limit)
    ret = None
    for item, take in zip(seq, randstream(5)):
        if not ret: ret = item
        if not take: return item
    return ret

def event_handler(slack_event):
    # p(slack_event)
    event = slack_event['event']
    event_type = event['type']
    if event_type == 'reaction_added':
        user_id = event['user']
    elif event_type == 'message' and 'text' in event:
        if event['text'] == 'ABORT' and 'thread_ts' in event:
            bot.api_call('chat.update', channel=event['channel'], text='Aborted by <@{}>. Contact <@{}>'.format(event['user'], usr_id), ts=event['thread_ts'], attachments=[])
        handle_message(slack_event, event['text'])
    elif event_type == 'emoji_changed':
        if event['subtype'] == 'add':
            g.emojis.append(event['name'])
        elif event['subtype'] == 'remove':
            for name in event['names']:
                g.emojis.remove(name)
    else:
        p(slack_event)
    return make_response("Ok", 200, )

@app.route("/slackchop/slash/s", methods=["POST"])
def find_replace():
    val = request.values
    # p(val['channel_id'], val['user_id'], val['command'], val['text'])

    # Make sure we can edit the user's messages
    if val['user_id'] not in authed_users:
        return "Please authorize slackchop to edit your messages"
    token = authed_users[val['user_id']]

    parts = re.split(r'(?<!\\)(?:\\\\)*\/', val['text'])
    if len(parts) != 4 or parts[0] != '':
        return "Malformed expression. Make sure to have exactly 3 unescaped slashes, escape the rest with `\\/`"

    sc = SlackClient(token)
    result = sc.api_call(
        'conversations.history',
        channel=val['channel_id'],
        limit=20
    )
    # p('Result:', result, '\n')
    if not result['ok']:
        return "Couldn't read channel history, contact @ozy"
    message = next(
        (m for m in result['messages'] if 'user' in m and m['user'] == val['user_id']),
        None
    )
    if not message:
        return "Currently only supports editing in last 20 messages"

    count = 1
    if parts[3] == 'g': count = 0
    if parts[3].isdigit(): count = int(parts[3])
    # p('Message:', message, '\n')
    text = re.sub(parts[1], parts[2], message['text'], count=count)
    # p('Text:', text, '\n')
    sc.api_call(
        'chat.update',
        channel=val['channel_id'],
        text=text,
        ts=message['ts']
    )
    return make_response('', 200, )

@app.route("/slackchop/events", methods=["GET", "POST"])
def hears():
    slack_event = json.loads(request.data)
    # p(slack_event)
    if "challenge" in slack_event:
        return make_response(slack_event["challenge"],
            200, {"content_type": "application/json"})
    return event_handler(slack_event)

def new_user(user_id, user_token):
    sc = SlackClient(user_token)
    two_weeks_ago = str(time.time() - 14*24*60*60)
    res = sc.api_call('files.list', ts_to=two_weeks_ago)
    files = res['files']
    while res['paging']['page'] < res['paging']['pages']:
        res = sc.api_call('files.list',
            ts_to=two_weeks_ago,
            page=res['paging']['page']+1)
        files += res['files']
    for file in files:
        sc.api_call('files.delete', file=file['id'])



@app.route("/slackchop")
def go_away():
    return 'Endpoints for slackchop, nothing to see here'

if __name__ == '__main__':
    app.run(debug=True)
