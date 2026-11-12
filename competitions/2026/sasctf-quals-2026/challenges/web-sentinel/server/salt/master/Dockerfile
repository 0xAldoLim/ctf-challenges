FROM alpine:3.22

RUN apk add --no-cache salt-master netcat-openbsd

ENV PYTHONWARNINGS=ignore::DeprecationWarning

COPY salt/master/master.conf /etc/salt/master
COPY salt/master/top.sls /srv/salt/top.sls
COPY salt/master/pillar-top.sls /srv/pillar/top.sls
COPY salt/master/states /srv/salt/states
COPY salt/master/_runners /srv/salt/_runners
COPY salt/master/reactor /srv/salt/reactor
COPY salt/master/pillars/common.sls.j2 /srv/pillar/common.sls.j2
COPY salt/master/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

EXPOSE 4505 4506

ENTRYPOINT ["/entrypoint.sh"]
