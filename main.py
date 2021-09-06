import requests
import json, sys, datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
from login.lib.step_helper import stepHelper
from login.lib.mongo import mongoHelper


# initiate libraries
ua = UserAgent()
errors = 0
user_agent = ua.random
print(user_agent)
response = None
mode = "normal"

# Connection to mongodb
db = mongoHelper.mongo_conn()

def get_page(url):
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Gpc": "1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": user_agent
    }
    response = requests.get(url=url, headers=headers)
    return response

if len(sys.argv) <= 1:
    exit('no parameters')

########################
# check the cmd commands
# getting seed from db
########################
if len(sys.argv) == 1:
    exit('parameter is missing')

if sys.argv[1] == '--all':
    # python main.py --all
    results = db.urls.find()
    records = [i for i in results]

elif sys.argv[1] == '--py_requests':
    # python main.py --py_requests
    results = db.urls.find({"c_method": "py_requests"})
    records = [i for i in results]

elif sys.argv[1] == '--py_selenium':
    # python main.py --py_selenium
    results = db.urls.find({"c_method":"py_selenium"})
    records = [i for i in results]

elif sys.argv[1] == '--user':
    # python main.py --user user123
    if len(sys.argv) == 3:
        user_id = sys.argv[2]
        results = db.urls.find(
            {"user_id": user_id}).sort("_id", -1).limit(1)
        records = [i for i in results]
    else:
        exit('user parameter is missing')

elif sys.argv[1] == '--task':
    # python main.py --task taskid
    if len(sys.argv) == 3:
        task_id = sys.argv[2]
        results = db.urls.find(
            {"task_id": task_id}).sort("_id", -1).limit(1)
        records = [i for i in results]
    else:
        exit('task parameter is missing')

elif sys.argv[1] == '--temphtml':
    # python main.py --temphtml pid0_&_url
    mode = "temphtml"
    if len(sys.argv) == 3:
        arg_pid, arg_url = sys.argv[2].split('_&_')
        results = db.preview_contents.find(
            {"preview_id": arg_pid}).sort("_id", -1).limit(1)
        records = [i for i in results]
        if len(records) == 0:
            response = get_page(arg_url).text
            params = {}
            params['url'] = arg_url
            params['preview_id'] = arg_pid
            params['contents'] = response
            params['created_at'] = datetime.datetime.utcnow()
            db.preview_contents.insert_one(params)
        else:
            exit('contents cache existed!')
        exit('temphtml ended')
    else:
        exit('preview parameter is missing')

elif sys.argv[1] == '--preview':
    # python main.py --preview pid0_&_steps_&_args_&_method
    mode = "preview"
    if len(sys.argv) == 3:
        arg_items = sys.argv[2].split('_&_')
        if len(arg_items) != 4:
            exit('preview parameter is missing')
        arg_pid = arg_items[0]
        arg_steps = json.loads(arg_items[1])
        arg_args = json.loads(arg_items[2])
        arg_method = arg_items[3]

        results = db.preview_contents.find(
            {"preview_id": arg_pid}).sort("_id", -1).limit(1)
        records = [i for i in results]
        if len(records) > 0:
            response = records[0]['contents']
        else:
            records = [{}]
            response = None
        records[0]['steps'] = arg_steps
        records[0]['args'] = arg_args
        records[0]['c_method'] = arg_method
        records[0]['task_id'] = arg_pid

    else:
        exit('preview parameter is missing')
else:
    exit('required parameters are missing')

if len(records) == 0:
    exit('no data to crawl')



################
# start crawling
################
for seed in records:
    results = []
    method = seed.get('c_method', None)
    task_id = seed.get('task_id', None)
    task_name = seed.get('task_name', None)
    noti_email = seed.get('noti_email', None)
    user_id = seed.get('user_id',None)
    url = seed.get('url',None)
    steps = list(zip(seed['steps'], seed['args']))

    if method == "py_requests":
        if response == None:
            response = get_page(url)
            ret = BeautifulSoup(response.text, 'html.parser')
        else:
            ret = BeautifulSoup(response, 'html.parser')

        # keep the original version clean
        temp = ret

        soup_steps_helper = stepHelper.get_soup_steps_helper()
        for i in steps:
            try:
                print('Steps+Args: ',i[0], i[1])
                print('Soup_cmd: ', soup_steps_helper[i[0]].format(param=i[1]))
                if 'ext_str_' in i[0]:
                    if isinstance(temp, list):
                        item_list = []
                        for s in temp:
                            exec("item_list.append(s" + soup_steps_helper[i[0]].format(param=i[1])+".strip().replace('\\n',' '))")
                        results.append(item_list)
                        # restore temp to original version
                        temp = ret
                    else:
                        exec("temp = temp" + soup_steps_helper[i[0]].format(param=i[1])+".strip().replace('\\n',' ')")
                        results.append(temp)
                        # restore temp to original version
                        temp = ret
                else:
                    exec("temp = temp" +
                        soup_steps_helper[i[0]].format(param=i[1]))

            except Exception as e:
                print(e)
                print("Steps or Args failed")

    else:
        try:
            options = Options()
            options.add_argument("window-size=1366,784")
            options.add_argument(f"user-agent={user_agent}")
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            driver = webdriver.Remote(
                command_executor='http://chrome:4444/wd/hub', options=options)
            driver.implicitly_wait(10)
            print(url)
            driver.get(url)
            driver.save_screenshot("screenshot.png")
            selenium_steps_helper = stepHelper.get_selenium_steps_helper()

            ret = driver


            for i in steps:
                if 'ext_str_' in i[0]:
                    if isinstance(ret, list):
                        item_list = []
                        for s in ret:
                            exec("item_list.append(s" + selenium_steps_helper[i[0]].format(
                                param=i[1])+".strip().replace('\\n', ' '))")
                        results.append(item_list)
                    else:
                        exec("ret = ret" +
                             selenium_steps_helper[i[0]].format(param=i[1])+".strip().replace('\\n', ' ')")
                        results.append(ret)

                else:
                    if (type(ret) is str) or (type(ret) is list) or ret == None:
                        head = "ret = driver"
                    else:
                        head = "ret = ret"
                    exec(head + selenium_steps_helper[i[0]].format(param=i[1]))
                print('Selenium_cmd: ',i)
            driver.quit()

        except Exception as e: 
            print(e)
            driver.quit()
    
    # clean response
    response = None

    if mode == "normal":
        items = {}
        items['contents'] = results
        items['task_id'] = task_id
        items['task_name'] = task_name
        items['noti_email'] = noti_email
        dt = datetime.datetime.utcnow()
        if user_id and user_id == 'auth0|60f28997680b890068f4bea7':
            items['demo'] = dt
        items['created_at'] = dt
        items['created_date'] = str(dt.date())
        db.contents.insert_one(items)
    print("__&Result&__")
    print("Final Result:",results)
