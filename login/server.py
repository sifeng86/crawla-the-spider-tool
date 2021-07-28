"""Python Flask WebApp Auth0 integration
"""
from functools import wraps
import json, sys
import random
import time, dateparser ,datetime
import subprocess, os
from os import environ as env
from werkzeug.exceptions import HTTPException

from dotenv import load_dotenv, find_dotenv
from flask import Flask
from flask import jsonify
from flask import redirect
from flask import render_template
from flask import session
from flask import url_for
from flask import request
from flask import send_from_directory
from authlib.integrations.flask_client import OAuth
from six.moves.urllib.parse import urlencode
from lib.mongo import mongoHelper

import constants

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

AUTH0_CALLBACK_URL = env.get(constants.AUTH0_CALLBACK_URL)
AUTH0_LOGOUT_REDIRECT_URL = env.get(constants.AUTH0_LOGOUT_REDIRECT_URL)
AUTH0_CLIENT_ID = env.get(constants.AUTH0_CLIENT_ID)
AUTH0_CLIENT_SECRET = env.get(constants.AUTH0_CLIENT_SECRET)
AUTH0_DOMAIN = env.get(constants.AUTH0_DOMAIN)
AUTH0_BASE_URL = 'https://' + AUTH0_DOMAIN
AUTH0_AUDIENCE = env.get(constants.AUTH0_AUDIENCE)

app = Flask(__name__, static_url_path='/public', static_folder='./public')
app.secret_key = env.get(constants.SECRET_KEY)
app.debug = True
app.TRAP_HTTP_EXCEPTIONS = True

errors = 0


# Connection to mongodb
db = mongoHelper.mongo_conn()

@app.errorhandler(Exception)
def handle_auth_error(ex):
    response = jsonify(message=str(ex))
    response.status_code = (ex.code if isinstance(ex, HTTPException) else 500)
    return response


oauth = OAuth(app)

auth0 = oauth.register(
    'auth0',
    client_id=AUTH0_CLIENT_ID,
    client_secret=AUTH0_CLIENT_SECRET,
    api_base_url=AUTH0_BASE_URL,
    access_token_url=AUTH0_BASE_URL + '/oauth/token',
    authorize_url=AUTH0_BASE_URL + '/authorize',
    client_kwargs={
        'scope': 'openid profile email',
    },
)


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if constants.PROFILE_KEY not in session:
            return redirect('/login')
        return f(*args, **kwargs)

    return decorated


# Controllers API
@app.route('/')
def home():
    return render_template('home.html')


@app.route('/callback')
def callback_handling():
    auth0.authorize_access_token()
    resp = auth0.get('userinfo')
    userinfo = resp.json()

    session[constants.JWT_PAYLOAD] = userinfo
    session[constants.PROFILE_KEY] = {
        'user_id': userinfo['sub'],
        'name': userinfo['name'],
        'email': userinfo['email'],
        'picture': userinfo['picture']
    }
    return redirect(url_for('contents'))


@app.route('/login')
def login():
    return auth0.authorize_redirect(redirect_uri=AUTH0_CALLBACK_URL, audience=AUTH0_AUDIENCE)


