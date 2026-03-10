#!/usr/bin/env python3

"""
Producer Example

Publishes messages to broker topics
"""

import sys
import json
import time
import random
import signal
import os
from datetime import datetime

# Add parent directory to path to import highway_client
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from highway_client import HighwayClient, QoS

IS_DEBUG = True
MAX_SENSORS_COUNT = 10

client = HighwayClient({
    'host': 'localhost',
    'port': 1883,
    'client_id': f'py-producer-{int(time.time() * 1000) % 1000000}',
    'auto_connect': False
})

message_count = 0

def on_connect():
    """Handle connection establishment"""
    print('\n[+] Connected to broker!\n')
    
    print(f'Init {MAX_SENSORS_COUNT} sensors ids ...')
    sensor_ids = [1000 + i for i in range(MAX_SENSORS_COUNT)]
    print(f'{MAX_SENSORS_COUNT} sensors ids is ready to use')
    
    def publish_message():
        """Publish a message"""
        global message_count
        
        sensor_id = random.choice(sensor_ids)
        speed = random.randint(0, 100)
        topic = f'highway/{sensor_id}/telemetry'
        
        message = json.dumps({
            'timestamp': datetime.now().isoformat(),
            'sensorId': sensor_id,
            'speed': speed,
            'vehicles': random.randint(0, 50),
            'temperature': 20 + random.random() * 10,
            'cordinate': {
                'x': random.randint(0, 1000),
                'y': random.randint(0, 1000),
                'z': random.randint(0, 50),
            },
            'roadId': sensor_id,
        })

        def on_publish_success(success):
            if success:
                global message_count
                message_count += 1
                print(f'[PUBLISH #{message_count}] Topic: {topic}')
                print(f'  Data: {message}\n')

        client.publish(topic, message, QoS.AT_LEAST_ONCE, on_publish_success)

    # Publish initial message
    publish_message()

    # Continue publishing every 10ms
    def publish_loop():
        while client.is_connected():
            publish_message()
            time.sleep(0.01)

    import threading
    publish_thread = threading.Thread(target=publish_loop, daemon=True)
    publish_thread.start()

    # Stop after 60 seconds (debug mode disabled)
    if not IS_DEBUG:
        def stop_after_timeout():
            time.sleep(60)
            print(f'\n\n[PRODUCER] Published {message_count} messages')
            client.disconnect()
        
        threading.Thread(target=stop_after_timeout, daemon=True).start()

def on_error(err):
    """Handle errors"""
    print(f'[-] Error: {err}')

def on_close():
    """Handle disconnect"""
    print('[-] Disconnected from broker')
    sys.exit(0)

def signal_handler(sig, frame):
    """Handle Ctrl+C"""
    print(f'\n\n[PRODUCER] Shutting down...')
    print(f'[PRODUCER] Published {message_count} messages total')
    client.disconnect(lambda: None)
    time.sleep(1)
    print('[PRODUCER] Disconnected')
    sys.exit(0)

# Register event handlers BEFORE connecting
client.on('connect', on_connect)
client.on('error', on_error)
client.on('close', on_close)

# Register signal handler for graceful shutdown
signal.signal(signal.SIGINT, signal_handler)

# NOW connect after handlers are registered
client.connect()

print('🚀 Producer started, publishing messages...')
print('   Press Ctrl+C to exit\n')

# Keep the main thread alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
