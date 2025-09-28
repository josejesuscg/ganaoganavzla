# list_tickets.py
import db
import json
from decimal import Decimal
from datetime import datetime, date, time

def make_json_serializable(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, list):
        return [make_json_serializable(v) for v in value]
    if isinstance(value, dict):
        return {k: make_json_serializable(v) for k, v in value.items()}
    return value

tickets = db.fetch_all_tickets()
normalized = []
for t in tickets:
    nt = {}
    for k, v in t.items():
        nt[k] = make_json_serializable(v)
    normalized.append(nt)

print(json.dumps(normalized, indent=2, ensure_ascii=False))
print("Total tickets:", len(normalized))
