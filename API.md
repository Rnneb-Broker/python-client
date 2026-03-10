# Highway Broker Python Client - API Reference

## Classes

### HighwayClient

Main client class for connecting to and communicating with the Highway Broker.

#### Constructor

```python
client = HighwayClient(config: dict = None)
```

**Parameters:**
- `config` (dict): Configuration dictionary with keys:
  - `host` (str): Broker hostname or IP address (default: 'localhost')
  - `port` (int): Broker port (default: 1883)
  - `client_id` (str): Unique client identifier (default: auto-generated)
  - `username` (str): Username for authentication (default: '')
  - `password` (str): Password for authentication (default: '')
  - `keepalive` (int): Keepalive interval in seconds (default: 60)
  - `auto_connect` (bool): Automatically connect on init (default: True)

#### Connection Methods

**connect(callback: Callable = None) -> None**

Establish connection to broker.

```python
def on_connect_result(success, error):
    if success:
        print("Connected!")
    else:
        print(f"Connection failed: {error}")

client.connect(on_connect_result)
```

**disconnect(callback: Callable = None) -> None**

Close connection to broker.

```python
def on_disconnect():
    print("Disconnected")

client.disconnect(on_disconnect)
```

#### Publishing Methods

**publish(topic: str, data: str|bytes, qos: int = 0, callback: Callable = None) -> None**

Publish a message to a topic.

```python
# Publish as string
client.publish('sensor/temperature', '25.5')

# Publish as JSON
import json
client.publish('sensor/data', json.dumps({'temp': 25.5, 'humidity': 60}))

# Publish with callback
def on_published(success):
    print(f"Published: {success}")

client.publish('topic', 'message', QoS.AT_LEAST_ONCE, on_published)
```

**Parameters:**
- `topic` (str): Topic to publish to
- `data` (str|bytes): Message payload
- `qos` (int): Quality of Service (0 or 1)
- `callback` (Callable): Function called with success status

#### Subscription Methods

**subscribe(topic: str, qos: int = 0, callback: Callable = None) -> None**

Subscribe to a topic to receive messages.

```python
def on_subscribed(result):
    print(f"Subscribed: {result['granted_qos_list']}")

# Subscribe with wildcards
client.subscribe('sensor/+/temperature', QoS.AT_LEAST_ONCE, on_subscribed)
```

**Parameters:**
- `topic` (str): Topic pattern (supports + for single-level wildcard)
- `qos` (int): Desired Quality of Service (0 or 1)
- `callback` (Callable): Function called with subscription result

**unsubscribe(topic: str, callback: Callable = None) -> None**

Unsubscribe from a topic.

```python
def on_unsubscribed(result):
    print(f"Unsubscribed: {result}")

client.unsubscribe('sensor/+/temperature', on_unsubscribed)
```

#### Event Handling

**on(event: str, handler: Callable) -> None**

Register event listener.

```python
client.on('connect', lambda: print("Connected!"))
client.on('message', lambda msg: print(f"Message: {msg}"))
client.on('error', lambda err: print(f"Error: {err}"))
```

**Supported Events:**
- `'connect'`: Client connected and authenticated
- `'message'`: Message received (data: dict with topic, data, qos, packet_id)
- `'error'`: Error occurred (data: Exception)
- `'close'`: Connection closed
- `'suback'`: Subscription acknowledged (data: dict with packet_id, granted_qos_list)
- `'puback'`: Publish acknowledged (data: dict with packet_id)

**on_message(handler: Callable) -> None**

Convenience method to register message handler.

```python
def handle_message(msg):
    print(f"Topic: {msg['topic']}")
    print(f"Data: {msg['data']}")
    print(f"QoS: {msg['qos']}")

client.on_message(handle_message)
```

**on_error(handler: Callable) -> None**

Convenience method to register error handler.

```python
def handle_error(error_msg):
    print(f"Error: {error_msg}")

client.on_error(handle_error)
```

#### State Methods

**is_connected() -> bool**

Check if client is currently connected and authenticated.

```python
if client.is_connected():
    client.publish('status', 'online')
```

**get_state() -> str**

Get current connection state.

```python
state = client.get_state()
# Returns: 'DISCONNECTED', 'CONNECTING', 'CONNECTED', 'AUTHENTICATED', 'DISCONNECTING'
```

**get_subscriptions() -> list**

Get list of currently subscribed topics.

```python
topics = client.get_subscriptions()
print(f"Subscribed to: {topics}")
```

---

### BinaryWriter

Helper class for manual binary packet construction.

