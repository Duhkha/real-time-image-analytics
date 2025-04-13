#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys

def main():
    current_label = None
    current_count = 0

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            label, count_str = line.split('\t', 1)
            count = int(count_str)

            if current_label == label:
                current_count += count
            else:
                if current_label is not None:
                    print("{}\t{}".format(current_label, current_count))
                current_label = label
                current_count = count
        except:
            continue 
    if current_label is not None:
        print("{}\t{}".format(current_label, current_count))

if __name__ == "__main__":
    main()