from configparser import ConfigParser
import sqlite3

from slackuser import User

class DataStore(object):

    tokens_db_name = 'user_tokens.db'
    ini_file = 'slackchop.ini'
    special_users = ('ADMIN', 'BOT')

    def __init__(self, ):
        config = ConfigParser()
        config.read(ini_file)
        credentials = config['credentials'].copy()
        self.initialize_sqlite()
        self.authed_users['ADMIN'] = User(
            credentials['admin_id'],
            credentials['admin_token'],
            None
        )
        self.authed_users['BOT'] = User(
            credentials['bot_id'],
            credentials['bot_token'],
            None
        )
        self.initialize_emoji_list()


    def initialize_emoji_list(init=False, add=None, rmeove=None):
        # Currently can't get this from an online list because slack doesn't
        #  return a list of default emoji they support and provide no way of
        #  checking if they support a particular emoji either
        el = open('emoji_names.txt').read().splitlines()
        el += list(self.authed_users['ADMIN'].do('emoji.list')['emoji'].keys())
        self.emoji_list = el

    def initialize_sqlite(self):
        with sqlite3.connect(tokens_db_name) as db:
            c = db.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS oauth_tokens (
                    user_id     TEXT NOT NULL PRIMARY KEY,
                    oauth_token TEXT NOT NULL,
                    scopes      TEXT NOT NULL
                )
            ''')
            db.commit()
            self.authed_users = {
                info[0] : User(*info)
                for info
                in c.execute('SELECT * FROM oauth_tokens')
            }


    def add_user(self, info):
        if info.id in authed_users:
            info.scopes += authed_users[info.id].scopes
        with sqlite3.connect(tokens_db_name) as db:
            c = db.cursor()
            c.execute(
                'INSERT OR REPLACE INTO oauth_tokens VALUES (?, ?, ?)',
                info.tuple()
            )
            db.commit()
        authed_users[info.id] = info