import os
import threading
import uuid
from datetime import datetime

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

from downloader import process_excel

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")
app.config["DEFAULT_OUTPUT_DIR"] = os.path.join(os.path.dirname(__file__), "output")

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["DEFAULT_OUTPUT_DIR"], exist_ok=True)

jobs: dict = {}
jobs_lock = threading.Lock()


def get_job(job_id: str):
    with jobs_lock:
        return jobs.get(job_id)


def update_job(job_id: str, **kwargs):
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id].update(kwargs)


def append_log(job_id: str, message: str, level: str = "info"):
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id]["logs"].append(
                {"time": datetime.now().strftime("%H:%M:%S"), "message": message, "level": level}
            )


def run_download_job(job_id: str, excel_path: str, output_dir: str):
    def on_progress(event: dict):
        event_type = event.get("type")

        if event_type == "item_start":
            update_job(
                job_id,
                current=event["current"],
                total=event["total"],
                current_file=event["filename"],
            )
            append_log(
                job_id,
                f"[{event['current']}/{event['total']}] 正在处理: {event['filename']}",
            )

        elif event_type == "item_done":
            if event.get("success"):
                append_log(job_id, f"✓ 成功: {event['filename']}", "success")
            else:
                append_log(
                    job_id,
                    f"✗ 失败: {event['filename']} — {event.get('reason', '')}",
                    "error",
                )

        elif event_type == "zip_start":
            append_log(job_id, "正在生成 ZIP...")

        elif event_type == "complete":
            result = event["result"]
            update_job(
                job_id,
                status="completed",
                zip_path=result["zip_path"],
                failed_path=result["failed_path"],
                downloaded_count=result["downloaded_count"],
                failed_count=result["failed_count"],
            )
            append_log(
                job_id,
                f"完成！成功 {result['downloaded_count']} 个，失败 {result['failed_count']} 个",
                "success",
            )
            append_log(job_id, f"ZIP: {result['zip_path']}")

    try:
        update_job(job_id, status="running")
        process_excel(excel_path, output_dir, on_progress=on_progress)
    except Exception as e:
        update_job(job_id, status="error", error=str(e))
        append_log(job_id, f"任务异常: {e}", "error")


@app.route("/")
def index():
    return render_template(
        "index.html",
        default_output_dir=app.config["DEFAULT_OUTPUT_DIR"],
    )


@app.route("/api/start", methods=["POST"])
def start_job():
    if "file" not in request.files:
        return jsonify({"error": "请上传 Excel 文件"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "请选择文件"}), 400

    if not file.filename.lower().endswith((".xlsx", ".xls")):
        return jsonify({"error": "仅支持 .xlsx / .xls 文件"}), 400

    output_dir = request.form.get("output_dir", "").strip() or app.config["DEFAULT_OUTPUT_DIR"]
    output_dir = os.path.abspath(output_dir)

    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as e:
        return jsonify({"error": f"无法创建输出目录: {e}"}), 400

    safe_name = secure_filename(file.filename) or "input.xlsx"
    job_id = str(uuid.uuid4())
    upload_path = os.path.join(app.config["UPLOAD_FOLDER"], f"{job_id}_{safe_name}")
    file.save(upload_path)

    with jobs_lock:
        jobs[job_id] = {
            "id": job_id,
            "status": "pending",
            "current": 0,
            "total": 0,
            "current_file": "",
            "logs": [],
            "zip_path": None,
            "failed_path": None,
            "downloaded_count": 0,
            "failed_count": 0,
            "error": None,
            "output_dir": output_dir,
        }

    thread = threading.Thread(
        target=run_download_job,
        args=(job_id, upload_path, output_dir),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "任务不存在"}), 404

    return jsonify(
        {
            "id": job["id"],
            "status": job["status"],
            "current": job["current"],
            "total": job["total"],
            "current_file": job["current_file"],
            "logs": job["logs"],
            "zip_path": job["zip_path"],
            "failed_path": job["failed_path"],
            "downloaded_count": job["downloaded_count"],
            "failed_count": job["failed_count"],
            "error": job["error"],
            "output_dir": job["output_dir"],
        }
    )


@app.route("/api/download/<job_id>/zip")
def download_zip(job_id: str):
    job = get_job(job_id)
    if not job or not job.get("zip_path") or not os.path.exists(job["zip_path"]):
        return jsonify({"error": "ZIP 文件不存在"}), 404

    return send_file(job["zip_path"], as_attachment=True)


@app.route("/api/download/<job_id>/failed")
def download_failed(job_id: str):
    job = get_job(job_id)
    if not job or not job.get("failed_path") or not os.path.exists(job["failed_path"]):
        return jsonify({"error": "失败记录不存在"}), 404

    return send_file(job["failed_path"], as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000, threaded=True)
