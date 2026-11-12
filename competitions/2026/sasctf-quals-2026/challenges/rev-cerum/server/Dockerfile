FROM ubuntu:22.04

RUN apt-get update && apt-get upgrade -y

RUN apt-get install python3 python3-pip -y

WORKDIR /opt/app

COPY . /opt/app

RUN pip3 install -r /opt/app/requirements.txt

EXPOSE 13317

CMD [ "python3", "/opt/app/license_server.py", "--config", "/opt/app/data/config.json" ]
