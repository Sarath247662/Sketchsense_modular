# app/services/diff_service.py

import fitz
import numpy as np

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
