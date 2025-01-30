import os
import time
from flask import Flask, request, jsonify
import pika
try:
    from db import init_db, SessionLocal
except ImportError:
    from server.db import init_db, SessionLocal
try:
    from metrics import metrics
except ImportError:
    from server.metrics import metrics
 
from sqlalchemy import text

# Инициализируем БД при старте
init_db()

app = Flask(__name__)
metrics.init_app(app)  # Подключаем метрики

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))

def connect_to_rabbitmq():
    """
    Функция для подключения к RabbitMQ с повторными попытками.
    """
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

@app.route("/orders", methods=["POST"])
def create_order():
    """
    Эндпоинт для создания заказа:
    1) Сохраняем заказ в БД
    2) Отправляем сообщение в RabbitMQ
    """
    data = request.json
    item_name = data.get("item_name")

    if not item_name:  # Проверяем, что поле передано
        return jsonify({"error": "item_name is required"}), 400

    session = SessionLocal()
    try:
        # Сохраним заказ в БД
        result = session.execute(
            text("INSERT INTO orders (item_name, status) VALUES (:name, 'CREATED') RETURNING id"),
            {"name": item_name}
        )
        
        order_id = result.fetchone()[0]
        session.commit()

        # Отправляем сообщение о новом заказе в RabbitMQ
        connection = connect_to_rabbitmq()
        channel = connection.channel()
        channel.queue_declare(queue='orders_queue', durable=True)

        message = f"NEW_ORDER:{order_id}"
        channel.basic_publish(
            exchange='',
            routing_key='orders_queue',
            body=message
        )
        connection.close()

        return jsonify({"order_id": order_id, "status": "CREATED"}), 201

    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 400

    finally:
        session.close()

@app.route("/orders/<int:order_id>", methods=["GET"])
def get_order(order_id):
    """
    Эндпоинт для получения заказа по ID.
    """
    session = SessionLocal()
    try:
        result = session.execute(
            text("SELECT id, item_name, status FROM orders WHERE id = :id"),
            {"id": order_id}
        )
        order = result.fetchone()

        if order is None:
            return jsonify({"error": "Order not found"}), 404

        return jsonify({"order_id": order[0], "item_name": order[1], "status": order[2]}), 200
    finally:
        session.close()

@app.route("/health", methods=["GET"])
def health_check():
    """
    Эндпоинт для проверки работоспособности сервиса.
    """
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    # Запускаем Flask на 8000 порту
    app.run(host="0.0.0.0", port=8000) # pragma: no cover
