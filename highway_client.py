#!/usr/bin/env python3
"""
Highway Broker Python Client
Implements MQTT-lite protocol for message broker communication
"""

import socket
import struct
import threading
import time
from enum import IntEnum
from collections import defaultdict
from typing import Callable, Optional, Any

# Packet Types
class PacketType(IntEnum):
    CONNECT = 0x10
    CONNACK = 0x20
    PUBLISH = 0x30
    PUBACK = 0x40
    SUBSCRIBE = 0x80
    SUBACK = 0x90
    UNSUBSCRIBE = 0xA0
    UNSUBACK = 0xB0
    PINGREQ = 0xC0
    PINGRESP = 0xD0
    DISCONNECT = 0xE0
    # Offset-based access (v1.1)
    FETCH_ONE = 0x50
    FETCH_RESPONSE = 0x51
    SUBSCRIBE_FROM_OFFSET = 0x81
    OFFSET_NOT_FOUND = 0x52

# Subscription modes (v1.1)
class SubscriptionMode(IntEnum):
    PUSH_LIVE = 0
    CATCHUP_THEN_PUSH = 1

# Quality of Service
class QoS(IntEnum):
    AT_MOST_ONCE = 0
    AT_LEAST_ONCE = 1
    EXACTLY_ONCE = 2

# Connection states
class State:
    DISCONNECTED = 'DISCONNECTED'
    CONNECTING = 'CONNECTING'
    CONNECTED = 'CONNECTED'
    AUTHENTICATED = 'AUTHENTICATED'
    DISCONNECTING = 'DISCONNECTING'

# Connection result codes
class ConnectResult(IntEnum):
    ACCEPTED = 0x00
    UNACCEPTABLE_VERSION = 0x01
    IDENTIFIER_REJECTED = 0x02
    SERVER_UNAVAILABLE = 0x03
    BAD_CREDENTIALS = 0x04
    NOT_AUTHORIZED = 0x05

class BinaryWriter:
    """Binary packet writer for serialization"""
    def __init__(self):
        self.buffer = bytearray()

    def write_u8(self, value: int) -> 'BinaryWriter':
        self.buffer.append(value & 0xFF)
        return self

    def write_u16(self, value: int) -> 'BinaryWriter':
        self.buffer.extend(struct.pack('>H', value))
        return self

    def write_u32(self, value: int) -> 'BinaryWriter':
        self.buffer.extend(struct.pack('>I', value))
        return self

    def write_u64(self, value: int) -> 'BinaryWriter':
        self.buffer.extend(struct.pack('>Q', value))
        return self

    def write_string(self, value: str) -> 'BinaryWriter':
        encoded = value.encode('utf-8')
        self.write_u16(len(encoded))
        self.buffer.extend(encoded)
        return self

    def write_bytes(self, data: bytes) -> 'BinaryWriter':
        self.buffer.extend(data)
        return self

    def release(self) -> bytes:
        return bytes(self.buffer)

class BinaryReader:
    """Binary packet reader for deserialization"""
    def __init__(self, buffer: bytes):
        self.buffer = buffer
        self.pos = 0

    def read_u8(self) -> int:
        value = self.buffer[self.pos]
        self.pos += 1
        return value

    def read_u16(self) -> int:
        value = struct.unpack('>H', self.buffer[self.pos:self.pos + 2])[0]
        self.pos += 2
        return value

    def read_u32(self) -> int:
        value = struct.unpack('>I', self.buffer[self.pos:self.pos + 4])[0]
        self.pos += 4
        return value

    def read_u64(self) -> int:
        value = struct.unpack('>Q', self.buffer[self.pos:self.pos + 8])[0]
        self.pos += 8
        return value

    def read_string(self) -> str:
        length = self.read_u16()
        value = self.buffer[self.pos:self.pos + length].decode('utf-8')
        self.pos += length
        return value

    def read_bytes(self, length: int) -> bytes:
        value = self.buffer[self.pos:self.pos + length]
        self.pos += length
        return value

    def read_remaining(self) -> bytes:
        value = self.buffer[self.pos:]
        self.pos = len(self.buffer)
        return value

    def empty(self) -> bool:
        return self.pos >= len(self.buffer)

def create_packet_header(packet_type: int, flags: int, payload_len: int) -> bytes:
    """Create a 4-byte packet header"""
    header = bytearray(4)
    header[0] = packet_type
    header[1] = flags
    header[2:4] = struct.pack('>H', payload_len)
    return bytes(header)

