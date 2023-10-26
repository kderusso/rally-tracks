#!/usr/bin/env python3
import json
import struct
import sys

try:
    from tqdm import tqdm

    iterate = lambda i: tqdm(range(i))
except ModuleNotFoundError:
    print("Warning: [tqdm] package is not available and you won't be able to see progress.", file=sys.stderr)
    iterate = range


def to_json(f):
    for line in f:
        l = line.split('\t')
        dict = { "docid": l[0], "url": l[1], "title": l[2], "body": l[3]}
        print(json.dumps(dict))

if len(sys.argv) != 2:
    print(f"Error: No tsv file. Rerun using [{sys.argv[0]} /path/to/msmarco-passage.tsv].")
    sys.exit(1)

with open(sys.argv[1], "r") as f:
    to_json(f)
