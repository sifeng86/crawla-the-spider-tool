import csv
import sys
import os
import time
from collections import defaultdict
from login.lib.mongo import mongoHelper

# Connection to mongodb
db = mongoHelper.mongo_conn()
mode = None
records = []


# initial waiting for crawling result
try:
    if "--wait" in sys.argv and len(sys.argv) == 5:
        wait_time = int(sys.argv[4])
        time.sleep(wait_time)
except Exception as e:
    print(e)


########################
# check the cmd commands
# getting data from db
########################
if len(sys.argv) == 1:
    exit('parameter is missing')

if sys.argv[1] == '--task':
    # python export_csv.py --task taskid
    if len(sys.argv) >= 3:
        mode = "task"
        task_id = sys.argv[2]
        results = db.contents.find({"task_id": task_id})
        records = [i for i in results]
    else:
        print(sys.argv)
        exit('taskid parameter is missing')

elif sys.argv[1] == '--all':
    # python export_csv.py --all
    mode = "all"
    results = db.contents.find()
    records = [i for i in results]

else:
    exit('bad command')



if len(records) == 0:
    exit('no data to export')

# mkdir if not exist
path = os.getcwd() + '/login/downloads/'
os.makedirs(path, exist_ok=True)


##################
# start to export
##################
d = defaultdict(list)
for item in records:
    data = [item['created_date'], item['contents'], str(item['created_at'])]
    d[item['task_id']].append(data)

for k,v in d.items():
    filename = path + k + '.csv'
 
    with open(filename, 'a', encoding='UTF8', newline='') as f:
        writer = csv.writer(f, delimiter=",")
        writer.writerows(v)

