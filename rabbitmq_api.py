import pika
import os
import json


def send_rabbitmq_message(queue, type, message):
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        'rabbitmq',
        5672,
        os.getenv('RABBITMQ_DEFAULT_VHOST', 'wish_swap'),
        pika.PlainCredentials(os.getenv('RABBITMQ_DEFAULT_USER', 'wish_swap'),
                              os.getenv('RABBITMQ_DEFAULT_PASS', 'wish_swap')),
    ))
    channel = connection.channel()
    channel.queue_declare(
        queue=queue,
        durable=True,
        auto_delete=False,
        exclusive=False
    )
    channel.basic_publish(
        exchange='',
        routing_key=queue,
        body=json.dumps(message),
        properties=pika.BasicProperties(type=type),
    )
    connection.close()
