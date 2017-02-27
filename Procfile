web: gunicorn example_project.wsgi --log-file -
worker: celery -A example_project worker --beat -l info -c 1
