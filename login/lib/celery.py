import json
from .cryptograpy import Crypto
from celery import Celery

with open("login/setting/config.json") as json_file:
    config = json.load(json_file)

crypto = Crypto()


class celeryHelper:

    def redis_conn():
        # Connection to redis
        if config["redis_host_port"] == 'local':
            broker = 'redis://redis:6379'
            backend = 'redis://redis:6379'
        else:
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
            worker_concurrency=1,
            timezone='Asia/Taipei',
            enable_utc=True,
            result_expires=300,
            broker_pool_limit= 10,
            redis_max_connections=15,
            worker_cancel_long_running_tasks_on_connection_loss=True
        )
        return app
