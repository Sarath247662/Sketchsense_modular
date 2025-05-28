import fitz  # PyMuPDF

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