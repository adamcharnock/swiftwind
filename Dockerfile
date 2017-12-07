FROM python:3.6-alpine

WORKDIR /swiftwind

### Setup postgres ###

RUN \
    apk add -U \
        ca-certificates \
        postgresql-dev gcc python3-dev musl-dev && \
    update-ca-certificates && \
    rm -rf /var/cache/apk/*

### Install Swiftwind dependencies ###

ADD ["requirements.txt", "manage.py", "setup.py", "VERSION", "fixtures", "/swiftwind/"]

# Dependencies will change fairly often, so do this
# separately to the above
RUN \
    apk add -U git && \
    pip install -r requirements.txt && \
    apk del --purge git && \
    rm -rf /var/cache/apk/*

RUN pip install -r requirements.txt

### Add Swiftwind code ###

ADD example_project /swiftwind/example_project
ADD swiftwind /swiftwind/swiftwind

### Collect the static files ready to be servced ###

RUN SECRET_KEY=none ./manage.py collectstatic --no-input

### Using gunicorn to serve ###

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "example_project.wsgi"]

