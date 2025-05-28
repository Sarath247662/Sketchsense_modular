import fitz  # PyMuPDF
from ultralytics import YOLO
from PIL import Image



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