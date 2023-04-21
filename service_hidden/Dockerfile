FROM ubuntu:latest
RUN apt-get update && apt-get upgrade -y

RUN apt-get install -y build-essential

WORKDIR /service
COPY . .

RUN gcc bambi-notes.c -o bambi-notes

ENTRYPOINT tail -f /dev/null
