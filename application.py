import json
import random
import re
import requests
from sys import stderr
from itertools import islice

import praw
from credentials import *
from datetime import datetime, timedelta
from flask import Flask, request, make_response, render_template
from slackclient import SlackClient

sc = SlackClient(oauth_token_bot)
user = SlackClient(oauth_token_user)
reddit = praw.Reddit(client_id=reddit_client_id, 
    client_secret=reddit_client_secret,
    user_agent='Slackchop')

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



application = Flask(__name__)

def get_emojis(init=False, add=None, rmeove=None):
    # currently can't get this from an online list because slack doesn't return
    #  a list of default emoji they support and provide no way of checking if
    #  they support a particular emoji either
    emojis = open('emoji_names.txt').read().splitlines()
    # add all current emojis
    emojis += list(user.api_call('emoji.list')['emoji'].keys())
    return emojis

emojis = get_emojis()

def truncate_message(message):
    message = message[:4000]
    if message.endswith('::'):
        message = message[:-1]
    elif not message.endswith(':'):
        message = message.rsplit(':', 1)[0]
    return message

def send_message(*args, **kwargs):
    sc.api_call('chat.postMessage', *args, **kwargs)

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
        reply = ':{}:'.format('::'.join(random.choices(emojis, k=num)))
        send_message(channel=channel, text=truncate_message(reply))
        return
    match = re.match(r'!emoji\s+(:[^:]+:)(?:[\*xX\s])?(\d+)', message)
    if match and int(match[2]) > 0 and match[1][1:-1] in emojis:
        send_message(channel=channel, text=truncate_message(match[1]*int(match[2])))
        return
    match = re.match(r'!emoji\s+(\S+)\s*', message)
    if match:
        es = [x for x in emojis if re.search(match[1], x)]
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
            sc.api_call('chat.update', channel=event['channel'], text='Aborted by <@{}>. Contact <@{}>'.format(event['user'], slack_event['authed_users'][0]), ts=event['thread_ts'], attachments=[])
        handle_message(slack_event, event['text'])
    elif event_type == 'emoji_changed':
        global emojis
        if event['subtype'] == 'add':
            emojis.append(event['name'])
        elif event['subtype'] == 'remove':
            for name in event['names']:
                emojis.remove(name)
    else:
        p(slack_event)
    return make_response("Ok", 200, )

@application.route("/events", methods=["GET", "POST"])
def hears():
    slack_event = json.loads(request.data)
    # p(slack_event)
    if "challenge" in slack_event:
        return make_response(slack_event["challenge"],
            200, {"content_type": "application/json"})
    return event_handler(slack_event)

@application.route("/begin_auth", methods=["GET"])
def pre_install():
    return '''
      <a href="https://slack.com/oauth/authorize?scope={0}&client_id={1}">
          Add to Slack
      </a>
    '''.format(oauth_scope, client_id)

@application.route("/finish_auth", methods=["GET", "POST"])
def post_install():
    auth_code = request.args['code']
    sc = SlackClient("")
    auth_response = sc.api_call(
        "oauth.access",
        client_id=client_id,
        client_secret=client_secret,
        code=auth_code
    )
    user_token = auth_response['access_token']
    bot_token = auth_response['bot']['bot_access_token']
    return "Auth complete"

@application.route("/")
def go_away():
    return 'Go Away'

if __name__ == '__main__':
    application.run(debug=True)
