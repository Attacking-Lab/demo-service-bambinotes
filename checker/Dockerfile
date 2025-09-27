FROM python:3.12-bookworm
RUN apt-get update && apt-get update -y 

RUN python3 -m pip install --break-system-packages git-pass-helper

# add checker user
RUN useradd -ms /bin/bash -u 1000 checker

WORKDIR /checker

COPY requirements.txt .

USER checker

RUN --mount=type=secret,id=github-pat,env=GITHUB_PAT \
	git-pass -p "${GITHUB_PAT:?GITHUB PAT not set}" -- \
		python3 -m pip install -r requirements.txt

COPY ./src .

ENTRYPOINT [ "/home/checker/.local/bin/gunicorn", "-c", "gunicorn.conf.py", "checker:app" ]
