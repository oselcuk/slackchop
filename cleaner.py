import argparse
import json
import pathlib
import sqlite3
import time

from os import chdir
from requests import get

from slackclient import SlackClient

# default to 10 days
def get_files(user_token, older_than=14):
    secs_in_day = 24*60*60
    sc = SlackClient(user_token)
    since = str(time.time() - older_than*secs_in_day)
    res = sc.api_call('files.list', ts_to=since)
    files = res['files']
    while res['paging']['page'] < res['paging']['pages']:
        res = sc.api_call(
            'files.list',
            ts_to=since,
            page=res['paging']['page']+1
        )
        files += res['files']

    return files

def download_file(file, headers={}):
    uri = file['url_private']
    try:
        foldername = time.strftime('%Y-%m-%d', time.gmtime(file['created']))
        folder = pathlib.Path(foldername)
        folder.mkdir(parents=True, exist_ok=True)
        filename = uri.split('-', 2)[-1].replace('/', '-')
        filepath = folder/filename
        if filepath.exists(): return
        res = get(uri, headers=headers, stream=True)
        with filepath.open('wb') as f:
            for chunk in res.iter_content(chunk_size=1024):
                f.write(chunk)
        with filepath.with_suffix('.meta.json').open('w') as f:
            json.dump(file, f)
    except Exception as e:
        with open('errors.txt', 'a') as log:
            log.write('Exception: {}\n\tOn file: {}\n'.format(e, uri))

def download_and_delete_files(token, files, download, delete):
    headers = {'Authorization': 'Bearer {}'.format(token)}
    sc = SlackClient(token)
    for file in files:
        if download:    download_file(file, headers)
        if delete:      sc.api_call('files.delete', file=file['id'])

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Download and delete old files from slack')
    parser.add_argument('-u', '--user-data-db', action='store', type=str)
    parser.add_argument('-t', '--user-tokens', action='store', nargs='*')
    parser.add_argument('-o', '--older-than', action='store', type=int, default=14)
    parser.add_argument('-d', '--download', action='store_true')
    parser.add_argument('-2', '--download-to', action='store', nargs='?')
    parser.add_argument('-D', '--delete', action='store_true')
    args = parser.parse_args()
    if args.user_tokens:
        tokens = args.user_tokens
    else:
        with sqlite3.connect(args.user_data_db or 'user_data.db') as db:
            tokens = db.execute(
                'SELECT token FROM tokens WHERE token LIKE "xoxp-%"'
            ).fetchall()
        tokens = [token for (token, ) in tokens]
    if args.download_to:
        pathlib.Path(args.download_to).mkdir(parents=True, exist_ok=True)
        chdir(args.download_to)
    for token in tokens:
        files = get_files(token, older_than=args.older_than)
        download_and_delete_files(token, files, download=args.download, delete=args.delete)
