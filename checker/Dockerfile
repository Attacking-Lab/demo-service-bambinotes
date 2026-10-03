FROM python:3.12-bookworm
RUN apt-get update && apt-get update -y

RUN python3 -m pip install --break-system-packages git-pass-helper uv

# add checker user
RUN useradd -ms /bin/bash -u 1000 checker

WORKDIR /checker
RUN chown checker /checker

USER checker
RUN --mount=type=cache,target=/home/checker/.cache/uv,uid=1000,gid=1000 \
	--mount=type=bind,source=uv.lock,target=uv.lock \
	--mount=type=bind,source=pyproject.toml,target=pyproject.toml \
	--mount=type=secret,id=checker-pull-token,uid=1000 \
	git-pass -U https://git.atklab.cloud -p "$(cat /run/secrets/checker-pull-token)" -- \
		uv sync --exact --frozen --compile-bytecode --no-install-project

COPY pyproject.toml uv.lock .
COPY ./src .

ENTRYPOINT [ "uv", "run", "--no-sync", "gunicorn", "-c", "gunicorn.conf.py", "checker:app" ]
