#!/bin/bash
set -e

celery -A celery_task1 worker --loglevel=info --without-gossip --without-mingle &
