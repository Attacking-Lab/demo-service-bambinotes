FROM ubuntu:latest
RUN apt-get update && apt-get upgrade -y

RUN apt-get install -y xinetd
RUN useradd author

COPY xinetd.conf /etc/xinetd.conf

WORKDIR /service
COPY ./bambi-notes bambi-notes

RUN mkdir /service/data

RUN service xinetd reload 

RUN touch /var/log/xinetd.log
ENTRYPOINT xinetd && tail -f /var/log/xinetd.log

