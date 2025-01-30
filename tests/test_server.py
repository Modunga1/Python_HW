import pytest
import json
from unittest.mock import patch, MagicMock
from server.main import app, connect_to_rabbitmq
import pika

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_create_order_success(client):
    response = client.post('/orders', json={'item_name': 'Test Item'})
    assert response.status_code == 201
    data = response.get_json()
    assert 'order_id' in data
    assert data['status'] == 'CREATED'

def test_create_order_failure(client):
    response = client.post('/orders', json={})
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data

def test_health_check(client):
    response = client.get('/health')
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}

def test_create_multiple_orders(client):
    order_names = ['Order 1', 'Order 2', 'Order 3']
    
    for name in order_names:
        response = client.post('/orders', json={'item_name': name})
        assert response.status_code == 201
        data = response.get_json()
        assert 'order_id' in data
        assert data['status'] == 'CREATED'

def test_orders_in_db(client):
    response = client.post('/orders', json={'item_name': 'Test Item'})
    assert response.status_code == 201
    order_id = response.get_json()['order_id']
    
    order_response = client.get(f'/orders/{order_id}')
    assert order_response.status_code == 200
    order_data = order_response.get_json()
    assert order_data['order_id'] == order_id

def test_get_order_not_found(client):
    response = client.get('/orders/99999')  # Несуществующий ID
    assert response.status_code == 404
    assert response.get_json() == {"error": "Order not found"}

def test_create_order_db_failure(client):
    with patch('server.main.SessionLocal') as mock_session:
        mock_session.return_value.execute.side_effect = Exception("DB error")
        response = client.post('/orders', json={'item_name': 'Test Item'})
        assert response.status_code == 400
        assert 'error' in response.get_json()

def test_connect_to_rabbitmq_success():
    with patch('pika.BlockingConnection') as mock_connection:
        mock_connection.return_value = MagicMock()
        connection = connect_to_rabbitmq()
        assert connection is not None

def test_connect_to_rabbitmq_failure():
    with patch('pika.BlockingConnection', side_effect=pika.exceptions.AMQPConnectionError("Connection error")):
        with pytest.raises(RuntimeError, match="Не удалось подключиться к RabbitMQ"):
            connect_to_rabbitmq()
