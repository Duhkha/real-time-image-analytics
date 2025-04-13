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
                    # Use .format() instead of f-string
                    print("{}\t{}".format(current_label, current_count))
                current_label = label
                current_count = count
        except:
            # Ignore errors in parsing or processing individual lines
            continue # Use continue to proceed to next line on error

    # Output the last label count
    if current_label is not None:
         # Use .format() instead of f-string
        print("{}\t{}".format(current_label, current_count))

if __name__ == "__main__":
    main()