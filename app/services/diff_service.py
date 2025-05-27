# app/services/diff_service.py

import re
import fitz
from PIL import Image
from ultralytics import YOLO
import numpy as np
from skimage.metrics import structural_similarity as ssim
from sklearn.metrics.pairwise import cosine_similarity

def normalize_text(text):
    """Remove whitespace and lowercase for comparison."""
    return re.sub(r'\s+', '', text.lower())

def get_largest_rects_per_page(pdf_path):
    """For each page, return the union rect of either text blocks or drawings, whichever is larger."""
    doc = fitz.open(pdf_path)
    page_rects = {}

    for page_num, page in enumerate(doc, start=1):
        # Text block union
        text_blocks = page.get_text("blocks")
        union_text = None
        if text_blocks:
            union_text = fitz.Rect(text_blocks[0][:4])
            for b in text_blocks[1:]:
                union_text |= fitz.Rect(b[:4])

        # Drawing union
        drawings = page.get_drawings()
        union_drawings = None
        if drawings:
            union_drawings = fitz.Rect(drawings[0]["rect"])
            for d in drawings[1:]:
                union_drawings |= fitz.Rect(d["rect"])

        # Decide which rect to use
        if union_text and union_drawings:
            if union_text.get_area() > union_drawings.get_area():
                page_rects[page_num] = union_text
            else:
                page_rects[page_num] = union_drawings
        elif union_text:
            page_rects[page_num] = union_text
        elif union_drawings:
            page_rects[page_num] = union_drawings
        else:
            page_rects[page_num] = page.rect

    doc.close()
    return page_rects

def extract_table_bboxes(pdf_path, drawing_rect=None):
    """Detect table-like regions via YOLO + built-in find_tables, returning bbox list."""
    model = YOLO("best_of_best_2.pt")
    doc = fitz.open(pdf_path)
    table_bboxes = []

    for page in doc:
        dr = drawing_rect.get(page.number + 1) if isinstance(drawing_rect, dict) else drawing_rect
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # YOLO predictions
        results = model.predict(img)
        wf = page.rect.width / pix.width
        hf = page.rect.height / pix.height
        for r in results:
            for box in r.boxes.data.tolist():
                cls = int(box[5]) if len(box) > 5 else 0
                x1, y1, x2, y2 = box[:4]
                rect = fitz.Rect(
                    page.rect.x0 + x1 * wf,
                    page.rect.y0 + y1 * hf,
                    page.rect.x0 + x2 * wf,
                    page.rect.y0 + y2 * hf
                )
                if dr and not dr.intersects(rect):
                    continue
                table_bboxes.append({"page": page.number + 1, "bbox": rect, "class": cls})

        # Built-in table detection
        for table in page.find_tables():
            table_bboxes.append({"page": page.number + 1, "bbox": table.bbox})

    doc.close()
    return table_bboxes

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

def annotate_pdf(input_pdf_path, output_pdf_path, bbox_dict, type_name, ps_regions=None):
    """
    Draws highlights/rectangles on each page for Added or Deleted changes.
    ps_regions is optional list of (page, fitz.Rect) for PS table markers.
    """
    doc = fitz.open(input_pdf_path)

    if type_name == "Modified":
        for (pnum, cid), (x, y, x1, y1) in bbox_dict.items():
            if pnum - 1 < len(doc):
                page = doc[pnum - 1]
                page.draw_rect(fitz.Rect(x, y, x1, y1), color=(1, 0, 0), width=2)

    else:
        colors = {"Added": ((0,1,0),(0,0.4,0)), "Deleted": ((1,0,0),(0.4,0,0))}
        fill_color = (1,1,0)
        opacity = 0.3
        box_color, text_color = colors[type_name]

        for (pnum, cid), (x, y, w, h) in bbox_dict.items():
            if pnum - 1 < len(doc):
                page = doc[pnum - 1]
                r = fitz.Rect(x, y, x+w, y+h)
                page.draw_rect(r, fill=fill_color, fill_opacity=opacity)
                page.draw_rect(r, color=box_color, width=0.8)
                page.insert_text((x-5, y), str(cid), fontsize=6, color=text_color)

        if ps_regions:
            for pnum, rect in ps_regions:
                if pnum - 1 < len(doc):
                    page = doc[pnum - 1]
                    lr = fitz.Rect(rect.x0-20, rect.y0-20, rect.x0, rect.y0)
                    page.draw_rect(lr, color=(0,0,1), width=1)
                    page.insert_text((rect.x0-18, rect.y0-10), "PS", fontsize=8, color=(0,0,1))

    doc.save(output_pdf_path)
    doc.close()

def adjust_elements_positions(text_data, offset):
    """Shift every element position by offset (for partial-page annotations)."""
    out = []
    for page in text_data:
        new_page = []
        for elem in page:
            ne = elem.copy()
            ne["x"] -= offset[0]
            ne["y"] -= offset[1]
            new_page.append(ne)
        out.append(new_page)
    return out

def get_scale_factors(old_rects, new_rects):
    """Compute per-page (sx, sy) factors for scaling bboxes."""
    factors = {}
    for p, r_old in old_rects.items():
        r_new = new_rects.get(p)
        if r_new:
            sx = r_old.width / r_new.width if r_new.width else 1
            sy = r_old.height / r_new.height if r_new.height else 1
            factors[p] = (sx, sy)
    return factors

