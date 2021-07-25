#!/bin/bash
#flask run;
celery -A celery_task1 worker --loglevel=info &
