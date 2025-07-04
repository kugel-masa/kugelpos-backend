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

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]