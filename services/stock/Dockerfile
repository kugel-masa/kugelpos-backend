FROM python:3.12.11

RUN apt-get update && apt-get install -y --no-install-recommends locales \
    && echo "ja_JP.UTF-8 UTF-8" > /etc/locale.gen \
    && locale-gen ja_JP.UTF-8 \
    && update-locale LANG=ja_JP.UTF-8 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV LC_ALL=ja_JP.UTF-8
ENV LANG=ja_JP.UTF-8
ENV LANGUAGE=ja_JP.UTF-8
ENV PIPENV_VENV_IN_PROJECT=0
ENV PIPENV_IGNORE_VIRTUALENVS=1

WORKDIR /app

COPY . /app

RUN pip install -U pip && pip install pipenv

RUN pipenv install --deploy --ignore-pipfile --system

EXPOSE 8000

# Stock service runs as a SINGLE uvicorn worker by design (issue #105):
# its WebSocket alert broadcast (services/stock/app/websocket/
# connection_manager.py) keeps connection state in-process. With multiple
# workers, a stock-update HTTP request handled on worker A only sees its
# local connection set and silently fails to deliver to clients
# connected on workers B/C/D. Until a cross-worker broadcast channel
# (Redis pub/sub or a dedicated ws process) is introduced, do not raise
# this past 1. See connection_manager.py module docstring.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]