import requests

domain = 'https://slack.com/api/{}'

class User(object):

    def __init__(self, id, token, scopes):
        self.id = id
        self.token = token
        if isinstance(scopes, str): scopes = scopes.split(',')
        self.scopes = set(scopes)
        self.headers = { 'Authorization': 'Bearer {}'.format(token) }

    def tuple(self):
        return (self.id, self.token, ','.join(self.scopes))

    def do(self, method, **kwargs):
        url = domain.format(method)
        return requests.post(url, headers=self.headers, data=kwargs).json()

    @staticmethod
    def do(method, **kwargs):
        url = domain.format(method)
        return requests.post(url, data=kwargs)

    @staticmethod
    def truncate_message(message):
        message = message[:4000]
        if message.endswith('::'):
            message = message[:-1]
        elif not message.endswith(':'):
            message = message.rsplit(':', 1)[0]
        return message