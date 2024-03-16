import functools
from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from .db import get_db
from requests_oauthlib import OAuth1Session
import urllib.parse as parse
from dotenv import load_dotenv
import os
from urllib.parse import urlencode, urlunparse

load_dotenv()
api_key = os.environ["TW_CLI_KEY"]
api_secret = os.environ["TW_SCR_KEY"]

# api_key = os.environ.get("TW_CLI_KEY")
# api_secret = os.environ.get("TW_SCR_KEY")

# Twitter Endpoint
twitter_base_url = "https://api.twitter.com"
authorization_endpoint = twitter_base_url + "/oauth/authenticate"
request_token_endpoint = twitter_base_url + "/oauth/request_token"
token_endpoint = twitter_base_url + "/oauth/access_token"
credentials = twitter_base_url + "/1.1/account/verify_credentials.json"

bp = Blueprint("auth", __name__, url_prefix="/auth")

# def convert_to_number(string, min_val=200000, max_val=1000000):
#     # 文字列から数字とアンダースコアを取り出す
#     digits = [str(ord(char) - 96) if char.isalpha() else char for char in string.lower()]
    
#     # アンダースコアを除去
#     digits = ''.join(filter(lambda x: x != '_', digits))
    
#     # 数値に変換
#     number = int(''.join(digits))
    
#     # 200000から1000000の範囲に収め、かつ一意の値となるよう調整
#     offset = number - min_val
#     number = min_val + offset % (max_val - min_val)
    
#     return number

@bp.route("/twitter_login", methods=("GET", "POST"))
def twitter_login():
    # 1.リクエストトークンを取得する。
    # (Step 1: Obtaining a request token:https://developer.twitter.com/en/docs/authentication/guides/log-in-with-twitter)
    twitter = OAuth1Session(api_key, api_secret)
    # oauth_callback = request.args.get('oauth_callback')
    oauth_callback = "https://soundsynapse-316201ce96e2.herokuapp.com/auth/callback"
    res = twitter.post(
        request_token_endpoint, params={"oauth_callback": oauth_callback}
    )
    request_token = dict(parse.parse_qsl(res.content.decode("utf-8")))
    print(request_token)
    oauth_token = request_token["oauth_token"]
    oauth_token_secret = request_token["oauth_token_secret"]
    # 2.リクエストトークンを指定してTwitterへ認可リクエスト(Authorization Request)を行う。
    # (Step 2: Redirecting the user:https://developer.twitter.com/en/docs/authentication/guides/log-in-with-twitter#tab2)
    return redirect(
        authorization_endpoint
        + "?{}".format(parse.urlencode({"oauth_token": oauth_token}))
    )


@bp.route("/callback")
def callback():
    db = get_db()

    # 3.ユーザー認証/同意を行い、認可レスポンスを受け取る。
    oauth_verifier = request.args.get("oauth_verifier")
    oauth_token = request.args.get("oauth_token")

    # 4.認可レスポンスを使ってトークンリクエストを行う。
    # (Step 3: Converting the request token to an access token:https://developer.twitter.com/en/docs/authentication/guides/log-in-with-twitter#tab3)
    twitter = OAuth1Session(api_key, api_secret, oauth_token)

    res = twitter.post(token_endpoint, params={"oauth_verifier": oauth_verifier})

    access_token = dict(parse.parse_qsl(res.content.decode("utf-8")))

    twitter = OAuth1Session(
        api_key,
        api_secret,
        access_token["oauth_token"],
        access_token["oauth_token_secret"],
    )
    response = twitter.get(
        "https://api.twitter.com/1.1/account/verify_credentials.json"
    )
    user_info = response.json()

    # ユーザー名とアイコンのURLを取得
    userid = user_info["screen_name"]
    icon_url = user_info["profile_image_url_https"]
    name = user_info["name"]

    # session['user_id']=userid
    cursor = db.cursor()

    cursor.execute("SELECT * FROM oauth WHERE identifier=%s", (userid,))
    result = cursor.fetchone()
    if result is None:

        cursor.execute(
            "INSERT INTO username (userid,icon_url,name,frequency) VALUES (%s,%s,%s,%s)",
            (userid, icon_url, name,200000),
        )

        db.commit()
        # last_inserted_id = cur.lastrowid
        cursor.execute(
            "INSERT INTO oauth (identify_type,identifier,credential) VALUES (%s,%s,%s)",
            ("twitter", userid, access_token["oauth_token_secret"]),
        )

    else:
        # freq_int=convert_to_number(userid)
        cursor.execute(
            "UPDATE username SET icon_url=%s,name=%s,frequency=200000 WHERE userid=%s",
            (icon_url, name, userid),
        )
        cursor.execute(
            "UPDATE oauth SET credential=%s WHERE identifier=%s",
            (access_token["oauth_token_secret"], userid),
        )

    db.commit()
    # session['user']={"userid": userid, "icon_url": icon_url, "name": name}
    # return redirect(url_for("index"))
    # パラメータをURLに追加
    redirect_url = "https://iruka-backend.onrender.com/"
    return redirect(redirect_url)


@bp.route("/login")
def login():
    userid = session.get("user_id")
    if userid is None:
        return "login required."
    return userid


# @bp.before_app_request
# def load_logged_in_user():
#     user_id = session.get("user_id")

#     if user_id is None:
#         g.user = None
#     else:
#         g.user = (
#             get_db().execute("SELECT * FROM user WHERE id=%s", (user_id,)).fetchone()
#         )


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@bp.route("/")
def index():
    return "index"


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return "login required."
        return view(**kwargs)

    return wrapped_view
