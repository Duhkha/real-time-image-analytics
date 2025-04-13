#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import json
from datetime import datetime

def main():
    try:
        content = sys.stdin.read()
        metadata = json.loads(content)
        timestamp = metadata.get("processing_timestamp")
        if not timestamp:
            return

        dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%f")
        hour_key = dt.strftime("%Y-%m-%d %H:00")
        full_ts = dt.strftime("%Y-%m-%dT%H:%M:%S")

        if 'detections' in metadata and isinstance(metadata['detections'], list):
            for detection in metadata['detections']:
                if 'label' in detection:
                    label = detection['label']
                    print("{}@{}\t{}".format(label, hour_key, full_ts))
    except:
        pass

if __name__ == "__main__":
    main()
