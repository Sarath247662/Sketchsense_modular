# app/services/logging_service.py
import os, csv, socket
from ..utils.time_utils import get_ist_time

def _write_csv(path, headers, row):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new: w.writerow(headers)
        w.writerow(row)
    return True

def write_login_log(user_id, ip):
    _write_csv(
        "logs/login_logs.csv",
        ["Timestamp","User ID","IP","Hostname"],
        [get_ist_time(), user_id, ip, socket.gethostname()]
    )

def write_compare_log(user_id, ip, count=1):
    _write_csv(
        "logs/compare_logs.csv",
        ["Timestamp","User ID","IP","Count"],
        [get_ist_time(), user_id, ip, count]
    )

def log_pdf_upload(user_id, filename, ip):
    return _write_csv(
        "logs/dwg_count.csv",
        ["Timestamp","User ID","Filename","IP","Hostname","Status"],
        [get_ist_time(), user_id, filename, ip, socket.gethostname(), "Upload Started"]
    )
