import csv
import re

RAW_FILE = "raw_colonies.txt"
OUT_FILE = "colonies.csv"

def is_header_line(line: str) -> bool:
    """Return True if the line is a header/separator we should ignore."""
    line = line.strip()
    if not line:
        return True
    # Header words
    if line.startswith("Colony Name"):
        return True
    if line.startswith("—"):
        return True
    # Sometimes "Colony Name Cat." etc
    if "Colony Name" in line and ("Cat" in line or "Category" in line):
        return True
    return False

def parse_line(line: str):
    """
    Parse a single line like:
    'Aali    H'
    'Lado Sarai Extn  F'
    into (colony_name, category).
    """
    line = line.strip()
    if not line:
        return None

    # Split based on last whitespace group
    parts = line.rsplit(None, 1)
    if len(parts) != 2:
        return None

    name, cat = parts[0].strip(), parts[1].strip().upper()

    # Skip if cat is clearly not a category letter
    if cat in ("CAT.", "CATEGORY", "CAT"):
        return None
    if not re.fullmatch(r"[A-H]", cat):
        return None

    return name, cat

def main():
    colonies = []
    with open(RAW_FILE, encoding="utf-8") as f:
        for raw_line in f:
            if is_header_line(raw_line):
                continue
            parsed = parse_line(raw_line)
            if parsed:
                colonies.append(parsed)

    # Remove duplicates while preserving order
    seen = set()
    cleaned = []
    for name, cat in colonies:
        key = (name.lower(), cat)
        if key not in seen:
            seen.add(key)
            cleaned.append((name, cat))

    print(f"Parsed {len(cleaned)} colony rows.")

    # Write to CSV
    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["colony_name", "category"])
        writer.writerows(cleaned)

    print(f"Written to {OUT_FILE}")

if __name__ == "__main__":
    main()
