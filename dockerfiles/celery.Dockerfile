FROM python:3.7.2

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

COPY . /app
CMD ["celery", "-A", "celery_config", "worker", "-B", "--loglevel=info"]