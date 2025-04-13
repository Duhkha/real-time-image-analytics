#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import json

def main():
    try:
        content = sys.stdin.read()
        metadata = json.loads(content)
        if 'detections' in metadata and isinstance(metadata['detections'], list):
            for detection in metadata['detections']:
                if 'label' in detection:
                    print("{}\t{}".format(detection['label'], 1))
    except:
        pass  

if __name__ == "__main__":
    main()
