import os
import threading
import uuid
from datetime import datetime

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

from downloader import process_excel

app = Flask(__name__)

app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")
app.config["OUTPUT_FOLDER"] = os.path.join(os.path.dirname(__file__), "output")

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["OUTPUT_FOLDER"], exist_ok=True)

jobs = {}
lock = threading.Lock()


# =====================
# job管理
# =====================
def get_job(job_id):
    with lock:
        return jobs.get(job_id)


def update_job(job_id, **kwargs):
    with lock:
        if job_id in jobs:
            jobs[job_id].update(kwargs)


def add_log(job_id, msg, level="info"):
    with lock:
        jobs[job_id]["logs"].append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "message": msg,
            "level": level
        })


# =====================
# 执行任务
# =====================
def run_job(job_id, excel_path, output_dir):

    def on_progress(event):
        t = event.get("type")

        if t == "item_start":
            update_job(job_id,
                       current=event["current"],
                       total=event["total"],
                       current_file=event["filename"])

        elif t == "item_done":
            if event.get("success"):
                add_log(job_id, f"✓ 成功: {event['filename']}")
            else:
                add_log(job_id, f"✗ 失败: {event['filename']}")

        elif t == "complete":
            r = event["result"]
            update_job(job_id,
                       status="done",
                       zip_path=r["zip_path"],
                       downloaded=r["downloaded_count"],
                       failed=r["failed_count"])

            add_log(job_id, f"完成：成功 {r['downloaded_count']} 个")

    try:
        update_job(job_id, status="running")
        process_excel(excel_path, output_dir, on_progress)

    except Exception as e:
        update_job(job_id, status="error", error=str(e))
        add_log(job_id, str(e), "error")


# =====================
# 页面
# =====================
@app.route("/")
def index():
    return render_template("index.html")


# =====================
# 开始任务
# =====================
@app.route("/api/start", methods=["POST"])
def start():

    file = request.files["file"]

    job_id = str(uuid.uuid4())

    filename = secure_filename(file.filename)
    excel_path = os.path.join(app.config["UPLOAD_FOLDER"], job_id + "_" + filename)

    file.save(excel_path)

    output_dir = app.config["OUTPUT_FOLDER"]

    with lock:
        jobs[job_id] = {
            "id": job_id,
            "status": "pending",
            "current": 0,
            "total": 0,
            "current_file": "",
            "logs": [],
            "zip_path": None,
            "downloaded": 0,
            "failed": 0,
            "error": None
        }

    t = threading.Thread(
        target=run_job,
        args=(job_id, excel_path, output_dir),
        daemon=True
    )
    t.start()

    return jsonify({"job_id": job_id})


# =====================
# 状态
# =====================
@app.route("/api/status/<job_id>")
def status(job_id):

    job = get_job(job_id)

    if not job:
        return jsonify({"error": "not found"}), 404

    return jsonify(job)


# =====================
# 下载ZIP
# =====================
@app.route("/api/download/<job_id>/zip")
def download_zip(job_id):

    job = get_job(job_id)

    if not job or not job.get("zip_path"):
        return jsonify({"error": "zip not ready"}), 404

    return send_file(job["zip_path"], as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)