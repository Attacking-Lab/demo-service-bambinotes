FROM python:3.12-bookworm
RUN apt-get update && apt-get update -y 

# add checker user
RUN useradd -ms /bin/bash -u 1000 checker

WORKDIR /checker

COPY requirements.txt .

USER checker
RUN git config --global credential.https://github.com.helper "store --file /tmp/.git-credentials"
RUN echo "https://token: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@github.com" > /tmp/.git-credentials
RUN python3 -m pip install -r requirements.txt

COPY ./src .

ENTRYPOINT [ "/home/checker/.local/bin/gunicorn", "-c", "gunicorn.conf.py", "checker:app" ]