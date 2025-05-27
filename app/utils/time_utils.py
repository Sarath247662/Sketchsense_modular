from datetime import datetime
import pytz

def get_ist_time() -> str:
    """
    Return the current date & time formatted as a string in Indian Standard Time (IST).

    Uses pytz to localize to Asia/Kolkata timezone.

    Example output: "2025-05-26 14:35:12 IST"
    """
    ist_tz = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(ist_tz)
    return now_ist.strftime("%Y-%m-%d %H:%M:%S %Z")
