import pytest
import pika
import signal
from unittest.mock import patch, MagicMock, call, ANY
from consumer.consumer import connect_to_rabbitmq, process_order, signal_handler, main

@pytest.fixture
def mock_pika():
    with patch("pika.BlockingConnection") as mock_conn:
        yield mock_conn

def test_connect_to_rabbitmq_success(mock_pika):
    connection = connect_to_rabbitmq()
    assert connection is not None

@patch("pika.BlockingConnection", side_effect=pika.exceptions.AMQPConnectionError)
def test_connect_to_rabbitmq_failure(mock_conn):
    with pytest.raises(RuntimeError, match="Не удалось подключиться к RabbitMQ"):
        connect_to_rabbitmq()

@patch("consumer.consumer.SessionLocal")
def test_process_order_success(mock_session):
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_body = b"NEW_ORDER:123"

    mock_session_instance = mock_session.return_value
    mock_session_instance.execute.return_value = None
    mock_session_instance.commit.return_value = None
    
    process_order(mock_ch, mock_method, None, mock_body)
    
    mock_ch.basic_ack.assert_called_once_with(delivery_tag=mock_method.delivery_tag)
    mock_session_instance.execute.assert_called()
    mock_session_instance.commit.assert_called()

@patch("consumer.consumer.SessionLocal")
def test_process_order_invalid_message(mock_session):
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_body = b"INVALID_MESSAGE"
    
    process_order(mock_ch, mock_method, None, mock_body)
    
    mock_ch.basic_ack.assert_called_once_with(delivery_tag=mock_method.delivery_tag)
    mock_session.assert_not_called()

@patch("consumer.consumer.SessionLocal")
def test_process_order_invalid_order_id(mock_session):
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_body = b"NEW_ORDER:abc"
    
    process_order(mock_ch, mock_method, None, mock_body)
    
    mock_ch.basic_ack.assert_called_once_with(delivery_tag=mock_method.delivery_tag)
    mock_session.assert_not_called()

@patch("consumer.consumer.sys.exit")
def test_signal_handler(mock_exit):
    mock_connection = MagicMock()
    signal_handler(signal.SIGINT, None, mock_connection)
    
    mock_connection.close.assert_called_once()
    mock_exit.assert_called_once_with(0)

@patch("consumer.consumer.connect_to_rabbitmq")
@patch("consumer.consumer.signal.signal")
@patch("pika.BlockingConnection")
@patch("consumer.consumer.sys.exit")
def test_main(mock_exit, mock_pika, mock_signal, mock_connect):
    mock_channel = MagicMock()
    mock_connection = mock_connect.return_value
    mock_connection.channel.return_value = mock_channel
    
    # Создаем счетчик для отслеживания вызовов signal.signal
    signal_call_count = 0
    
    def fake_signal(sig, handler):
        nonlocal signal_call_count
        signal_call_count += 1
        if signal_call_count == 2:  # После второго вызова signal.signal
            handler(sig, None)  # Вызываем обработчик сигнала
    
    mock_signal.side_effect = fake_signal
    
    # Запускаем main()
    main()
    
    # Проверяем, что signal.signal был вызван для SIGINT и SIGTERM
    assert mock_signal.call_count == 2
    mock_signal.assert_any_call(signal.SIGINT, ANY)
    mock_signal.assert_any_call(signal.SIGTERM, ANY)
    
    mock_channel.queue_declare.assert_called_once_with(queue='orders_queue', durable=True)
    mock_channel.basic_qos.assert_called_once_with(prefetch_count=1)
    mock_channel.basic_consume.assert_called_once()
    mock_channel.start_consuming.assert_called_once()
    
    # Проверяем, что sys.exit был вызван
    mock_exit.assert_called_once_with(0)
    

@patch("pika.BlockingConnection", side_effect=pika.exceptions.AMQPConnectionError)
def test_connect_to_rabbitmq_retries(mock_conn):
    with pytest.raises(RuntimeError, match="Не удалось подключиться к RabbitMQ"):
        connect_to_rabbitmq()

@patch("consumer.consumer.SessionLocal")
def test_process_order_db_error(mock_session):
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_body = b"NEW_ORDER:123"

    mock_session_instance = mock_session.return_value
    mock_session_instance.execute.side_effect = Exception("DB Error")
    
    process_order(mock_ch, mock_method, None, mock_body)
    
    mock_ch.basic_ack.assert_called_once_with(delivery_tag=mock_method.delivery_tag)
    mock_session_instance.execute.assert_called()
    mock_session_instance.commit.assert_not_called()
