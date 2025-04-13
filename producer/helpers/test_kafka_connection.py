import os
import sys
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable
import time
from dotenv import load_dotenv

load_dotenv()
print("Loaded environment variables from .env file (if found).")


# --- Configuration ---
KAFKA_BROKER = "kafka.spacerra.com:9094" 
SECURITY_PROTOCOL = "SASL_PLAINTEXT"
SASL_MECHANISM = "PLAIN"

# --- SASL Credentials ---
SASL_USERNAME = "admin"
SASL_PASSWORD = os.environ.get('KAFKA_USER_PASSWORD')

# --- SSL Truststore CA Path (Extracted PEM) ---
#SSL_CAFILE = "../le_chain_full.pem" 

# --- End Configuration ---

print(f"Attempting to connect to Kafka broker: {KAFKA_BROKER}")
print(f"  Security Protocol: {SECURITY_PROTOCOL}")
print(f"  SASL Mechanism: {SASL_MECHANISM}")
print(f"  SASL Username: {SASL_USERNAME}")
#print(f"  Truststore CA (PEM): {SSL_CAFILE}")

producer = None # Initialize producer to None
connection_successful = False

try:
    producer = KafkaProducer(
        bootstrap_servers=[KAFKA_BROKER],
        security_protocol=SECURITY_PROTOCOL,
        sasl_mechanism=SASL_MECHANISM,
        sasl_plain_username=SASL_USERNAME,
        sasl_plain_password=SASL_PASSWORD,
      #  ssl_cafile=SSL_CAFILE,
        ssl_check_hostname=True, 
        api_version_auto_timeout_ms=30000, 
        request_timeout_ms=45000 
    )
    print("Producer initialized. Waiting a few seconds to check connection status...")
    time.sleep(5)

    if producer.bootstrap_connected():
        print("Bootstrap connection successful.")
        connection_successful = True
    else:
        print("WARN: Bootstrap connection reported as NOT successful after wait.")


except NoBrokersAvailable as e:
    print(f"\n--- CONNECTION FAILED ---")
    print(f"Error: Could not connect to any Kafka brokers specified: {KAFKA_BROKER}")
    print(f"Details: {e}")
    print("\nTroubleshooting:")
    print(f"- Verify the KAFKA_BROKER address and port ({KAFKA_BROKER}).")
    print("- Check network accessibility and firewalls.")
  #  print(f"- Verify the path to the extracted CA PEM file is correct: '{SSL_CAFILE}'")
    print("- Ensure the SASL username and password are correct.")
    print("- Check if the Kafka broker requires specific SASL/SSL configurations.")

except Exception as e:
    print(f"\n--- CONNECTION FAILED ---")
    print(f"An unexpected error occurred: {e}")
    print("Check broker address, port, SASL credentials, and CA file path/permissions.")

finally:
    if producer:
        print("Closing Kafka producer connection...")
        producer.close()

print("\n--- Test Script Finished ---")

if connection_successful:
    print("RESULT: Initial connection test appears SUCCESSFUL!")
    sys.exit(0) 
else:
    print("RESULT: Initial connection test FAILED.")
    sys.exit(1) 