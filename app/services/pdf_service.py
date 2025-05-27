# app/services/pdf_service.py

import os
import pandas as pd
from ..utils.file_utils import save_temp_pdf, cleanup_temp
from .diff_service import (
    get_largest_rects_per_page,
    extract_text_with_pos,
    adjust_new_elements_positions,
    compare_text_positions,
    inverse_adjust_bbox,
    extract_table_bboxes,
    match_ps_tables,
    remove_common_table_changes,
    reassign_change_numbers,
    annotate_pdf
)

def process_comparison(uploaded_file1, uploaded_file2, output_dir="output"):
    """
    Orchestrates the full PDF diff pipeline:
    1. Saves uploaded files to temp paths.
    2. Runs text+table extraction, diff, PS-table matching, cleanup.
    3. Writes out CSV of changes and two annotated PDFs.
    4. Cleans up temps and returns the output file paths.
    """
    # 1. Save uploads
    old_path = save_temp_pdf(uploaded_file1, folder="static")
    new_path = save_temp_pdf(uploaded_file2, folder="static")

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # 2. Compute per-page “drawing” rects
    old_page_rects = get_largest_rects_per_page(old_path)
    new_page_rects = get_largest_rects_per_page(new_path)

    # 3. Extract text spans
    old_text_data = extract_text_with_pos(old_path, drawing_rect=old_page_rects)
    new_text_data = extract_text_with_pos(new_path, drawing_rect=new_page_rects)

    # 4. Align new spans into old coords if both rect sets exist
    if old_page_rects and new_page_rects:
        new_text_data = adjust_new_elements_positions(
            new_text_data, old_page_rects, new_page_rects
        )

    # 5. Compute text diffs
    tolerance = 100
    changes, bbox_dict = compare_text_positions(
        old_text_data, new_text_data, tolerance=tolerance
    )

    # 6. Inverse-map “Added” bboxes back into new-PDF coords
    if old_page_rects and new_page_rects and "Added" in bbox_dict:
        inv_added = {}
        for key, box in bbox_dict["Added"].items():
            page = key[0]
            dr_o = old_page_rects.get(page)
            dr_n = new_page_rects.get(page)
            inv_added[key] = (
                inverse_adjust_bbox(box, dr_o, dr_n)
                if dr_o and dr_n else box
            )
        bbox_dict["Added"] = inv_added

    # 7. Extract table bboxes
    old_tables = extract_table_bboxes(old_path, drawing_rect=old_page_rects)
    old_table_dict = {(t["page"], i+1): t["bbox"]
                      for i, t in enumerate(old_tables)}

    new_tables = extract_table_bboxes(new_path, drawing_rect=new_page_rects)
    new_table_dict = {(t["page"], i+1): t["bbox"]
                      for i, t in enumerate(new_tables)}

    # 8. Match PS tables across PDFs
    matched = match_ps_tables(
        old_path, new_path,
        old_table_dict, new_table_dict,
        tol=20
    )
    added_ps = [(new_key[0], new_table_dict[new_key])
                for _, new_key in matched]
    deleted_ps = [(old_key[0], old_table_dict[old_key])
                  for old_key, _ in matched]

    # 9. Remove changes inside PS tables
    changes, bbox_dict = remove_common_table_changes(
        changes, bbox_dict, matched,
        old_path, new_path,
        old_table_dict, new_table_dict
    )

    # 10. Re-number Change # sequences
    changes, bbox_dict = reassign_change_numbers(changes, bbox_dict)

    # 11. Write CSV of all changes
    df = pd.DataFrame(changes)
    csv_path = os.path.join(output_dir, "vector_text_changes.csv")
    df.to_csv(csv_path, index=False)

    # 12. Generate annotated PDFs
    added_pdf = os.path.join(output_dir, "annotated_new_added.pdf")
    deleted_pdf = os.path.join(output_dir, "annotated_old_deleted.pdf")

    annotate_pdf(
        new_path, added_pdf,
        bbox_dict.get("Added", {}),
        type_name="Added",
        ps_regions=added_ps
    )
    annotate_pdf(
        old_path, deleted_pdf,
        bbox_dict.get("Deleted", {}),
        type_name="Deleted",
        ps_regions=deleted_ps
    )

    # 13. Cleanup temporary uploads
    cleanup_temp(old_path)
    cleanup_temp(new_path)

    return added_pdf, deleted_pdf, csv_path
