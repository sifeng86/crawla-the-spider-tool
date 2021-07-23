import time
import json, sys
import subprocess
from login.lib.celery import celeryHelper


# Connection to redis
app = celeryHelper.redis_conn()

@app.task(name='crawl')
def crawl(mode, args):
    try:
        ret = subprocess.check_output(
            ["python", "/work/main.py", mode, args], universal_newlines=True)

        if mode == '--preview':
            print(ret)
            if "__&Result&__" in ret:
                ret = ret.split("__&Result&__")
                if len(ret) > 1:
                    result = ret[1].replace('Final Result:', '').strip()
                    return str(result)
                else:
                    return "[]"
            else:
                return "No Elements found."

        return 'success_crawl_' + mode + '_' + args

    except Exception as e:
        return "Crawler is having difficulty"

@app.task(name='export_csv')
def export_csv(_, mode, task_id):
    try:
        ret = subprocess.check_output(
            ["python", "/work/export_csv.py", mode, task_id], universal_newlines=True)
        return 'success_export_csv_' + mode + '_' + task_id
    except Exception as e:
        return 'error'


@app.task(name='send_email')
def send_email(_, mode, task_id):
    try:
        ret = subprocess.check_output(
            ["python", "/work/sendmail.py", mode, task_id], universal_newlines=True)
        return 'success_send_email_' + mode + '_' + task_id
    except Exception as e:
        return 'error'
