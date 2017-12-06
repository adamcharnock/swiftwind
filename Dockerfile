FROM python:3.6-alpine

RUN apk update && apk add \
        ca-certificates \
        postgresql-dev gcc python3-dev musl-dev && \
    update-ca-certificates && \
    rm -rf /var/cache/apk/*

WORKDIR /swiftwind

ADD ["requirements.txt", "manage.py", "setup.py", "VERSION", "fixtures", "/swiftwind/"]

RUN pip install .

ADD example_project /swiftwind/example_project
ADD swiftwind /swiftwind/swiftwind

RUN SECRET_KEY=none ./manage.py collectstatic --no-input

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "example_project.wsgi"]

