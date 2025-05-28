import fitz  # PyMuPDF
import re
import numpy as np


def normalize_text(text):
    """Remove whitespace and lowercase for comparison."""
    return re.sub(r'\s+', '', text.lower())


def extract_text_with_pos(pdf_path, drawing_rect=None):
    """Extract every span of text with its bbox, normalized text, and page number."""
    doc = fitz.open(pdf_path)
    text_by_page = []

    for pnum, page in enumerate(doc, start=1):
        dr = drawing_rect.get(pnum) if isinstance(drawing_rect, dict) else drawing_rect
        blocks = page.get_text("dict")["blocks"]
        page_text = []

        for blk in blocks:
            if "lines" not in blk:
                continue
            for line in blk["lines"]:
                merged_spans = []
                curr = None
                for span in line["spans"]:
                    if curr is None:
                        curr = span.copy()
                    else:
                        # Merge close spans
                        if (span["bbox"][0] - curr["bbox"][2] < 5 and
                            abs(span["bbox"][1] - curr["bbox"][1]) < 2):
                            curr["text"] += " " + span["text"]
                            curr["bbox"] = [
                                min(curr["bbox"][0], span["bbox"][0]),
                                min(curr["bbox"][1], span["bbox"][1]),
                                max(curr["bbox"][2], span["bbox"][2]),
                                max(curr["bbox"][3], span["bbox"][3])
                            ]
                            curr["size"] = (curr["size"] + span["size"]) / 2
                        else:
                            merged_spans.append(curr)
                            curr = span.copy()
                if curr:
                    merged_spans.append(curr)

                for sp in merged_spans:
                    if dr and not fitz.Rect(sp["bbox"]).intersects(dr):
                        continue
                    txt = sp["text"].strip()
                    if not txt:
                        continue
                    x0, y0, x1, y1 = sp["bbox"]
                    page_text.append({
                        "text": txt,
                        "norm": normalize_text(txt),
                        "x": x0, "y": y0,
                        "w": x1 - x0, "h": y1 - y0,
                        "page": pnum,
                        "font_size": sp.get("size")
                    })

        text_by_page.append(page_text)

    doc.close()
    return text_by_page

def compare_text_positions(old_data, new_data, tolerance=200):
    """
    Compare two lists-of-lists of text spans page-by-page.
    Returns a list of change dicts and a bbox_dict grouping Added/Deleted boxes.
    """
    changes = []
    cid = 1
    bbox_dict = {"Added": {}, "Deleted": {}}
    matched_old_ids, matched_new_ids = set(), set()

    for idx in range(max(len(old_data), len(new_data))):
        old_page = old_data[idx] if idx < len(old_data) else []
        new_page = new_data[idx] if idx < len(new_data) else []

        # Deletions
        for o in old_page:
            found = False
            for n in new_page:
                if n["norm"] == o["norm"] and id(n) not in matched_new_ids:
                    if abs(n["x"] - o["x"]) + abs(n["y"] - o["y"]) <= tolerance:
                        matched_old_ids.add(id(o))
                        matched_new_ids.add(id(n))
                        found = True
                        break
            if not found:
                changes.append({
                    "Change #": cid,
                    "Page": o["page"],
                    "ChangeType": "Deleted",
                    "Old Text": o["text"],
                    "New Text": "",
                    "X": o["x"],
                    "Y": o["y"],
                    "W": o["w"],
                    "H": o["h"]
                })
                bbox_dict["Deleted"][(o["page"], cid)] = (o["x"], o["y"], o["w"], o["h"])
                cid += 1

        # Additions
        for n in new_page:
            if id(n) not in matched_new_ids:
                changes.append({
                    "Change #": cid,
                    "Page": n["page"],
                    "ChangeType": "Added",
                    "Old Text": "",
                    "New Text": n["text"],
                    "X": n["x"],
                    "Y": n["y"],
                    "W": n["w"],
                    "H": n["h"]
                })
                bbox_dict["Added"][(n["page"], cid)] = (n["x"], n["y"], n["w"], n["h"])
                cid += 1

    return changes, bbox_dict