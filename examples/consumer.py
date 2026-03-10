#!/usr/bin/env python3

"""
Consumer Example

Connects to broker and consumes messages from topics
"""

import sys
import time
import signal
import os
from datetime import datetime

# Add parent directory to path to import highway_client
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from highway_client import HighwayClient, QoS

client = HighwayClient({
    'host': 'localhost',
    'port': 1883,
    'client_id': f'py-consumer-{int(time.time() * 1000) % 1000000}',
    'auto_connect': False
})

def on_connect():
    """Handle connection establishment"""
    print('\n[+] Connected to broker!\n')
    
    # Subscribe to sensor telemetry
    client.subscribe('highway/+/telemetry', QoS.AT_LEAST_ONCE, lambda result: None)
    print('[CONSUMER] Subscribed to highway/+/telemetry')
    
    # Also subscribe to alerts
    client.subscribe('highway/+/alerts', QoS.AT_LEAST_ONCE, lambda result: None)
    print('[CONSUMER] Subscribed to highway/+/alerts')

def on_message(msg):
    """Handle incoming messages"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f'[{timestamp}] Message from "{msg["topic"]}"')
    print(f'  Data: {msg["data"].decode("utf-8")}')
    print(f'  QoS: {msg["qos"]}\n')

def on_error(err):
    """Handle errors"""
    print(f'[-] Error: {err}')

def on_close():
    """Handle disconnect"""
    print('[-] Disconnected from broker')
    sys.exit(0)

def signal_handler(sig, frame):
    """Handle Ctrl+C"""
    print('\n\n[CONSUMER] Shutting down...')
    client.disconnect(lambda: None)
    time.sleep(1)
    print('[CONSUMER] Disconnected')
    sys.exit(0)

# Register event handlers BEFORE connecting
client.on('connect', on_connect)
client.on('message', on_message)
client.on('error', on_error)
client.on('close', on_close)

# Register signal handler for graceful shutdown
signal.signal(signal.SIGINT, signal_handler)

# NOW connect after handlers are registered
client.connect()

print('🚀 Consumer started, waiting for messages...')
print('   Press Ctrl+C to exit\n')

# Keep the main thread alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