class HighwayClient:
    """Main Highway Broker Client"""
    
    def __init__(self, config: Optional[dict] = None):
        if config is None:
            config = {}

        self.config = {
            'host': config.get('host', 'localhost'),
            'port': config.get('port', 1883),
            'client_id': config.get('client_id', f'python-{int(time.time() * 1000) % 1000000}'),
            'username': config.get('username', ''),
            'password': config.get('password', ''),
            'keepalive': config.get('keepalive', 60),
            'auto_connect': config.get('auto_connect', True)
        }

        self.state = State.DISCONNECTED
        self.socket: Optional[socket.socket] = None
        self.next_packet_id = 1
        self.subscriptions = {}
        self.message_handlers = []
        self.error_handlers = []
        self.event_handlers = defaultdict(list)
        self.pending_pubacks = {}  # packet_id -> callback for QoS > 0
        self.pending_subacks = {}  # packet_id -> callback for SUBACK

        # Partial packet buffer for incomplete reads
        self.partial_buffer = b''

        # Connection callback and timeout
        self.connect_callback: Optional[Callable] = None
        self.connect_timeout_handle: Optional[threading.Timer] = None
        self.read_thread: Optional[threading.Thread] = None

        if self.config['auto_connect']:
            self.connect()

    def connect(self, callback: Optional[Callable] = None) -> None:
        """Connect to broker"""
        if self.state != State.DISCONNECTED:
            err = Exception('Already connected or connecting')
            if callback:
                callback(False, err)
            self._emit_error(err)
            return

        self.state = State.CONNECTING
        self.connect_callback = callback

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.socket.connect((self.config['host'], self.config['port']))
            print(f"[CLIENT] Connected to {self.config['host']}:{self.config['port']}")
            
            self.send_connect()

            # Start read thread
            self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.read_thread.start()

            # Set connection timeout
            self.connect_timeout_handle = threading.Timer(5.0, self._on_connect_timeout)
            self.connect_timeout_handle.start()

        except Exception as err:
            self._emit_error(err)
            if callback:
                callback(False, err)
            if self.socket:
                self.socket.close()

    def _on_connect_timeout(self) -> None:
        """Handle connection timeout"""
        if self.state == State.CONNECTING:
            err = Exception('Connection timeout')
            self._emit_error(err)
            if self.connect_callback:
                self.connect_callback(False, err)
            if self.socket:
                self.socket.close()

    def send_connect(self) -> None:
        """Send CONNECT packet"""
        payload = (BinaryWriter()
                   .write_string(self.config['client_id'])
                   .write_string(self.config['username'])
                   .write_string(self.config['password'])
                   .write_u16(self.config['keepalive'])
                   .release())

        header = create_packet_header(PacketType.CONNECT, 0, len(payload))
        packet = header + payload
        self.socket.sendall(packet)
        print('[CLIENT] Sent CONNECT')

    def _read_loop(self) -> None:
        """Read loop for incoming data"""
        try:
            while self.state != State.DISCONNECTED:
                data = self.socket.recv(4096)
                if not data:
                    break
                self._on_data(data)
        except Exception as err:
            if self.state != State.DISCONNECTED:
                self._emit_error(err)
                if self.connect_callback:
                    self.connect_callback(False, err)
                    self.connect_callback = None
        finally:
            self._on_close()

    def _on_data(self, data: bytes) -> None:
        """Handle incoming data"""
        self.partial_buffer += data

        # Process complete packets
        while len(self.partial_buffer) >= 4:
            header_type = self.partial_buffer[0]
            header_flags = self.partial_buffer[1]
            header_payload_len = struct.unpack('>H', self.partial_buffer[2:4])[0]

            total_len = 4 + header_payload_len

            if len(self.partial_buffer) < total_len:
                break  # Incomplete packet, wait for more data

            # Extract complete packet
            packet = self.partial_buffer[:total_len]
            self.partial_buffer = self.partial_buffer[total_len:]

            # Process packet
            self._process_packet(
                {'type': header_type, 'flags': header_flags, 'payload_len': header_payload_len},
                packet[4:]
            )

    def _process_packet(self, header: dict, payload: bytes) -> None:
        """Process incoming packet"""
        packet_type = header['type']

        if packet_type == PacketType.CONNACK:
            self._handle_connack(payload)
        elif packet_type == PacketType.PUBLISH:
            self._handle_publish(header, payload)
        elif packet_type == PacketType.SUBACK:
            self._handle_suback(payload)
        elif packet_type == PacketType.PUBACK:
            self._handle_puback(payload)
        elif packet_type == PacketType.PINGRESP:
            self._handle_pingresp()
        elif packet_type == PacketType.FETCH_RESPONSE:
            self._handle_fetch_response(payload)
        elif packet_type == PacketType.OFFSET_NOT_FOUND:
            self._handle_offset_not_found(payload)
        else:
            print(f'[CLIENT] Unknown packet type: 0x{packet_type:02x}')

    def _handle_connack(self, payload: bytes) -> None:
        """Handle CONNACK response"""
        if self.connect_timeout_handle:
            self.connect_timeout_handle.cancel()

        if len(payload) < 2:
            err = Exception('Invalid CONNACK packet')
            self._emit_error(err)
            if self.connect_callback:
                self.connect_callback(False, err)
            return

        result = payload[1]

        if result == ConnectResult.ACCEPTED:
            print('[CLIENT] Connected and authenticated')
            self.state = State.AUTHENTICATED
            self._emit('connect')
            if self.connect_callback:
                self.connect_callback(True, None)
        else:
            err = Exception(f'Connection rejected: code {result}')
            self._emit_error(err)
            if self.connect_callback:
                self.connect_callback(False, err)
            if self.socket:
                self.socket.close()

    def _handle_publish(self, header: dict, payload: bytes) -> None:
        """Handle incoming PUBLISH message (with offset metadata - v1.1)"""
        try:
            reader = BinaryReader(payload)
            topic = reader.read_string()
            packet_id = reader.read_u16()
            offset = reader.read_u64()  # NEW: Offset metadata
            data = reader.read_remaining()

            qos = (header['flags'] >> 1) & 0x03

            # Send PUBACK if QoS > 0
            if qos == QoS.AT_LEAST_ONCE:
                self._send_puback(packet_id)

            # Emit message event (with offset)
            message = {
                'topic': topic,
                'data': data,
                'qos': qos,
                'packet_id': packet_id,
                'offset': offset  # NEW: Include offset
            }
            self._emit('message', message)

            # Call message handlers
            for handler in self.message_handlers:
                handler(topic, data, offset)  # Pass offset to handler
        except Exception as err:
            self._emit_error(Exception(f'Failed to parse PUBLISH: {err}'))

    def _handle_suback(self, payload: bytes) -> None:
        """Handle SUBACK (subscription acknowledgment)"""
        try:
            reader = BinaryReader(payload)
            packet_id = reader.read_u16()

            granted_qos_list = []
            while not reader.empty():
                granted_qos_list.append(reader.read_u8())

            print(f'[CLIENT] SUBACK: packetId={packet_id}, grants={granted_qos_list}')
            
            # Call the callback for this packet ID
            if packet_id in self.pending_subacks:
                callback = self.pending_subacks.pop(packet_id)
                callback({'packet_id': packet_id, 'granted_qos_list': granted_qos_list})
            
            self._emit('suback', {'packet_id': packet_id, 'granted_qos_list': granted_qos_list})
        except Exception as err:
            self._emit_error(Exception(f'Failed to parse SUBACK: {err}'))

    def _handle_puback(self, payload: bytes) -> None:
        """Handle PUBACK (publish acknowledgment)"""
        try:
            reader = BinaryReader(payload)
            packet_id = reader.read_u16()
            print(f'[CLIENT] PUBACK: packetId={packet_id}')
            
            # Call the callback for this packet ID
            if packet_id in self.pending_pubacks:
                callback = self.pending_pubacks.pop(packet_id)
                callback(True)
            
            self._emit('puback', {'packet_id': packet_id})
        except Exception as err:
            self._emit_error(Exception(f'Failed to parse PUBACK: {err}'))

    def _handle_pingresp(self) -> None:
        """Handle PINGRESP"""
        print('[CLIENT] PINGRESP received')

    def _on_close(self) -> None:
        """Close handler"""
        print('[CLIENT] Connection closed')
        self.state = State.DISCONNECTED
        self.socket = None
        self._emit('close')

    def subscribe(self, topic: str, qos: int = QoS.AT_MOST_ONCE, callback: Optional[Callable] = None) -> None:
        """Subscribe to topic"""
        if self.state != State.AUTHENTICATED:
            err = Exception('Not connected')
            self._emit_error(err)
            if callback:
                callback(False, err)
            return

        packet_id = self.next_packet_id
        self.next_packet_id += 1

        payload = (BinaryWriter()
                   .write_u16(packet_id)
                   .write_string(topic)
                   .write_u8(qos)
                   .release())

        header = create_packet_header(PacketType.SUBSCRIBE, 0x02, len(payload))
        packet = header + payload

        self.socket.sendall(packet)
        self.subscriptions[topic] = qos

        print(f'[CLIENT] Sent SUBSCRIBE: topic="{topic}", QoS={qos}')

        if callback:
            self._once('suback', callback)

    def unsubscribe(self, topic: str, callback: Optional[Callable] = None) -> None:
        """Unsubscribe from topic"""
        if self.state != State.AUTHENTICATED:
            err = Exception('Not connected')
            self._emit_error(err)
            if callback:
                callback(False, err)
            return

        packet_id = self.next_packet_id
        self.next_packet_id += 1

        payload = (BinaryWriter()
                   .write_u16(packet_id)
                   .write_string(topic)
                   .release())

        header = create_packet_header(PacketType.UNSUBSCRIBE, 0x02, len(payload))
        packet = header + payload

        self.socket.sendall(packet)
        del self.subscriptions[topic]

        print(f'[CLIENT] Sent UNSUBSCRIBE: topic="{topic}"')

        if callback:
            self._once('unsuback', callback)

    def publish(self, topic: str, data: Any, qos: int = QoS.AT_MOST_ONCE, callback: Optional[Callable] = None) -> None:
        """Publish message"""
        if self.state != State.AUTHENTICATED:
            err = Exception('Not connected')
            self._emit_error(err)
            if callback:
                callback(False, err)
            return

        packet_id = self.next_packet_id if qos > QoS.AT_MOST_ONCE else 0
        if qos > QoS.AT_MOST_ONCE:
            self.next_packet_id += 1

        # Convert string to bytes if needed
        if isinstance(data, str):
            data_bytes = data.encode('utf-8')
        else:
            data_bytes = data

        payload = (BinaryWriter()
                   .write_string(topic)
                   .write_u16(packet_id)
                   .write_bytes(data_bytes)
                   .release())

        flags = (qos << 1) & 0x06
        header = create_packet_header(PacketType.PUBLISH, flags, len(payload))
        packet = header + payload

        self.socket.sendall(packet)

        print(f'[CLIENT] Sent PUBLISH: topic="{topic}", size={len(data_bytes)}, QoS={qos}')

        if callback:
            if qos == QoS.AT_MOST_ONCE:
                callback(True)
            else:
                # Track the callback by packet ID
                self.pending_pubacks[packet_id] = callback

    def _send_puback(self, packet_id: int) -> None:
        """Send PUBACK"""
        payload = BinaryWriter().write_u16(packet_id).release()
        header = create_packet_header(PacketType.PUBACK, 0, len(payload))
        packet = header + payload
        self.socket.sendall(packet)

    def fetch_one(self, topic: str, offset: int, callback: Optional[Callable] = None) -> None:
        """Fetch single message by offset (stateless) - v1.1
        
        Args:
            topic: Topic name
            offset: Message offset
            callback: Called with (data, error, offset) or (None, error)
        """
        if self.state != State.AUTHENTICATED:
            err = Exception('Not connected')
            self._emit_error(err)
            if callback:
                callback(None, err)
            return

        payload = (BinaryWriter()
                   .write_string(topic)
                   .write_u64(offset)
                   .release())

        header = create_packet_header(PacketType.FETCH_ONE, 0, len(payload))
        packet = header + payload

        self.socket.sendall(packet)

        print(f'[CLIENT] Sent FETCH_ONE: topic="{topic}", offset={offset}')

        if callback:
            # Register callback for response
            self._once('fetchResponse', lambda msg: 
                callback(msg['data'], None, msg['offset']) 
                if msg['topic'] == topic and msg['offset'] == offset 
                else None)
            self._once('offsetNotFound', lambda err:
                callback(None, err)
                if err['topic'] == topic and err['requested_offset'] == offset
                else None)

    def subscribe_from_offset(self, topic: str, start_offset: int, 
                             qos: int = QoS.AT_MOST_ONCE, callback: Optional[Callable] = None) -> None:
        """Subscribe from specific offset with catch-up - v1.1
        
        Args:
            topic: Topic name
            start_offset: Starting offset for replay
            qos: Quality of Service
            callback: Called with (success, error)
        """
        if self.state != State.AUTHENTICATED:
            err = Exception('Not connected')
            self._emit_error(err)
            if callback:
                callback(False, err)
            return

        packet_id = self.next_packet_id
        self.next_packet_id += 1

        payload = (BinaryWriter()
                   .write_u16(packet_id)
                   .write_string(topic)
                   .write_u64(start_offset)
                   .write_u8(qos)
                   .release())

        header = create_packet_header(PacketType.SUBSCRIBE_FROM_OFFSET, 0, len(payload))
        packet = header + payload

        self.socket.sendall(packet)
        
        # Track subscription mode
        self.subscriptions[topic] = {'qos': qos, 'mode': SubscriptionMode.CATCHUP_THEN_PUSH, 'offset': start_offset}

        print(f'[CLIENT] Sent SUBSCRIBE_FROM_OFFSET: topic="{topic}", startOffset={start_offset}, QoS={qos}')

        if callback:
            self._once('suback', callback)

    def _handle_fetch_response(self, payload: bytes) -> None:
        """Handle FETCH_RESPONSE - v1.1"""
        try:
            reader = BinaryReader(payload)
            topic = reader.read_string()
            offset = reader.read_u64()
            data = reader.read_remaining()

            print(f'[CLIENT] FETCH_RESPONSE: topic=\"{topic}\", offset={offset}, size={len(data)}')

            self._emit('fetchResponse', {'topic': topic, 'offset': offset, 'data': data})
        except Exception as err:
            self._emit_error(Exception(f'Failed to parse FETCH_RESPONSE: {err}'))

    def _handle_offset_not_found(self, payload: bytes) -> None:
        """Handle OFFSET_NOT_FOUND - v1.1"""
        try:
            reader = BinaryReader(payload)
            topic = reader.read_string()
            requested_offset = reader.read_u64()
            oldest_available = reader.read_u64()
            newest_available = reader.read_u64()

            error = {
                'topic': topic,
                'requested_offset': requested_offset,
                'oldest_available': oldest_available,
                'newest_available': newest_available,
                'message': f'Offset not found: {requested_offset}, available range: {oldest_available}-{newest_available}'
            }

            print(f'[CLIENT] OFFSET_NOT_FOUND: topic=\"{topic}\", requested={requested_offset}, available={oldest_available}-{newest_available}')

            self._emit('offsetNotFound', error)
        except Exception as err:
            self._emit_error(Exception(f'Failed to parse OFFSET_NOT_FOUND: {err}'))

    def on_message(self, handler: Callable) -> None:
        """Set message handler callback"""
        self.message_handlers.append(handler)

    def on_error(self, handler: Callable) -> None:
        """Set error handler callback"""
        self.error_handlers.append(handler)

    def on(self, event: str, handler: Callable) -> None:
        """Register event handler"""
        self.event_handlers[event].append(handler)

    def _once(self, event: str, handler: Callable) -> None:
        """Register one-time event handler"""
        def wrapper(*args, **kwargs):
            handler(*args, **kwargs)
            self.event_handlers[event].remove(wrapper)
        self.event_handlers[event].append(wrapper)

    def _emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Emit event"""
        if event in self.event_handlers:
            for handler in self.event_handlers[event]:
                try:
                    handler(*args, **kwargs)
                except Exception as err:
                    print(f'[ERROR] Event handler error: {err}')

    def _emit_error(self, err: Exception) -> None:
        """Emit error"""
        print(f'[ERROR] {str(err)}')
        self._emit('error', err)
        for handler in self.error_handlers:
            try:
                handler(str(err))
            except Exception as e:
                print(f'[ERROR] Error handler error: {e}')

    def disconnect(self, callback: Optional[Callable] = None) -> None:
        """Disconnect"""
        if self.state == State.DISCONNECTED:
            if callback:
                callback()
            return

        self.state = State.DISCONNECTING

        if self.socket:
            header = create_packet_header(PacketType.DISCONNECT, 0, 0)
            try:
                self.socket.sendall(header)
            except:
                pass

            def close_socket():
                time.sleep(1)
                if self.socket:
                    self.socket.close()
                self.state = State.DISCONNECTED
                if callback:
                    callback()

            threading.Thread(target=close_socket, daemon=True).start()

    def is_connected(self) -> bool:
        """Check if connected"""
        return self.state == State.AUTHENTICATED

    def get_state(self) -> str:
        """Get current state"""
        return self.state

    def get_subscriptions(self) -> list:
        """Get subscribed topics"""
        return list(self.subscriptions.keys())
