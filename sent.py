import json
import os

FILE = "sent.json"


def load():
    if not os.path.exists(FILE):
        return set()

    with open(FILE, "r") as f:
        return set(json.load(f))


def save(data):
    with open(FILE, "w") as f:
        json.dump(list(data), f)
