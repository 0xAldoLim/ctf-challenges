FROM nginx:alpine

COPY ratelimiter.conf ratelimiter.conf

RUN rm /etc/nginx/conf.d/default.conf

RUN cat ratelimiter.conf >> /etc/nginx/nginx.conf
