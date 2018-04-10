from flask import Flask, request, make_response, g

from datastore import DataStore
from slackuser import User

############## Initialize flask and the global flask environment ##############
app = Flask(__name__)
g.d = DataStore()
g.admin = g.d.authed_users['ADMIN']
g.bot = g.d.authed_users['BOT']

####################### Flask routes ##########################
@app.route("/slackchop")
def endpoints():
    return 'Endpoints for slackchop, nothing to see here'

@app.route("/slackchop/authenticate", methods=["GET", "POST"])
def authenticate():
    auth_code = request.args['code']
    cres = g.d.credentials
    auth_response = User.do(
        "oauth.access",
        client_id=creds['client_id'],
        client_secret=creds['client_secret'],
        code=auth_code
    )
    user_token = auth_response['access_token']
    if 'user_id' not in auth_response:
        #fug
        return "Couldn't retrieve your identity. Please contact @ozy"
    user_id = auth_response['user_id']
    scopes = auth_response['scope']
    #test this

    user = User()
    user_info = (auth_response['user_id'], auth_response['access_token'])

    with sqlite3.connect('user_data.db') as db:
        db.execute('INSERT INTO tokens VALUES (?, ?)', user_info)
        db.commit()
    # TODO: set userid as primary key and use insert or update
    g.authed_users[user_info[0]] = user_info[1]
    Thread(target=new_user, args=user_info)
    return "Auth complete"