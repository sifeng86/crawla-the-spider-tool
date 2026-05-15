import sys
from login.lib.mongo import mongoHelper
import smtplib
from email.mime.text import MIMEText
from login.lib.runtime_config import get_int_setting, get_secret_setting, get_setting

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


mail_host = get_setting('CRAWLA_MAIL_HOST', config_path='mail_host')
mail_port = get_int_setting('CRAWLA_MAIL_PORT', config_path='mail_port', default=465)
mail_sender = get_setting('CRAWLA_MAIL_SENDER', config_path='mail_sender')
mail_user = get_setting('CRAWLA_MAIL_USER', config_path='mail_user')
mail_password = get_secret_setting('CRAWLA_MAIL_PASSWORD', config_path='mail_pw', decrypt_legacy=True)
host_url = get_setting('CRAWLA_HOST_URL', config_path='host_url')

if not mail_host:
    print("Email not configured (mail_host missing). Set CRAWLA_MAIL_HOST or keep the legacy config.json fallback.")
    sys.exit(0)

try:
    with open("login/templates/email1.html", encoding="utf-8") as htmlfile:
        ori_template = htmlfile.read()
except FileNotFoundError:
    print("Email template not found.")
    sys.exit(0)


for item in records:
    if not host_url:
        print("Email not configured (host_url missing). Set CRAWLA_HOST_URL or keep the legacy config.json fallback.")
        sys.exit(0)
    if not all((mail_sender, mail_user, mail_password)):
        print("Email not configured (sender, user, or password missing). Set CRAWLA_MAIL_* env vars or the legacy config.json fallback.")
        sys.exit(0)

    dw_url = 'https://' + host_url + '/dw_csv/' + item['task_id']
    template = ori_template
    template = template.replace("{{name}}", item['noti_email'].split('@')[0])
    template = template.replace("{{download_url}}", dw_url)
    sender = mail_sender
    receivers = item['noti_email']
    try:
        with smtplib.SMTP_SSL(host=mail_host, port=mail_port) as smtpObj:
            smtpObj.login(
                user=mail_user, password=mail_password)
            template = MIMEText(template, 'html')
            template['Subject'] = 'New Task is added.'
            template['From'] = sender
            template['To'] = receivers
            smtpObj.sendmail(sender, receivers, template.as_string())
            print("Successfully sent email")

    except Exception as e:
        print(e)

