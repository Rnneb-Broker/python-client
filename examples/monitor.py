#!/usr/bin/env python3

"""
Monitor Example

Monitors broker activity and displays statistics
"""

import sys
import time
import json
import signal
import os

# Add parent directory to path to import highway_client
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from highway_client import HighwayClient, QoS

client = HighwayClient({
    'host': 'localhost',
    'port': 1883,
    'client_id': f'py-monitor-{int(time.time() * 1000) % 1000000}',
    'auto_connect': False
})

stats = {
    'messages_received': 0,
    'bytes_received': 0,
    'avg_speed': 0,
    'max_speed': 0,
    'min_speed': 0,
    'alert_count': 0,
    'sensors': {}
}

def on_connect():
    """Handle connection establishment"""
    print('\n[+] Connected to broker!\n')
    
    # Subscribe to sensor telemetry
    client.subscribe('highway/+/telemetry', QoS.AT_LEAST_ONCE, lambda result: None)
    print('[MONITOR] Subscribed to highway/+/telemetry')
    
    # Also subscribe to alerts
    client.subscribe('highway/+/alerts', QoS.AT_LEAST_ONCE, lambda result: None)
    print('[MONITOR] Subscribed to highway/+/alerts\n')

def on_message(msg):
    """Handle incoming messages"""
    stats['messages_received'] += 1
    stats['bytes_received'] += len(msg['data'])
    
    try:
        data = json.loads(msg['data'].decode('utf-8'))
        
        if 'speed' in data:
            # Telemetry message
            speed = data.get('speed', 0)
            sensor_id = data.get('sensorId')
            
            stats['max_speed'] = max(stats['max_speed'], speed)
            stats['min_speed'] = min(stats['min_speed'], speed)
            stats['avg_speed'] = (stats['avg_speed'] * (stats['messages_received'] - 1) + speed) / stats['messages_received']
            
            if sensor_id not in stats['sensors']:
                stats['sensors'][sensor_id] = {
                    'messages': 0,
                    'avg_speed': 0,
                    'last_speed': 0
                }
            
            sensor_stats = stats['sensors'][sensor_id]
            sensor_stats['messages'] += 1
            sensor_stats['last_speed'] = speed
            sensor_stats['avg_speed'] = (sensor_stats['avg_speed'] * (sensor_stats['messages'] - 1) + speed) / sensor_stats['messages']
        else:
            # Alert message
            stats['alert_count'] += 1
            print(f'\n🚨 ALERT: {data}')
    except:
        pass

def on_error(err):
    """Handle errors"""
    print(f'[-] Error: {err}')

def on_close():
    """Handle disconnect"""
    print('[-] Disconnected from broker')
    sys.exit(0)

def signal_handler(sig, frame):
    """Handle Ctrl+C"""
    print_stats()
    client.disconnect(lambda: None)
    time.sleep(1)
    sys.exit(0)

def print_stats():
    """Print statistics"""
    print('\n' + '='*60)
    print('BROKER MONITOR STATISTICS')
    print('='*60)
    print(f'Messages Received: {stats["messages_received"]}')
    print(f'Bytes Received: {stats["bytes_received"]:,}')
    print(f'Average Speed: {stats["avg_speed"]:.2f} km/h')
    print(f'Max Speed: {stats["max_speed"]:.2f} km/h')
    print(f'Min Speed: {stats["min_speed"]:.2f} km/h')
    print(f'Alert Count: {stats["alert_count"]}')
    print(f'\nActive Sensors: {len(stats["sensors"])}')
    
    for sensor_id, sensor_stats in sorted(stats['sensors'].items()):
        print(f'  Sensor {sensor_id}:')
        print(f'    Messages: {sensor_stats["messages"]}')
        print(f'    Avg Speed: {sensor_stats["avg_speed"]:.2f} km/h')
        print(f'    Last Speed: {sensor_stats["last_speed"]:.2f} km/h')
    
    print('='*60 + '\n')

# Register event handlers
client.on('connect', on_connect)
client.on('message', on_message)
client.on('error', on_error)
client.on('close', on_close)


client.connect();

# Register signal handler for graceful shutdown
signal.signal(signal.SIGINT, signal_handler)

print('🚀 Monitor started, collecting statistics...')
print('   Press Ctrl+C to view stats and exit\n')

# Print stats every 30 seconds
import threading

def print_stats_loop():
    while client.is_connected():
        time.sleep(30)
        print_stats()

stats_thread = threading.Thread(target=print_stats_loop, daemon=True)
stats_thread.start()

# Keep the main thread alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
