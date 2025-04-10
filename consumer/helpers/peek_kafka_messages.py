import os
import sys
import json
import time
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()
print("Loaded environment variables from .env file (if found).")


# Kafka Configuration 
KAFKA_BROKER = "kafka.spacerra.com:9092"
SECURITY_PROTOCOL = "SASL_SSL"
SASL_MECHANISM = "SCRAM-SHA-512"
SASL_USERNAME = "spartacus"
SASL_PASSWORD = os.environ.get('KAFKA_USER_PASSWORD')
KAFKA_TOPIC = "image_metadata_topic" 

# Consumer Group ID - Use a unique ID for peeking so it doesn't interfere
PEEK_GROUP_ID = f"peek-script-{int(time.time())}"

CONSUMER_TIMEOUT = 5000 # 5 seconds

# --- End Configuration ---

print("--- Starting Kafka Message Peeker ---")
print(f"Connecting to: {KAFKA_BROKER}")
print(f"Topic: {KAFKA_TOPIC}")
print(f"Using temporary Group ID: {PEEK_GROUP_ID}")

consumer = None
message_count = 0
try:
    consumer = KafkaConsumer(
        KAFKA_TOPIC, 
        bootstrap_servers=[KAFKA_BROKER],
        security_protocol=SECURITY_PROTOCOL,
        sasl_mechanism=SASL_MECHANISM,
        sasl_plain_username=SASL_USERNAME,
        sasl_plain_password=SASL_PASSWORD,
        ssl_check_hostname=True, 
        group_id=PEEK_GROUP_ID,  
        auto_offset_reset='earliest', 
        enable_auto_commit=False, # <<< IMPORTANT: Do NOT auto commit offsets
        consumer_timeout_ms=CONSUMER_TIMEOUT,
        value_deserializer=lambda v: json.loads(v.decode('utf-8', errors='ignore')) 
    )
    print("Consumer connected. Reading messages from the beginning...")

    # Loop through messages received
    for message in consumer:
        message_count += 1
        print("-" * 20)
        print(f"Message #{message_count}")
        print(f"  Partition: {message.partition}")
        print(f"  Offset:    {message.offset}")
        # print(f"  Timestamp: {message.timestamp} ({datetime.fromtimestamp(message.timestamp/1000)})") 
        print(f"  Key:       {message.key}")
        print(f"  Value:     {message.value}") 

    print("\n" + "=" * 40)
    if message_count > 0:
        print(f"Finished reading messages. Found {message_count} messages.")
    else:
         print("No messages found in the topic or consumer timed out before receiving any.")
    print(f"Consumer timed out after {CONSUMER_TIMEOUT}ms of inactivity (or reached end).")
    print("Offsets were NOT committed for this group.")
    print("=" * 40 + "\n")


except NoBrokersAvailable:
    print(f"\nError: Could not connect to Kafka brokers at {KAFKA_BROKER}.")
except Exception as e:
    print(f"\nAn error occurred: {e}")

finally:
    if consumer:
        print("Closing Kafka consumer...")
        consumer.close()

print("--- Peek Script Finished ---")