@app.route('/contents', methods=['POST','GET'])
@requires_auth
def contents():
    if request.method == 'POST':
        if not request.form.get('token') or request.form.get('token') != session['form_token']:
            return "Bad Request", 400
        error = None
        res = {}
        steps = request.form.getlist('steps[]')
        args = request.form.getlist('args[]')
        res['steps'] = list(filter(lambda x: x.strip() != '', steps))
        res['args'] = list(filter(lambda x: x.strip() != '', args))
        if len(res['steps']) != len(res['args']):
            error = 'Steps_and_Arguments_are_not_match.'
            return redirect(url_for('contents', error=error))
        res['task_name'] = request.form.get('task_name')
        res['url'] = request.form.get('url')
        res['c_method'] = request.form.get('c_method')
        res['noti_email'] = request.form.get('noti_email')
        res['user_id'] = session[constants.PROFILE_KEY]['user_id']
        res['task_id'] = session['form_token']
        res['created_at'] = str(dateparser.parse('today').date())
        dt = datetime.datetime.utcnow()
        if res['user_id'] and res['user_id'] == 'auth0|60f28997680b890068f4bea7':
            res['demo'] = dt
        db.urls.insert_one(res)

        # add tasks into queue and chaining with pipe
        try:
            ret = subprocess.check_output(
                ["python", "/work/celery_task1.py", "--task", res['task_id']], universal_newlines=True)
        except:
            pass

        msg = 'success'

        return redirect(url_for('contents', msg=msg))
        
    else:
        results = db.urls.find(
            {"user_id": session[constants.PROFILE_KEY]['user_id']}).sort("_id", -1)
        form_token = str(int(time.time())) + str(random.randint(1000, 10000))
        session['form_token'] = form_token
        return render_template('add_contents.html', userinfo=session[constants.PROFILE_KEY],
                                records=results, formtoken=session['form_token'])


@app.route('/temphtml', methods=['POST'])
@requires_auth
def temphtml():
    if request.method == 'POST':
        data = request.get_json()
        # data elements: data['preview_id'], data['url']
        # python main.py --temphtml pid_&_url
        if data:
            pid_url = data['preview_id'] + '_&_'+ data['url']
            ret = subprocess.run(
                ["python", "/work/main.py", "--temphtml", pid_url])
            print(ret)
        return "success", 200


@app.route('/preview', methods=['POST'])
@requires_auth
def preview():
    if request.method == 'POST':
        data = request.get_json()
        # data elements: data['preview_id'], data['url']
        # python main.py --preview pid_&_steps_&_args_&_method
        if data:
            pid_step_arg_method = data['preview_id'] + '_&_' + json.dumps(data['steps']) + \
            '_&_' + json.dumps(data['args']) + '_&_' + data['c_method']

            # add task to queue
            try:
                ret = subprocess.check_output(
                    ["python", "/work/celery_task1.py", "--preview", pid_step_arg_method], universal_newlines=True)
                return str(ret), 200
            except:
                return "Crawler is having difficulty", 500
        else:
            return "No data input", 500


@app.route('/del_contents/<tid>', methods=['GET'])
@requires_auth
def del_contents(tid):
    if request.method == 'GET':
        user_id = session[constants.PROFILE_KEY]['user_id']
        ret = db.urls.delete_one({"task_id": tid, "user_id": user_id})
        if ret.deleted_count == 1:
            try:
                filename = tid + '.csv'
                os.remove('/work/login/downloads/' + filename)
            except:
                pass
        msg = 'deleted'
        return redirect(url_for('contents',msg=msg))


@app.route('/dw_csv/<tid>', methods=['GET'])
@requires_auth
def dw_csv(tid):
    if request.method == 'GET':
        user_id = session[constants.PROFILE_KEY]['user_id']
        ret = db.urls.find({"task_id": tid, "user_id": user_id})
        print(ret)
        if len(list(ret)) != 0:
            filename = tid + '.csv'
            return send_from_directory('/work/login/downloads', filename, as_attachment=True)
        return "No file found", 404


@app.route('/logout')
def logout():
    session.clear()
    params = {'returnTo': AUTH0_LOGOUT_REDIRECT_URL, 'client_id': AUTH0_CLIENT_ID}
    return redirect(auth0.api_base_url + '/v2/logout?' + urlencode(params))


@app.route('/dashboard')
@requires_auth
def dashboard():
    return render_template('dashboard.html',
                           userinfo=session[constants.PROFILE_KEY],
                           userinfo_pretty=json.dumps(session[constants.JWT_PAYLOAD], indent=4))


@app.errorhandler(Exception)
def all_exception_handler(error):

    return "Error: " + str(error.code)


if __name__ == "__main__":
    app.run(port=env.get('PORT', 3000))
