# TODO: add docker-compose
# when started from docker-compose, start up cron job based on configuration
# if no cron string is provided, update daily
# read creds from .env file
FROM python:3.13-slim
RUN apt-get update && apt-get upgrade && apt-get install cron -y
RUN pip install setuptools
WORKDIR /root/home
COPY ./pyproject.toml .
COPY src src
RUN /usr/local/bin/python3 -m pip install . 
# RUN rm -rf src
COPY docker/setup_cron.sh .
RUN chmod +x setup_cron.sh

ENTRYPOINT ["./setup_cron.sh"]
# ENTRYPOINT which python3