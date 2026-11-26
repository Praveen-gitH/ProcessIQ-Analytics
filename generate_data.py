import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)
OUTPUT = Path(__file__).parent / "data" / "order_event_log.csv"
OUTPUT.parent.mkdir(exist_ok=True)

regions = ["South", "North", "East", "West"]
channels = ["Website", "Mobile App", "Marketplace"]
rows = []

for n in range(1, 501):
    case_id = f"ORD{10000+n}"
    region = random.choice(regions)
    channel = random.choice(channels)
    start = datetime(2026, 1, 1) + timedelta(days=random.randint(0, 150))
    current = start

    # Each case follows the standard path, with occasional rework loops.
    steps = [
        ("Order Created", random.randint(0, 1)),
        ("Payment Approved", random.randint(1, 12)),
        ("Inventory Checked", random.randint(1, 18)),
    ]
    if random.random() < 0.16:
        steps.append(("Inventory Recheck", random.randint(1, 10)))
    if random.random() < 0.10:
        steps.append(("Payment Retry", random.randint(1, 8)))
    steps += [
        ("Order Packed", random.randint(1, 12)),
        ("Order Shipped", random.randint(1, 8)),
        ("Order Delivered", random.randint(1, 14)),
    ]

    for activity, days in steps:
        current += timedelta(hours=days * 24 + random.randint(0, 8))
        rows.append({
            "case_id": case_id,
            "activity": activity,
            "timestamp": current.strftime("%Y-%m-%d %H:%M:%S"),
            "region": region,
            "channel": channel
        })

with OUTPUT.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["case_id", "activity", "timestamp", "region", "channel"])
    writer.writeheader()
    writer.writerows(rows)

print(f"Created {len(rows)} event records at {OUTPUT}")
