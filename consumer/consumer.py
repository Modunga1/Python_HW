import os
import time
import signal
import sys
import logging
import pika
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Логирование
logging.basicConfig(level=logging.INFO)

# Настройки подключения к БД и RabbitMQ
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/orders_db")
engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, future=True)

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))

def connect_to_rabbitmq():
    retries = 5
    for i in range(retries):
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT)
            )
            return connection
        except pika.exceptions.AMQPConnectionError:
            if i < retries - 1:
                time.sleep(2)
            else:
                raise RuntimeError("Не удалось подключиться к RabbitMQ")

def process_order(ch, method, properties, body):
    """
    Функция обработки сообщения из очереди RabbitMQ.
    """
    message = body.decode("utf-8")
    if not message.startswith("NEW_ORDER:"):
        logging.warning(f"Получено некорректное сообщение: {message}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    try:
        order_id = int(message.split(":")[1])
    except ValueError:
        logging.warning(f"Невозможно преобразовать order_id в число: {message}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    session = SessionLocal()
    try:
        # Обновим статус заказа
        session.execute(
            text("UPDATE orders SET status=:status WHERE id=:id"),
            {"status": "PROCESSED", "id": order_id}
        )
        session.commit()
        logging.info(f"Заказ {order_id} успешно обработан.")
    except Exception as e:
        logging.error(f"Ошибка при обработке заказа {order_id}: {e}")
    finally:
        session.close()

    ch.basic_ack(delivery_tag=method.delivery_tag)

def signal_handler(sig, frame, connection):
    logging.info("Получен сигнал завершения. Закрываем соединение...")
    connection.close()
    sys.exit(0)

def main():
    connection = connect_to_rabbitmq()
    channel = connection.channel()
    channel.queue_declare(queue='orders_queue', durable=True)
    
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(
        queue='orders_queue',
        on_message_callback=process_order
    )
    
    signal.signal(signal.SIGINT, lambda sig, frame: signal_handler(sig, frame, connection))
    signal.signal(signal.SIGTERM, lambda sig, frame: signal_handler(sig, frame, connection))
    
    logging.info("Консюмер запущен. Ожидаем сообщений...")
    channel.start_consuming()

if __name__ == "__main__":
    main() # pragma: no cover
