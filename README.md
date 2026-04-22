# NetDiag Pro
Universal (Win/Linux/macOS) agentless network diagnostic tool.

## Setup
1. `pip install fastapi uvicorn psutil`
2. `uvicorn netdiag_micro:app --host 0.0.0.0 --port 8000`

## Usage
- User: `http://SERVER_IP:8000/client`
- Admin: `http://SERVER_IP:8000/admin`
