# Highway Broker Python Client

Complete implementation of the Highway Broker MQTT-lite protocol client in Python with the same API structure as the JavaScript client.

## Features

- **Binary Protocol Implementation**: Full MQTT-lite protocol support with correct network byte order handling
- **Async I/O**: Non-blocking socket operations with threading for read loop
- **Event-based API**: Familiar event emitter pattern from JavaScript
- **Quality of Service**: Support for QoS 0 (At Most Once) and QoS 1 (At Least Once)
- **Connection Management**: Automatic reconnection, keepalive, and graceful shutdown
- **Thread-safe**: Safe for multi-threaded applications

## Installation

```bash
# No external dependencies required - uses only Python stdlib
python3 -m pip install --upgrade pip
```

## Quick Start

### Basic Connection

```python
from highway_client import HighwayClient, QoS

client = HighwayClient({
    'host': 'localhost',
    'port': 1883,
    'client_id': 'my-client'
})

def on_connect():
    print('Connected!')
    client.subscribe('my/topic', QoS.AT_LEAST_ONCE)

def on_message(msg):
    print(f"Received: {msg['data'].decode('utf-8')}")

client.on('connect', on_connect)
client.on('message', on_message)

# Keep running
import time
while True:
    time.sleep(1)
```

## API

### HighwayClient

#### Constructor Options

```python
client = HighwayClient({
    'host': 'localhost',        # Broker host
    'port': 1883,               # Broker port
    'client_id': 'my-client',   # Unique client ID
    'username': '',             # Optional username
    'password': '',             # Optional password
    'keepalive': 60,            # Keepalive interval (seconds)
    'auto_connect': True        # Auto-connect on initialization
})
```

#### Methods

**connect(callback: Optional[Callable]) -> None**
- Connect to broker
- Callback receives (success: bool, error: Optional[Exception])

**disconnect(callback: Optional[Callable]) -> None**
- Gracefully disconnect from broker
- Sends DISCONNECT packet and closes socket

**publish(topic: str, data: str|bytes, qos: int = QoS.AT_MOST_ONCE, callback: Optional[Callable]) -> None**
- Publish message to topic
- QoS: 0 (fire-and-forget) or 1 (acknowledged)
- Callback receives (success: bool)

**subscribe(topic: str, qos: int = QoS.AT_MOST_ONCE, callback: Optional[Callable]) -> None**
- Subscribe to topic (supports wildcards: +, *)
- QoS: 0 (at most once) or 1 (at least once)
- Callback receives (result: dict)

**unsubscribe(topic: str, callback: Optional[Callable]) -> None**
- Unsubscribe from topic
- Callback receives (result: dict)

**on(event: str, handler: Callable) -> None**
- Register event listener
- Events: 'connect', 'message', 'error', 'close', 'suback', 'puback'

**on_message(handler: Callable) -> None**
- Shortcut to register message handler
- Handler receives (topic: str, data: bytes)

**on_error(handler: Callable) -> None**
- Shortcut to register error handler
- Handler receives (error: str)

**is_connected() -> bool**
- Check if currently connected and authenticated

**get_state() -> str**
- Get current connection state

**get_subscriptions() -> list**
- Get list of subscribed topics

#### Events

**'connect'**
- Emitted when successfully connected and authenticated

**'message'**
- Emitted when a message is received
- Data: `{'topic': str, 'data': bytes, 'qos': int, 'packet_id': int}`

**'error'**
- Emitted when an error occurs
- Data: error message (str) or exception

**'close'**
- Emitted when connection is closed

**'suback'**
- Emitted when subscription is acknowledged
- Data: `{'packet_id': int, 'granted_qos_list': list}`

**'puback'**
- Emitted when publish is acknowledged
- Data: `{'packet_id': int}`

### QoS

- `QoS.AT_MOST_ONCE` (0): Fire and forget
- `QoS.AT_LEAST_ONCE` (1): Acknowledged delivery

### BinaryReader / BinaryWriter

For manual packet construction:

```python
from highway_client import BinaryWriter, BinaryReader

# Writing
writer = BinaryWriter()
writer.write_u8(255)
writer.write_u16(1234)
writer.write_string("hello")
data = writer.release()

# Reading
reader = BinaryReader(data)
value = reader.read_u8()
port = reader.read_u16()
text = reader.read_string()
```

## Examples

### Producer

```python
from highway_client import HighwayClient, QoS
import json

client = HighwayClient({'host': 'localhost', 'port': 1883})

def on_connect():
    client.publish('sensor/1/temp', json.dumps({'temp': 25.5}), QoS.AT_LEAST_ONCE)

client.on('connect', on_connect)
```

See `examples/producer.py` for full example.

### Consumer

```python
from highway_client import HighwayClient, QoS

client = HighwayClient({'host': 'localhost', 'port': 1883})

def on_connect():
    client.subscribe('sensor/+/temp', QoS.AT_LEAST_ONCE)

def on_message(msg):
    print(f"Received from {msg['topic']}: {msg['data']}")

client.on('connect', on_connect)
client.on('message', on_message)
```

See `examples/consumer.py` for full example.

### Monitor

See `examples/monitor.py` for a monitoring example that collects statistics.

## Running Examples

```bash
# Terminal 1: Start broker
./broker

# Terminal 2: Start consumer
python3 examples/consumer.py

# Terminal 3: Start producer
python3 examples/producer.py

# Terminal 4: Start monitor
python3 examples/monitor.py
```

## Compatibility

- Python 3.6+
- No external dependencies (uses only stdlib)
- Cross-platform (Linux, macOS, Windows)

## Differences from JavaScript Client

The Python client has the same API interface but with Python conventions:

| Feature | JavaScript | Python |
|---------|-----------|--------|
| Constructor | `new HighwayClient()` | `HighwayClient()` |
| Config keys | camelCase | snake_case |
| Event emitter | `EventEmitter` pattern | Custom event system |
| Callbacks | Promise-friendly | Regular callbacks |
| Bytes | `Buffer` | `bytes` |
| Threading | Event loop | Thread-based |

## Protocol Details

The client implements the MQTT-lite protocol with:
- 4-byte fixed header (type, flags, remaining length)
- Variable-length payload encoding
- Network byte order (big-endian) for multi-byte fields
- Packet types: CONNECT, CONNACK, PUBLISH, PUBACK, SUBSCRIBE, SUBACK, DISCONNECT, etc.

## Thread Safety

The client is thread-safe for:
- Publishing messages from multiple threads
- Calling disconnect while handling events
- Multiple event handlers

The read loop runs in a background daemon thread.

## Error Handling

```python
def on_error(error_msg):
    print(f"Error: {error_msg}")

client.on_error(on_error)

# Or use try-catch with callbacks
try:
    client.connect(lambda success, err: 
        print(f"Connected: {success}") if success else print(f"Error: {err}"))
except Exception as e:
    print(f"Connection failed: {e}")
```

## License

Same as Highway Broker project
