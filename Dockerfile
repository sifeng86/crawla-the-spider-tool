FROM python:3.8-slim

WORKDIR /work

COPY ./requirements.txt /work/
RUN pip3 install -r requirements.txt

ENV FLASK_APP=login/server.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=3000
ENV PYTHONPATH="${PYTHONPATH}:/work"


CMD bash startup.sh && flask run
