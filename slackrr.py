import requests
import re
import sys
import json
from threading import Thread

from flask import jsonify, make_response

class Arr(object):
    def __init__(self, medium):
        assert medium in ['tv', 'movies']
        self.medium = medium
        self.url = 'https://{}.prismo.biz'.format(medium)
        session = requests.Session()
        session.cert = 'prismo.pem'
        res = session.get(self.url)
        api_root = re.search(r"ApiRoot\s*:\s*'([^']+)',", res.text)[1]
        api_key = re.search(r"ApiKey\s*:\s*'([^']+)',", res.text)[1]
        self.api_base = self.url + api_root
        session.headers.update({'X-Api-Key': api_key})
        profile_id = session.get(self.api_base+'/profile').json()[0]['id']
        root_folder_path = session.get(self.api_base+'/rootfolder').json()[0]['path']
        download_options = {
            'profileId': profile_id,
            'rootFolderPath': root_folder_path,
            'addOptions': {
                'ignoreEpisodesWithFiles': False,
                'ignoreEpisodesWithoutFiles': False,
            }
        }
        if medium == 'tv':
            download_options['seasonFolder'] = True
            download_options['addOptions']['searchForMissingEpisodes'] = True
            self.type = 'Show'
            self.media_endpoint = '/series'
            self.db_key = 'tvdbId'
            self.db_url = 'http://www.thetvdb.com/?tab=series&id={}'
        else:
            download_options['addOptions']['searchForMovie'] = True
            self.type = 'Movie'
            self.media_endpoint = '/movie'
            self.db_key = 'tmdbId'
            self.db_url = 'https://www.themoviedb.org/movie/{}/'
        self.download_options = download_options
        self.session = session

    def get(self, url, **kwargs):
        return self.session.get(self.api_base+url, **kwargs)
    def post(self, url, **kwargs):
        return self.session.post(self.api_base+url, **kwargs)

sonarr = Arr('tv')
radarr = Arr('movies')

def get_link_for_media(media, arr):
    if 'imdbId' in media:
        return 'https://www.imdb.com/title/{}/'.format(media['imdbId'])
    return arr.db_url.format(media[arr.db_key])

def get_poster_for_media(media):
    if 'remote_poster' in media:
        return media['remote_poster']
    if 'images' in media and len(media['images']) > 0:
        return media['images'][-1]['url']
    return None

def get_attachment(media, arr):
    title = '{} ({})'.format(media['title'], media['year'])
    copied_fields = [arr.db_key, 'title', 'titleSlug', 'images', 'seasons', 'imdbId', 'year', 'seriesType']
    download_data = {field: media[field] for field in copied_fields if field in media}
    download_data.update(arr.download_options)
    message = {
        'title': title,
        'title_link': get_link_for_media(media, arr),
        'text': media['overview'],
        'thumb_url': get_poster_for_media(media),
        'footer': '{} | Rating: {:.1f}/10'.format(', '.join(media['genres']), media['ratings']['value']),
        'callback_id': 'add_{}'.format(arr.medium),
        'actions': [
            {
                'name': 'add_{}'.format(arr.type.lower()),
                'text': 'Add {} to Plex'.format(arr.type),
                'type': 'button',
                'value': json.dumps(download_data),
                'style': 'primary',
                'confirm': {
                    'title': 'Confirmation',
                    'text': 'Are you sure you want to add {} to Plex?'.format(title),
                    'ok_text': 'Yes',
                    'dismiss_text': 'No'
                }
            }
        ]
    }
    if arr.medium == 'tv':
        message['actions'][0]['confirm']['text'] += ' If this is an Anime, please click No and select the "Add Anime" button instead'
        message['actions'].insert(0, {
            'name': 'add_anime',
            'text': 'Add Anime to Plex',
            'type': 'button',
            'confirm': {
                'title': 'Confirmation',
                'text': 'Are you sure you want to add {} to Plex? If this is not an Anime, please click No and select the "Add Show" button instead'.format(title),
                'ok_text': 'Yes',
                'dismiss_text': 'No'
            }
        })
    return message

def media_1(name, vals, arr):
    res = arr.get(arr.media_endpoint+'/lookup', params={'term': name})
    candidates = res.json()
    attachments = map(lambda x: get_attachment(x, arr), candidates[:3])
    cs = len(candidates)
    update = {
        'text': 'Found {} candidates. Top {}:'.format(cs, min(cs, 3)),
        'attachments': list(attachments)
    }
    requests.post(vals['response_url'], json=update)

def media_2(payload, arr, chat_fn):
    media = json.loads(payload['actions'][0]['value'])
    update = {
        'text': 'Trying to add {}, please wait.'.format(media['title']),
        'replace_original': True
    }
    if payload['callback_id'] == 'add_anime':
        media['seriesType'] = 'anime'
    Thread(target=media_2_async, kwargs={
        'media': media,
        'payload': payload,
        'arr': arr,
        'chat_fn': chat_fn
    }).start()
    return jsonify(update)

def media_2_async(media, payload, arr, chat_fn):
    res = arr.get(arr.media_endpoint)
    for thing in res.json():
        if thing[arr.db_key] == media[arr.db_key]:
            response = {
                'text': '{} already on Plex, aborting'.format(arr.type),
                'replace_original': True
            }
            requests.post(payload['response_url'], json=response)
            return
    arr.post(arr.media_endpoint, json=media)
    text = 'Added <{}|{} ({})> to Plex at <@{}>\'s request'.format(
        get_link_for_media(media, arr), media['title'], media['year'], payload['user']['id'])
    chat_fn(text=text, channel=payload['channel']['id'])


def request_media(vals, token):
    if token:
        assert vals['token'] == token, "Verification tokens don't match!"
    text = vals['text'].strip().lower()
    parts = text.split(maxsplit=1)
    medium = parts[0]

    approved_channels = ['ftp-media-requests', 'poop-testing-public']

    if vals['channel_name'] not in approved_channels:
        return make_response(
            'You need to be in #ftp-media-requests to use this feature', 200, )
    if medium not in ['tv', 'movie', 'movies']:
        return make_response('Invalid command. First word of your command must be tv or movie', 200, )
    if len(parts) == 1:
        return make_response('Invalid command. Please include a name', 200, )

    name = parts[1]
    arr = sonarr if medium == 'tv' else radarr
    Thread(
        target=media_1,
        kwargs={'name':name, 'vals':vals, 'arr':arr}
    ).start()

    return make_response('Searching...', 200, )

def request_media_2(payload, chat_fn):
    arr = sonarr if payload['callback_id'] == 'add_tv' else radarr
    return media_2(payload, arr, chat_fn)