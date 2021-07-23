import json
from .cryptograpy import Crypto
from celery import Celery

with open("login/setting/config.json") as json_file:
    config = json.load(json_file)

crypto = Crypto()


class celeryHelper:

    def redis_conn():
        # Connection to redis
        redis_pw = bytes(config["redis_pw"], encoding='utf-8')
        redis_pw = crypto.decrypt_message(redis_pw)
        redis_host_port = 'redis://:{pw}@{host_port}'.format(
            pw=redis_pw,
            host_port=config["redis_host_port"]
        )

        broker = redis_host_port
        backend = redis_host_port

        app = Celery('task1', broker=broker, backend=backend)

        app.conf.update(
            worker_concurrency=2,
            timezone='Asia/Taipei',
            enable_utc=True,
            result_expires=300
        )
        return app
