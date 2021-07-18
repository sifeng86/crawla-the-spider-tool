import json
from .cryptograpy import Crypto
from pymongo import MongoClient

with open("login/setting/config.json") as json_file:
    config = json.load(json_file)

crypto = Crypto()


class mongoHelper:

    def mongo_conn():
        # Connection to mongodb
        if config["mongo_mode"] == "atlas":
            atlas_pw = bytes(config["atlas_pw"], encoding='utf-8')
            atlas_pw = crypto.decrypt_message(atlas_pw)
            conn_str = "mongodb+srv://{user}:{pw}@{cluster}/{db}?retryWrites=true&w=majority".format(
                user=config["atlas_user"],
                pw=atlas_pw,
                cluster=config["atlas_host"],
                db=config["atlas_db"],
            )
            client = MongoClient(conn_str)
            return client[config["atlas_db"]]
        else:
            # Local
            client = MongoClient('localhost', 27017)
            return client[config["mongo_db"]]