def adjust_new_elements_positions(text_data, old_rects, new_rects):
    """
    Remap new-page element coords into old-page coordinate space
    using the scale factors and origins.
    """
    sf = get_scale_factors(old_rects, new_rects)
    out = []
    for idx, page in enumerate(text_data):
        pnum = idx + 1
        r_old = old_rects.get(pnum)
        r_new = new_rects.get(pnum)
        sx, sy = sf.get(pnum, (1,1))
        new_page = []
        for elem in page:
            ne = elem.copy()
            if r_old and r_new:
                ne["x"] = (ne["x"] - r_new.x0) * sx + r_old.x0
                ne["y"] = (ne["y"] - r_new.y0) * sy + r_old.y0
                ne["w"] *= sx
                ne["h"] *= sy
            new_page.append(ne)
        out.append(new_page)
    return out

def inverse_adjust_bbox(bbox, old_rect, new_rect):
    """
    Map a bbox from old->new coordinate space (inverse scaling).
    """
    xa, ya, wa, ha = bbox
    sx = old_rect.width / new_rect.width if new_rect.width else 1
    sy = old_rect.height / new_rect.height if new_rect.height else 1
    ox = ((xa - old_rect.x0)/sx) + new_rect.x0
    oy = ((ya - old_rect.y0)/sy) + new_rect.y0
    return (ox, oy, wa/sx, ha/sy)

def match_ps_tables(pdf_old, pdf_new, old_table_dict, new_table_dict, tol=1000, shift_thresh=20):
    """
    Match “PS tables” across old/new by size, position shift, and Jaccard text similarity.
    Returns list of (old_key, new_key) matched pairs.
    """
    def jaccard_similarity(a, b):
        ta = set(re.findall(r'\w+', a.lower()))
        tb = set(re.findall(r'\w+', b.lower()))
        if not ta and not tb:
            return 1.0
        return len(ta & tb) / len(ta | tb)

    doc_o = fitz.open(pdf_old)
    doc_n = fitz.open(pdf_new)
    candidates = []

    for old_key, box_o in old_table_dict.items():
        p = old_key[0]
        ro = fitz.Rect(box_o)
        text_o = doc_o[p-1].get_text("text", clip=ro).strip()

        for new_key, box_n in new_table_dict.items():
            if new_key[0] != p:
                continue
            rn = fitz.Rect(box_n)
            if (abs(ro.width - rn.width) > tol or abs(ro.height - rn.height) > tol):
                continue
            if not (abs(ro.x0 - rn.x0) + abs(ro.y0 - rn.y0) > shift_thresh):
                continue
            text_n = doc_n[p-1].get_text("text", clip=rn).strip()
            sim = jaccard_similarity(text_o, text_n)
            if sim >= 0.4:
                candidates.append((old_key, new_key, sim))

    doc_o.close()
    doc_n.close()
    candidates.sort(key=lambda x: x[2], reverse=True)

    matched_o, matched_n, final = set(), set(), []
    for ok, nk, _ in candidates:
        if ok not in matched_o and nk not in matched_n:
            matched_o.add(ok)
            matched_n.add(nk)
            final.append((ok, nk))

    return final

def remove_common_table_changes(changes, bbox_dict, matched_tables, pdf_old, pdf_new, old_table_dict, new_table_dict):
    """
    Remove changes that lie within matched PS table areas and share words
    in common between old/new table text.
    """
    def tokenize(t): return set(re.findall(r'\w+', t.lower()))

    doc_o = fitz.open(pdf_old)
    doc_n = fitz.open(pdf_new)
    to_remove = set()

    for old_key, new_key in matched_tables:
        p = old_key[0]
        ro = fitz.Rect(old_table_dict[old_key])
        rn = fitz.Rect(new_table_dict[new_key])

        text_o = doc_o[p-1].get_text("text", clip=ro)
        text_n = doc_n[p-1].get_text("text", clip=rn)
        common = tokenize(text_o) & tokenize(text_n)

        for change in changes:
            if change["Page"] != p:
                continue
            cx = change["X"] + change["W"]/2
            cy = change["Y"] + change["H"]/2

            if change["ChangeType"] == "Deleted":
                if not ro.contains(fitz.Point(cx, cy)):
                    continue
                toks = tokenize(change["Old Text"])
            else:
                if not rn.contains(fitz.Point(cx, cy)):
                    continue
                toks = tokenize(change["New Text"])

            if common & toks:
                to_remove.add((change["Page"], change["Change #"]))

    # Filter out marked changes
    filtered = [c for c in changes if (c["Page"], c["Change #"]) not in to_remove]
    new_bbox = {"Added": {}, "Deleted": {}}
    for typ in ("Added", "Deleted"):
        for key, box in bbox_dict.get(typ, {}).items():
            if key not in to_remove:
                new_bbox[typ][key] = box

    doc_o.close()
    doc_n.close()
    return filtered, new_bbox

def reassign_change_numbers(changes, bbox_dict):
    """
    Re-number Change # sequentially and update bbox_dict accordingly.
    """
    mapping = {}
    new_changes = []
    new_bbox = {"Added": {}, "Deleted": {}}
    new_id = 1

    for c in changes:
        old_key = (c["Page"], c["Change #"])
        mapping[old_key] = new_id
        c["Change #"] = new_id
        new_changes.append(c)
        new_id += 1

    for typ in ("Added", "Deleted"):
        for old_key, box in bbox_dict.get(typ, {}).items():
            if old_key in mapping:
                new_bbox[typ][(old_key[0], mapping[old_key])] = box

    return new_changes, new_bbox
