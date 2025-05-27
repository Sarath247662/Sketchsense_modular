# # app/blueprints/compare/routes.py
# import os
# from flask           import request, jsonify, send_file, abort
# from flask_jwt_extended import jwt_required, get_jwt_identity
# from ...services.logging_service import log_pdf_upload, write_compare_log
# from ...services.pdf_service      import process_comparison
# from ...utils.file_utils          import save_temp_pdf, cleanup_temp
# from . import compare_bp

# @compare_bp.route("/compare", methods=["POST"])
# @jwt_required()
# def compare_files():
#     user_id = get_jwt_identity()
#     ip      = request.remote_addr

#     # Ensure both files present
#     if "file1" not in request.files or "file2" not in request.files:
#         return jsonify({"error": "Both files are required"}), 400

#     # Save uploads locally
#     old_path = save_temp_pdf(request.files["file1"])
#     new_path = save_temp_pdf(request.files["file2"])

#     # Log uploads & compare invocation
#     log_pdf_upload(user_id, os.path.basename(old_path), ip)
#     log_pdf_upload(user_id, os.path.basename(new_path), ip)
#     write_compare_log(user_id, ip)

#     try:
#         # Unpack the three output paths
#         added_pdf_path, deleted_pdf_path, csv_path = process_comparison(old_path, new_path)

#         # Build download URLs based on your API host
#         host = request.host_url.rstrip("/")
#         return jsonify({
#             "download_url_old": f"{host}/download/{os.path.basename(added_pdf_path)}",
#             "download_url_new": f"{host}/download/{os.path.basename(deleted_pdf_path)}",
#             "download_url":     f"{host}/download/{os.path.basename(csv_path)}"
#         }), 200

#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

#     finally:
#         # Always clean up the temporary uploads
#         cleanup_temp(old_path)
#         cleanup_temp(new_path)

# @compare_bp.route("/download/<filename>", methods=["GET"])
# def download_file(filename):
#     fp = os.path.join("output", filename)
#     if not os.path.exists(fp):
#         abort(404)
#     return send_file(fp, as_attachment=True)


# app/blueprints/compare/routes.py

import os
from flask import (
    request, jsonify, send_file, abort, current_app
)
from flask_jwt_extended import jwt_required, get_jwt_identity
from ...services.logging_service import log_pdf_upload, write_compare_log
from ...services.pdf_service      import process_comparison
from ...utils.file_utils          import save_temp_pdf, cleanup_temp
from . import compare_bp

@compare_bp.route("/compare", methods=["POST"])
@jwt_required()
def compare_files():
    user_id = get_jwt_identity()
    ip      = request.remote_addr

    # Validate inputs
    if "file1" not in request.files or "file2" not in request.files:
        return jsonify({"error": "Both files are required"}), 400

    # Save uploads
    old_path = save_temp_pdf(request.files["file1"])
    new_path = save_temp_pdf(request.files["file2"])

    # Log activity
    log_pdf_upload(user_id, os.path.basename(old_path), ip)
    log_pdf_upload(user_id, os.path.basename(new_path), ip)
    write_compare_log(user_id, ip)

    try:
        # Run the diff pipeline
        added_pdf, deleted_pdf, csv_file = process_comparison(old_path, new_path)

        # Return **relative** download URLs
        return jsonify({
            "download_url_old":  f"/download/{os.path.basename(added_pdf)}",
            "download_url_new":  f"/download/{os.path.basename(deleted_pdf)}",
            "download_url":      f"/download/{os.path.basename(csv_file)}"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        # Clean up temp uploads
        cleanup_temp(old_path)
        cleanup_temp(new_path)

@compare_bp.route("/download/<filename>", methods=["GET"])
def download_file(filename):
    # Build path to the output directory one level above app/
    project_root = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
    file_path    = os.path.join(project_root, "output", filename)

    current_app.logger.debug(f"Download requested for: {file_path}")
    if not os.path.isfile(file_path):
        abort(404)
    return send_file(file_path, as_attachment=True)