```python
from highway_client import BinaryWriter

writer = BinaryWriter()
writer.write_u8(255)           # Write unsigned 8-bit integer
writer.write_u16(1234)          # Write unsigned 16-bit integer (big-endian)
writer.write_u32(123456)        # Write unsigned 32-bit integer (big-endian)
writer.write_u64(12345678901234) # Write unsigned 64-bit integer (big-endian)
writer.write_string("hello")    # Write UTF-8 string with 2-byte length prefix
writer.write_bytes(b"data")     # Write raw bytes
data = writer.release()         # Get resulting bytes
```

#### Methods

- `write_u8(value: int) -> BinaryWriter`
- `write_u16(value: int) -> BinaryWriter`
- `write_u32(value: int) -> BinaryWriter`
- `write_u64(value: int) -> BinaryWriter`
- `write_string(value: str) -> BinaryWriter`
- `write_bytes(data: bytes) -> BinaryWriter`
- `release() -> bytes`

---

### BinaryReader

Helper class for manual binary packet parsing.

```python
from highway_client import BinaryReader

reader = BinaryReader(data)
value = reader.read_u8()        # Read unsigned 8-bit integer
port = reader.read_u16()         # Read unsigned 16-bit integer (big-endian)
count = reader.read_u32()        # Read unsigned 32-bit integer (big-endian)
timestamp = reader.read_u64()    # Read unsigned 64-bit integer (big-endian)
text = reader.read_string()      # Read UTF-8 string with 2-byte length prefix
raw = reader.read_bytes(10)      # Read specific number of bytes
remaining = reader.read_remaining() # Read all remaining bytes
```

#### Methods

- `read_u8() -> int`
- `read_u16() -> int`
- `read_u32() -> int`
- `read_u64() -> int`
- `read_string() -> str`
- `read_bytes(length: int) -> bytes`
- `read_remaining() -> bytes`
- `empty() -> bool`

---

### Enums

**PacketType**

```python
PacketType.CONNECT = 0x10
PacketType.CONNACK = 0x20
PacketType.PUBLISH = 0x30
PacketType.PUBACK = 0x40
PacketType.SUBSCRIBE = 0x80
PacketType.SUBACK = 0x90
PacketType.UNSUBSCRIBE = 0xA0
PacketType.UNSUBACK = 0xB0
PacketType.PINGREQ = 0xC0
PacketType.PINGRESP = 0xD0
PacketType.DISCONNECT = 0xE0
```

**QoS**

```python
QoS.AT_MOST_ONCE = 0    # Fire and forget
QoS.AT_LEAST_ONCE = 1   # Acknowledged delivery
QoS.EXACTLY_ONCE = 2    # Guaranteed single (not implemented)
```

**ConnectResult**

```python
ConnectResult.ACCEPTED = 0x00
ConnectResult.UNACCEPTABLE_VERSION = 0x01
ConnectResult.IDENTIFIER_REJECTED = 0x02
ConnectResult.SERVER_UNAVAILABLE = 0x03
ConnectResult.BAD_CREDENTIALS = 0x04
ConnectResult.NOT_AUTHORIZED = 0x05
```

**State**

```python
State.DISCONNECTED = 'DISCONNECTED'
State.CONNECTING = 'CONNECTING'
State.CONNECTED = 'CONNECTED'
State.AUTHENTICATED = 'AUTHENTICATED'
State.DISCONNECTING = 'DISCONNECTING'
```

---

## Usage Examples

### Basic Subscribe and Receive

```python
from highway_client import HighwayClient, QoS

client = HighwayClient({
    'host': 'localhost',
    'port': 1883,
    'client_id': 'my-subscriber'
})

def on_connect():
    client.subscribe('news/+/updates', QoS.AT_LEAST_ONCE)
    print("Subscribed to news/+/updates")

def on_message(msg):
    print(f"News update from {msg['topic']}: {msg['data'].decode('utf-8')}")

client.on('connect', on_connect)
client.on('message', on_message)

# Run forever
import time
while True:
    time.sleep(1)
```

### Basic Publish

```python
from highway_client import HighwayClient, QoS
import json

client = HighwayClient({
    'host': 'localhost',
    'port': 1883,
    'client_id': 'my-publisher'
})

def on_connect():
    data = json.dumps({'temperature': 25.5, 'humidity': 60})
    client.publish('weather/sensor1/data', data, QoS.AT_LEAST_ONCE)
    client.disconnect()

client.on('connect', on_connect)
```

### Error Handling

```python
from highway_client import HighwayClient

client = HighwayClient({'host': 'localhost', 'port': 1883})

def on_error(err):
    print(f"Client error: {err}")

def on_close():
    print("Connection closed, will retry...")

client.on('error', on_error)
client.on('close', on_close)
```

---

## Notes

- All callbacks are called synchronously from the read thread
- The client is thread-safe for publishing from multiple threads
- Strings are encoded/decoded as UTF-8
- Network byte order (big-endian) is used for multi-byte fields
- The read loop runs as a daemon thread
