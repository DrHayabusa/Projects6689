import os
import socket
import tempfile
import threading
import time
import uuid
from datetime import datetime

from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from excel_builder import build_excel_report
from parser import OUTPUT_COLUMNS, parse_and_stage_csv


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads_v4")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs_v4")
ALLOWED_EXTENSIONS = {"csv"}
JOB_TTL_SECONDS = 60 * 60


os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = Flask(__name__, root_path=BASE_DIR, template_folder="templates_v4", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024

jobs = {}
jobs_lock = threading.Lock()


PROCESS_STEPS = [
    ("validate", "Read and validate CSV"),
    ("group", "Group vulnerabilities by IP"),
    ("clean", "Map fields and calculate exploit-aware priority"),
    ("excel", "Build Excel workbook"),
    ("ready", "Ready to download"),
]


PREVIEW_LABELS = {
    "IP Address": "IP Address",
    "DNS Name": "DNS Name",
    "Vulnerability Name": "Vulnerability Name",
    "CVE": "CVE",
    "Severity": "Severity",
    "Exploit?": "Exploit Availability",
    "Patch Priority": "Patch Priority",
    "Asset Exposure (on 1000)": "Asset Exposure (0-1000)",
    "Vulnerability Finding": "Vulnerability Finding",
    "Summary": "Summary",
    "Description": "Description",
    "Remediation": "Remediation",
    "KB Links": "KB Links",
    "Platform Details": "Platform Details",
    "First Discovered": "First Discovered",
    "Last Observed": "Last Observed",
}


def find_available_port(start_port, host="127.0.0.1", max_attempts=25):
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if sock.connect_ex((host, port)) != 0:
                return port
    raise RuntimeError(f"No open port found between {start_port} and {start_port + max_attempts - 1}.")


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def create_job(filename, upload_path):
    job_id = uuid.uuid4().hex
    output_name = f"mva-report-v4-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{job_id[:8]}.xlsx"
    output_path = os.path.join(OUTPUT_DIR, output_name)
    db_file = tempfile.NamedTemporaryFile(
        prefix=f"mva-v4-{job_id}-",
        suffix=".sqlite3",
        dir=OUTPUT_DIR,
        delete=False,
    )
    db_file.close()
    job = {
        "id": job_id,
        "status": "queued",
        "filename": filename,
        "created_at": time.time(),
        "updated_at": time.time(),
        "progress": 0,
        "message": "Queued for processing",
        "upload_path": upload_path,
        "output_path": output_path,
        "db_path": db_file.name,
        "stats": None,
        "preview_groups": [],
        "source": None,
        "download_name": output_name,
        "error": None,
        "steps": build_steps_state("validate"),
    }
    with jobs_lock:
        jobs[job_id] = job
    return job


def build_steps_state(active_key, completed=False):
    steps = []
    seen_active = False
    for key, label in PROCESS_STEPS:
        if completed:
            status = "done"
        elif key == active_key:
            status = "active"
            seen_active = True
        elif not seen_active:
            status = "done"
        else:
            status = "pending"
        steps.append({"key": key, "label": label, "status": status})
    return steps


def update_job(job_id, **updates):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return
        job.update(updates)
        job["updated_at"] = time.time()


def progress_callback(job_id, step_key, base_progress, detail):
    update_job(
        job_id,
        progress=base_progress,
        message=detail,
        steps=build_steps_state(step_key),
        status="processing",
    )


def process_job(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        return
    try:
        update_job(
            job_id,
            status="processing",
            progress=5,
            message="Initializing workbook build",
            steps=build_steps_state("validate"),
        )
        staged = parse_and_stage_csv(
            job["upload_path"],
            job["db_path"],
            progress_callback=lambda progress, detail: progress_callback(job_id, "clean", 12 + progress, detail),
        )
        update_job(
            job_id,
            progress=54,
            message=f"Mapped {staged['stats']['total_findings']:,} findings across {staged['stats']['total_ips']:,} hosts",
            steps=build_steps_state("group"),
            source=staged["source"].upper(),
        )
        build_excel_report(
            job["upload_path"],
            job["db_path"],
            job["output_path"],
            staged["group_summaries"],
            progress_callback=lambda progress, detail: progress_callback(job_id, "excel", progress, detail),
        )
        update_job(
            job_id,
            status="ready",
            progress=100,
            message="Workbook generated successfully",
            stats=staged["stats"],
            preview_groups=staged["preview_groups"],
            steps=build_steps_state("ready", completed=True),
        )
    except Exception as exc:
        update_job(
            job_id,
            status="error",
            error=str(exc),
            message="Processing failed",
            steps=build_steps_state("validate"),
        )
    finally:
        if job.get("upload_path") and os.path.exists(job["upload_path"]):
            try:
                os.remove(job["upload_path"])
            except OSError:
                pass
            update_job(job_id, upload_path=None)


def purge_stale_jobs():
    now = time.time()
    stale_ids = []
    with jobs_lock:
        for job_id, job in jobs.items():
            if now - job["updated_at"] > JOB_TTL_SECONDS:
                stale_ids.append(job_id)
    for job_id in stale_ids:
        cleanup_job_files(job_id)
        with jobs_lock:
            jobs.pop(job_id, None)


def cleanup_job_files(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return
        paths = [job.get("upload_path"), job.get("output_path"), job.get("db_path")]
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


def get_job_or_404(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            abort(404)
        return dict(job)


@app.route("/")
def upload_page():
    purge_stale_jobs()
    return render_template("upload.html")


@app.route("/upload", methods=["POST"])
def upload_file():
    purge_stale_jobs()
    file = request.files.get("file")
    if not file or not file.filename:
        return render_template("upload.html", error="Choose a Tenable SC or Tenable IO CSV file."), 400
    if not allowed_file(file.filename):
        return render_template("upload.html", error="Only .csv exports are supported."), 400

    filename = secure_filename(file.filename)
    timestamped_name = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{filename}"
    upload_path = os.path.join(UPLOAD_DIR, timestamped_name)
    file.save(upload_path)

    job = create_job(filename, upload_path)
    thread = threading.Thread(target=process_job, args=(job["id"],), daemon=True)
    thread.start()
    return redirect(url_for("processing_page", job_id=job["id"]))


@app.route("/processing/<job_id>")
def processing_page(job_id):
    job = get_job_or_404(job_id)
    return render_template("processing.html", job=job)


@app.route("/results/<job_id>")
def results_page(job_id):
    job = get_job_or_404(job_id)
    if job["status"] == "ready":
        return render_template(
            "results.html",
            job=job,
            preview_columns=OUTPUT_COLUMNS,
            preview_labels=PREVIEW_LABELS,
        )
    if job["status"] == "error":
        return render_template("processing.html", job=job), 500
    return redirect(url_for("processing_page", job_id=job_id))


@app.route("/api/status/<job_id>")
def job_status(job_id):
    job = get_job_or_404(job_id)
    return jsonify(
        {
            "status": job["status"],
            "progress": job["progress"],
            "message": job["message"],
            "error": job["error"],
            "steps": job["steps"],
            "redirect_url": url_for("results_page", job_id=job_id) if job["status"] == "ready" else None,
        }
    )


@app.route("/download/<job_id>")
def download_report(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job or job["status"] != "ready":
            abort(404)
        output_path = job["output_path"]
        download_name = job["download_name"]

    response = send_file(output_path, as_attachment=True, download_name=download_name)

    @response.call_on_close
    def _cleanup():
        cleanup_job_files(job_id)
        with jobs_lock:
            jobs.pop(job_id, None)

    return response


if __name__ == "__main__":
    host = os.environ.get("MVA_HOST", "127.0.0.1")
    preferred_port = int(os.environ.get("PORT", "5002"))
    debug = os.environ.get("MVA_DEBUG", "0") == "1"
    port = find_available_port(preferred_port, host=host)
    print(f"MVA Tool V4 running on http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)
