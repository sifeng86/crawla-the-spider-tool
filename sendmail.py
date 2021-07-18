import sys, json
from login.lib.mongo import mongoHelper
import smtplib
from email.mime.text import MIMEText
from login.lib.cryptograpy import Crypto
with open("login/setting/config.json") as json_file:
    config = json.load(json_file)

crypto = Crypto()

# Connection to mongodb
db = mongoHelper.mongo_conn()


########################
# check the cmd commands
# getting data from db
########################
if len(sys.argv) == 1:
    exit('parameter is missing')


elif sys.argv[1] == '--task':
    # python sendmail.py --task taskid
    if len(sys.argv) == 3:
        task_id = sys.argv[2]
        results = db.urls.find({"task_id": task_id}).limit(1)
        records = [i for i in results]
    else:
        exit('taskid parameter is missing')
else:
    exit('bad command')


with open("login/templates/email1.html", encoding="utf-8") as htmlfile:
    ori_template = htmlfile.read()


for item in records:
    dw_url = 'https://' + config['host_url'] + '/dw_csv/' + item['task_id']
    template = ori_template
    template = template.replace("{{name}}", item['noti_email'].split('@')[0])
    template = template.replace("{{download_url}}", dw_url)
    sender = config['mail_sender']
    receivers = item['noti_email']
    mail_pw = bytes(config["mail_pw"], encoding='utf-8')
    mail_pw = crypto.decrypt_message(mail_pw)
    try:
        with smtplib.SMTP_SSL(host=config['mail_host'], port=config['mail_port']) as smtpObj:
            smtpObj.login(
                user=config["mail_user"], password=mail_pw)
            template = MIMEText(template, 'html')
            template['Subject'] = 'New Task is added.'
            template['From'] = sender
            template['To'] = receivers
            smtpObj.sendmail(sender, receivers, template.as_string())
            print("Successfully sent email")

    except Exception as e:
        print(e)

