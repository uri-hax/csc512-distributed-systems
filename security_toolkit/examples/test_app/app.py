import os
import time
import threading
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)
DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:s3cret-passw0rd@db:5432/myapp")
API_KEY = os.getenv("API_KEY", "AKIAIOSFODNN7EXAMPLE")
SECRET_TOKEN = os.getenv(
    "SECRET_TOKEN", "Bearer eyJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoiYWRtaW4ifQ.SflKxwRJ"
)
counter = 0
leak_store = []
open_connections = []


@app.route("/")
def index():
    return jsonify({"app": "test-app", "status": "running"})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# VULN: SSRF -- user-controlled URL
@app.route("/proxy")
def proxy():
    url = request.args.get("url", "http://localhost:5000/health")
    resp = requests.get(url, verify=False, timeout=5)
    return jsonify({"body": resp.text[:500]})


# VULN: Path traversal
@app.route("/read")
def read_file():
    path = request.args.get("path", "/etc/hostname")
    with open(path) as f:
        return jsonify({"content": f.read()[:1000]})


# VULN: Race condition
@app.route("/increment")
def increment():
    global counter
    tmp = counter
    time.sleep(0.001)
    counter = tmp + 1
    return jsonify({"counter": counter})


# VULN: Memory leak
@app.route("/leak")
def leak():
    leak_store.append("x" * 50000)
    return jsonify({"leaked_items": len(leak_store)})


# VULN: Resource allocation without limits
@app.route("/allocate")
def allocate():
    size = int(request.args.get("size", "10000"))
    data = "A" * size
    leak_store.append(data)
    return jsonify({"allocated": size, "total": len(leak_store)})


# VULN: Connection leak
@app.route("/connection-leak")
def connection_leak():
    try:
        r = requests.get("http://localhost:5000/health", timeout=2, verify=False)
        open_connections.append(r)
    except Exception:
        pass
    return jsonify({"connections": len(open_connections)})


# VULN: Secrets in error messages
@app.route("/auth-test")
def auth_test():
    token = request.args.get("token", "")
    if token != SECRET_TOKEN:
        return jsonify({"error": f"Invalid token. Expected: {SECRET_TOKEN}"}), 401
    return jsonify({"status": "ok"})


# VULN: Timing attack
@app.route("/sensitive-operation")
def sensitive_op():
    pwd = request.args.get("pwd", "")
    time.sleep(len(pwd) * 0.01)
    if pwd == "s3cret-passw0rd":
        return jsonify({"status": "authenticated"})
    return jsonify({"status": "failed"}), 401


# VULN: Info endpoint leaking secrets
@app.route("/info")
def info():
    return jsonify(
        {
            "database_url": DB_URL,
            "api_key": API_KEY,
            "secret_token": SECRET_TOKEN,
        }
    )


# VULN: Process info leak
@app.route("/process-info")
def process_info():
    import subprocess

    env = subprocess.check_output(["env"], text=True)
    return jsonify({"env": env[:500]})


# VULN: Debug endpoint
@app.route("/debug")
def debug():
    return jsonify(
        {
            "debug": True,
            "secret_key": app.secret_key or "dev-key",
            "password": DB_URL,
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
