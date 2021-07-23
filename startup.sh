#!/bin/bash
#flask run;
celery -A login.celery_task1 worker --loglevel=info &
