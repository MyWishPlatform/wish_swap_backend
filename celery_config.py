import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wish_swap.settings')
import django
django.setup()
from wish_swap.settings import CELERY_TIMEZONE, PUSHING_TRANSFERS_TASK_TIMEOUT_MINUTES

app = Celery('centurion_crowdsale', broker='amqp://rabbit:rabbit@rabbitmq:5672/rabbit', include=['celery_tasks'])
app.config_from_object('django.conf:settings', namespace='CELERY')
app.conf.update(result_expires=3600, enable_utc=True, timezone=CELERY_TIMEZONE)

app.conf.beat_schedule['pushing_transfers_and_payments'] = {
    'task': 'celery_tasks.push_transfers_and_payments',
    'schedule': crontab(minute=f'*/{PUSHING_TRANSFERS_TASK_TIMEOUT_MINUTES}'),
}
