#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys

def main():
    current_key = None
    timestamps = []

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            key, timestamp = line.split('\t', 1)
        except:
            continue

        if current_key == key:
            timestamps.append(timestamp)
        else:
            if current_key is not None:
                print("{}\t{}\t[{}]".format(current_key, len(timestamps), ", ".join(timestamps)))
            current_key = key
            timestamps = [timestamp]

    if current_key is not None:
        print("{}\t{}\t[{}]".format(current_key, len(timestamps), ", ".join(timestamps)))

if __name__ == "__main__":
    main()
