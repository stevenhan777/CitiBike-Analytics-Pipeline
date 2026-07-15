# Ingesting from S3 Helper functions. Handles both folder naming conventions inside yearly zips:
# pre-2020: "1_January", "2_February", etc.
# 2020+: "202001-citibike-tripdata", etc.

import subprocess
import os
import glob
import shutil
import re
import csv

def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

MONTH_NAME_TO_NUM = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12"
}

def resolve_month_key(entry_name, year):
    """
    Given a folder/zip entry name and the year of the source zip,
    return a "YYYYMM" key, or None if it doesn't match either
    known naming convention.
    """
    # Convention 1 (2020+): starts with 6-digit YYYYMM
    m = re.match(r"^(\d{6})", entry_name)
    if m:
        return m.group(1)

    # Convention 2 (pre-2020): "1_January", "2_February", etc.
    m = re.match(r"^(\d{1,2})[_\-\s]+([A-Za-z]+)", entry_name)
    if m:
        month_num_raw = m.group(1).zfill(2)
        month_name = m.group(2).lower()

        # Check the name against the number, in case of typos in source data
        if month_name in MONTH_NAME_TO_NUM:
            return f"{year}{MONTH_NAME_TO_NUM[month_name]}"
        elif 1 <= int(month_num_raw) <= 12:
	        print("there was typo in ", month_name)
            return f"{year}{month_num_raw}"
            
    return None

def combine_csvs(csv_paths, output_path):
    """
    Combine multiple CSVs into one, keeping only the first file's header.
    Assumes all CSVs in the group share the same column structure.
    """
    if not csv_paths:
        return False

    csv_paths = sorted(csv_paths)

    with open(output_path, "w", newline="", encoding="utf-8") as out_f:
        writer = None
        for i, path in enumerate(csv_paths):
            with open(path, "r", newline="", encoding="utf-8", errors="replace") as in_f:
                reader = csv.reader(in_f)
                header = next(reader, None)
                if header is None:
                    continue
                if i == 0:
                    writer = csv.writer(out_f)
                    writer.writerow(header)
                for row in reader:
                    writer.writerow(row)
    return True

def extract_yearly_zip(zip_path, extract_dir, year):
    """
    2014-2023 year top level zip may unzip into:
    - month folders/zips directly at the top level, OR
    - a single folder (i.e. "2014-citibike-tripdata")
    containing the month folders/zips one level down
    Handles both pre-2020 ("1_January") and 2020+ ("YYYYMM-citibike-tripdata") folder naming.

    Returns: dict mapping month_key ("YYYYMM") -> list of raw CSV paths
    """
    top_extract = f"{extract_dir}/_top"
    os.makedirs(top_extract, exist_ok=True)
    run(f"unzip -o -q '{zip_path}' -d '{top_extract}'")

    # define dictionary where keys are months and values are list of file paths
    month_csvs = {}

    # function to append paths to respective month key in month_csvs
    def register(month_key, path):
        month_csvs.setdefault(month_key, []).append(path)

    def process_entries(dir_to_scan, depth=0):
        for entry in os.listdir(dir_to_scan):

            # skipping hidden file
            if entry == "__MACOSX":
                continue

            full_path = os.path.join(dir_to_scan, entry)

            # check if folder instead of file
            if os.path.isdir(full_path):
                month_key = resolve_month_key(entry, year)
                if month_key:
                    found = glob.glob(f"{full_path}/**/*.csv", recursive=True)
                    found = [p for p in found if "__MACOSX" not in p]
                    for p in found:
                        register(month_key, p)
                elif depth == 0:
                    # Doesn't look like a month folder, it's probably a
                    # wrapper folder (i.e. "2014-citibike-tripdata").
                    # Recurse one level in to look for month folders inside.
                    print(f"Not a month folder, looking inside: {entry}")
                    process_entries(full_path, depth=1)
                else:
                    print(f"Unrecognized folder, skipping: {entry}")

            elif entry.lower().endswith(".zip"):
                month_key = resolve_month_key(entry, year)
                if not month_key:
                    print(f"Unrecognized zip, skipping: {entry}")
                    continue
                nested_dir = os.path.join(dir_to_scan, entry.replace(".zip", "_extracted"))
                os.makedirs(nested_dir, exist_ok=True)
                run(f"unzip -o -q '{full_path}' -d '{nested_dir}'")
                found = glob.glob(f"{nested_dir}/**/*.csv", recursive=True)
                found = [p for p in found if "__MACOSX" not in p]
                for p in found:
                    register(month_key, p)

            # Ignores loose csvs directly in main directory
            elif entry.lower().endswith(".csv"):
                print(f"Ignoring stray CSV: {entry}")

    process_entries(top_extract, depth=0)
    return month_csvs

def extract_monthly_zip(zip_path, extract_dir, ym):
    """
    202401-202605 month and year folders: zip contains CSVs directly, no nested folders.
    """
    os.makedirs(extract_dir, exist_ok=True)
    run(f"unzip -o -q '{zip_path}' -d '{extract_dir}'")
    csv_paths = glob.glob(f"{extract_dir}/**/*.csv", recursive=True)
    csv_paths = [p for p in csv_paths if "__MACOSX" not in p]
    return {ym: csv_paths}