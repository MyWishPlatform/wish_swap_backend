import pika
import os
import json


def get_connection():
    return pika.BlockingConnection(pika.ConnectionParameters(
        'rabbitmq',
        5672,
        os.getenv('RABBITMQ_DEFAULT_VHOST', 'wish_swap'),
        pika.PlainCredentials(os.getenv('RABBITMQ_DEFAULT_USER', 'wish_swap'),
                              os.getenv('RABBITMQ_DEFAULT_PASS', 'wish_swap')),
    ))


def get_channel(connection, queue):
    channel = connection.channel()
    channel.queue_declare(
        queue=queue,
        durable=True,
        auto_delete=False,
        exclusive=False
    )
    return channel


def publish_message(queue, type, message):
    connection = get_connection()
    channel = get_channel(connection, queue)
    channel.basic_publish(
        exchange='',
        routing_key=queue,
        body=json.dumps(message),
        properties=pika.BasicProperties(type=type),
    )
    connection.close()


def delete_queue(queue):
    connection = get_connection()
    channel = get_channel(connection, queue)
    channel.queue_delete(queue=queue)
    connection.close()
