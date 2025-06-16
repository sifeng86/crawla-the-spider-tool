# Crawla - the spider tool
All you might want to ask:

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/sifeng86/crawla-the-spider-tool)

This tool is suitable for developer who need to develop a lot of spiders.  

Web interface to create and manage spiders easily for developer.  

No hassle, create a spider in minutes.  

Demo: https://crawla.cachigo.com
## Description

A web based spider tooling which provide user a simple entry point to design a spider and it has a live preview section to estimate the result and the result also accumulated in a csv file for further analyzing. 

## Getting Started

### Prerequisite
#### -- Required
* Docker
* Docker-compose
* Auth0 account (https://auth0.com/)
* MongoDB (see optional for alternative)
* Mail Server (see optional for alternative)
#### -- Optional
* MongoDB Atlas account (https://www.mongodb.com/cloud/atlas)
* Sendgrid (https://sendgrid.com/)


### Installation
#### -- Configuration
* create ***.env*** file (using .env_example)
```
#path: login/

# Application configuration
APP_PORT=3000
APP_ENV=development
SECRET_KEY=aaaaaaaaaa

# AUTH0 configuration
APP_PORT=3000
APP_ENV=development
AUTH0_CLIENT_ID=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AUTH0_DOMAIN=abcdefg-999.us.auth0.com
AUTH0_CLIENT_SECRET=
AUTH0_CALLBACK_URL=http://localhost:3000/callback
AUTH0_LOGOUT_REDIRECT_URL=http://localhost:3000/
AUTH0_AUDIENCE=


# Google API key configuration
GOOGLE_API_KEY=AAAA


#explanation:
1. Please refer the tutorial to get the needed info:
https://auth0.com/docs/quickstart/webapp/python#configure-auth0
2. "SECRET_KEY" is a key that flask section needed. You can input any string.
3. This project is using google-gemini as LLM example.

```

* create ***config.json*** file (using config_example.json)
```
#path: login/setting/

{
    "host_url": "www.example.com",
    "mongo_mode": "atlas or local (either one)",
    "atlas_host": "cluster9999.abcdefg.mongodb.net",
    "atlas_db": "example",
    "atlas_user": "hehe",
    "atlas_pw": "gABCDE(must use encryption)",
    "redis_host_port": "redislabs.com:9999 or local (either one)",
    "redis_user": "hehe",
    "redis_pw": "gAA(must use encryption)",
    "mail_host": "smtp.sendgrid.net",
    "mail_port": 465,
    "mail_sender": "me@example.com",
    "mail_user":"apikey",
    "mail_pw": "gAA(must use encryption)"
    "llm": {
        "gemini": {
            "api_key": "gAA",
            "model": "gemini-2.5-flash-preview-04-17",
            "temperature": 0.7
        },
        "openapi": {
            "api_key": "",
            "model": "",
            "temperature": 0.7
        }
    }
}

#explanation:
1. "host_url" is your site url
2. (mongo, redis) you can skip user/pw if using local mode.
3. "must be encryption" mean need to use encryption tool
4. encryption tool usage will be covered later on.
5. llm gemini is an option if you want to use LLM feature.
6. openapi not yet support, but it's in the future plan.

```
#### -- First Run
```
docker-compose build
```
#### -- Encryption tool
1.Run docker.
```
docker run -it --rm -v ${PWD}:/work --name crawla crawla_web:latest bash
```
2.Generate key(first time only):
```
python key_generator.py
```
- rename the key to **"secret.key"** inside **<key>** folder

3.Encrypt token & password.
```
python encrypt_token.py
```
```
Enter your token: (type something here)
```
- return:
```
'gAAAAABgGSLAtS13rMuiKa6CkBP-ThisisexampleBd8zfEH2M2tr5Tgrq4N9whg=='
Token is encrypted.
```
- copy the generated string only.

4.Input the related information in **"setting/config.json"** file.
- "atlas_pw", "redis_pw" and "mail_pw" must be encrypted.

## Running the tool
* Start the docker 
  * add  **-d**  to run in the background
```
docker-compose up
```
* Stop the docker 
```
docker-compose down
```


### Run the job periodic using crontab

Run tasks at custom scheduled time. \
*(Currently not support LLM method.)*
```
0 1 * * * docker exec -t crawla_web python ./main.py --all >> /log/xx.log 2>&1
```
* **--all** (all tasks)
* **--py_requests** Request tasks only)
* **--py_selenium** (Selenium tasks only)
* **--user userid** (Certain user only)
* **--task taskid** (Certain task only)

Export the results to csv file
```
0 1 * * * docker exec -t crawla_web python ./export_csv.py --task taskid >> /log/xx.log 2>&1
```
* **--task taskid** (Certain task only)
* **--all** (all tasks)

Send the result by mail for specific task only
```
0 1 * * * docker exec -t crawla_web python ./sendmail.py --task taskid >> /log/xx.log 2>&1
```
* **--task taskid** (Certain task only)

*PS: You can get the taskid in the download link of the csv file*

## More
#### Advance
You can limit the redis usage if your server has resources limitation.
* log in to the running redis contatiner.
```
docker exec -it crawla_redis sh
```

```
redis-cli

127.0.0.1:6379> config get maxmemory
1) "maxmemory"
2) "0"
127.0.0.1:6379> config set maxmemory 100MB
OK
127.0.0.1:6379> config get maxmemory
1) "maxmemory"
2) "104857600"
127.0.0.1:6379> config set maxmemory-policy volatile-lru
OK
127.0.0.1:6379> config get maxmemory-policy
1) "maxmemory-policy"
2) "volatile-lru"
127.0.0.1:6379> config set maxclients 1000
OK

```

## Authors

Alan Gan (https://www.linkedin.com/in/iamalan)

## Version History

* 1.1
    * Add LLM feature
* 1.0 Beta
    * Initial Release

## License

This project is licensed under the Apache License 2.0 - see the LICENSE.txt file for details

## Acknowledgments

Inspiration, code snippets, etc.
* [Auth0 Python SDK](https://github.com/auth0-samples/auth0-python-web-app/)
* [Flask](https://flask.palletsprojects.com/)
* [Celery](https://docs.celeryproject.org)
* more...