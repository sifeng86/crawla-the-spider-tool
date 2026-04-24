import csv
import json
import sys
import os
import time
from collections import defaultdict
from login.lib.mongo import mongoHelper

# Connection to mongodb
db = mongoHelper.mongo_conn()


def normalize_csv_contents(contents):
    if isinstance(contents, dict):
        return json.dumps(contents, ensure_ascii=False)

    if isinstance(contents, list) and any(isinstance(item, (dict, list)) for item in contents):
        return json.dumps(contents, ensure_ascii=False)

    return contents


def maybe_wait(argv):
    try:
        if "--wait" in argv and len(argv) == 5:
            wait_time = int(argv[4])
            time.sleep(wait_time)
    except Exception as e:
        print(e)


def load_records(argv):
    if len(argv) == 1:
        raise SystemExit('parameter is missing')

    if argv[1] == '--task':
        if len(argv) >= 3:
            task_id = argv[2]
            results = db.contents.find({"task_id": task_id})
            return [i for i in results]

        print(argv)
        raise SystemExit('taskid parameter is missing')

    if argv[1] == '--all':
        results = db.contents.find()
        return [i for i in results]

    raise SystemExit('bad command')


def export_records(records):
    if len(records) == 0:
        raise SystemExit('no data to export')

    path = os.getcwd() + '/login/downloads/'
    os.makedirs(path, exist_ok=True)

    grouped_records = defaultdict(list)
    for item in records:
        data = [item['created_date'], normalize_csv_contents(item['contents']), str(item['created_at'])]
        grouped_records[item['task_id']].append(data)

    for task_id, rows in grouped_records.items():
        filename = path + task_id + '.csv'

        with open(filename, 'w', encoding='UTF8', newline='') as f:
            writer = csv.writer(f, delimiter=",")
            writer.writerows(rows)


def main(argv=None):
    argv = argv or sys.argv
    maybe_wait(argv)
    export_records(load_records(argv))


if __name__ == '__main__':
    main()

