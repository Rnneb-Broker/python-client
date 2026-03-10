#!/usr/bin/env python3

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from highway_client import HighwayClient, QoS

print("=" * 60)
print("E2E TEST: Producer and Consumer")
print("=" * 60)

messages_received = []
publish_confirmed = False

# Consumer setup
print("\n[CONSUMER] Creating consumer...")
consumer = HighwayClient({
    'host': 'localhost',
    'port': 1883,
    'client_id': 'test-consumer',
    'auto_connect': False
})

def on_consumer_connect():
    print("[CONSUMER] Connected!")
    consumer.subscribe('test/topic', QoS.AT_LEAST_ONCE)
    print("[CONSUMER] Subscribed to test/topic")

def on_consumer_message(msg):
    print(f"[CONSUMER] Message received: {msg['data'].decode()}")
    messages_received.append(msg)

consumer.on('connect', on_consumer_connect)
consumer.on('message', on_consumer_message)

print("[CONSUMER] Connecting...")
consumer.connect()
time.sleep(1)

# Producer setup
print("\n[PRODUCER] Creating producer...")
producer = HighwayClient({
    'host': 'localhost',
    'port': 1883,
    'client_id': 'test-producer',
    'auto_connect': False
})

def on_producer_connect():
    print("[PRODUCER] Connected!")
    def on_publish_success(success):
        global publish_confirmed
        publish_confirmed = True
        print(f"[PRODUCER] Publish callback: success={success}")
    
    print("[PRODUCER] Publishing message...")
    producer.publish('test/topic', 'Hello from E2E test!', QoS.AT_LEAST_ONCE, on_publish_success)

producer.on('connect', on_producer_connect)

print("[PRODUCER] Connecting...")
producer.connect()
time.sleep(1)

# Wait for message delivery
print("\n[TEST] Waiting for message delivery...")
for i in range(5):
    time.sleep(1)
    print(f"[WAIT] {i+1}s... received={len(messages_received)}, published={publish_confirmed}")
    if messages_received and publish_confirmed:
        break

# Verify
print("\n" + "=" * 60)
if publish_confirmed and messages_received:
    print("[+] SUCCESS: Producer published and consumer received!")
    print(f"   - Publish confirmed: {publish_confirmed}")
    print(f"   - Messages received: {len(messages_received)}")
else:
    print("[-] FAILURE:")
    print(f"   - Publish confirmed: {publish_confirmed}")
    print(f"   - Messages received: {len(messages_received)}")
print("=" * 60)

producer.disconnect()
consumer.disconnect()
