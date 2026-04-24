import sys
import subprocess
from login.lib.celery import celeryHelper


# Connection to redis
app = celeryHelper.redis_conn()

PREVIEW_SEPARATOR = '_&_'
LLM_METHOD = 'py_llm'
DEFAULT_PREVIEW_TIMEOUT = 50
DEFAULT_PREVIEW_EXPIRES = 120
LLM_PREVIEW_TIMEOUT = 570
LLM_PREVIEW_EXPIRES = 600
LLM_SOFT_TIME_LIMIT = 540
LLM_TIME_LIMIT = 600


def get_preview_method(args: str) -> str:
    parts = args.split(PREVIEW_SEPARATOR)
    if len(parts) < 4:
        return ''
    return parts[3]


def get_crawl_async_options(method: str) -> dict:
    if method == LLM_METHOD:
        return {
            'soft_time_limit': LLM_SOFT_TIME_LIMIT,
            'time_limit': LLM_TIME_LIMIT,
        }
    return {}


def get_preview_async_options(args: str) -> dict:
    method = get_preview_method(args)
    options = {
        'expires': DEFAULT_PREVIEW_EXPIRES,
    }
    if method == LLM_METHOD:
        options['expires'] = LLM_PREVIEW_EXPIRES
    options.update(get_crawl_async_options(method))
    return options


def get_preview_timeout(args: str) -> int:
    return LLM_PREVIEW_TIMEOUT if get_preview_method(args) == LLM_METHOD else DEFAULT_PREVIEW_TIMEOUT


def get_task_method(task_id: str) -> str:
    from login.lib.mongo import mongoHelper

    db = mongoHelper.mongo_conn()
    record = db.urls.find_one({'task_id': task_id}, {'c_method': 1})
    if not record:
        return ''
    return record.get('c_method', '')


def get_task_async_options(task_id: str) -> dict:
    return get_crawl_async_options(get_task_method(task_id))

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


if __name__ == "__main__":
    if len(sys.argv) == 1:
        exit('parameter is missing')
    if sys.argv[1] == '--preview':  
        # python celery_task1.py --preview pid0_&_steps_&_args_&_method
        if len(sys.argv) == 3:
            args = sys.argv[2]
            ret = crawl.apply_async(('--preview', args), **get_preview_async_options(args))
            count = 0
            result_output = ret.get(timeout=get_preview_timeout(args), propagate=False)
            ret.forget()
            print(str(result_output))
            
        else:
            exit('preview parameter is missing')
    elif sys.argv[1] == '--task':
        # python celery_task1.py --task taskid
        if len(sys.argv) == 3:
            task_id = sys.argv[2]
            crawl_signature = crawl.s('--task', task_id).set(**get_task_async_options(task_id))
            # add two tasks into queue and chaining with pipe
            (crawl_signature | export_csv.s('--task',
            task_id) | send_email.s('--task', task_id)).apply_async()
        else:
            exit('task parameter is missing')
