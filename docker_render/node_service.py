#!/usr/bin/env python3
"""
CEMT node service (Docker micro-system, light version).

One identical service per container. Standard library only. Configuration
arrives entirely through environment variables written by docker_render
from the ScenarioSpec, so every container is the same image.

IAE realisation
  Interface          /deliver/entry (external admission) is accepted only
                     when INTERFACE=1; otherwise 403 "no interface".
                     /deliver/connection is admission through a connection
                     relation, which supplies I at system level (Paper 1B),
                     so it does not require the node-level flag.
  Execution Pathway  a delivered payload is routed to the handler only when
                     EXEC_PATHWAY=1 or a live X supplier exists (X_SUPPLIERS,
                     the static dependency suppliers) or the delivery itself
                     confers X (channel delivery).
  Authority          the handler writes the state object only when
                     AUTHORITY=1, or a live A supplier exists (A_SUPPLIERS,
                     the static control-plane controllers), or the delivery
                     confers A (control-plane push with the plane token).
  Payload            the request body; processing it changes the state
                     object, which is what "compromised" means here.

Observer side (outside the model): /status and /act. The probe drives
rounds by calling /act on every compromised node; a node infected in round
k acts from round k+1 (the one-step detection window of Layer 4).

Relations (outward, executed on /act in this order, matching layers.py):
  connection   CONN_PEERS       POST peer/deliver/connection
  channel      CHANNEL_MEMBERS  POST member/deliver/channel   (token)
  control plane CP_GROUP        first act: own plane; later: POST member/deliver/cp
  dependency   DEP_DOWNSTREAM   POST down/deliver/dependency
"""

import json
import os
import sys
import threading
import urllib.error
import urllib.request

# bypass any system proxy: all traffic is container-to-container or localhost
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def env(name, default=""):
    return os.environ.get(name, default)


def env_list(name):
    v = env(name).strip()
    return [x for x in v.split(",") if x]


NODE_ID = env("NODE_ID", "node")
INTERFACE = env("INTERFACE", "0") == "1"
EXEC_PATHWAY = env("EXEC_PATHWAY", "1") == "1"
AUTHORITY = env("AUTHORITY", "1") == "1"
STATE_OBJECT = env("STATE_OBJECT", "state")
STATE_PATH = env("STATE_PATH", f"/tmp/{NODE_ID}_{STATE_OBJECT}")
PORT = int(env("PORT", "8000"))

X_SUPPLIERS = env_list("X_SUPPLIERS")
A_SUPPLIERS = env_list("A_SUPPLIERS")
CONN_PEERS = env_list("CONN_PEERS")
CHANNEL_MEMBERS = env_list("CHANNEL_MEMBERS")
CHANNEL_TOKEN = env("CHANNEL_TOKEN")
CHANNEL_MEMBER_TOKENS = env_list("CHANNEL_MEMBER_TOKENS")
CP_GROUP = env("CP_GROUP")                 # group id when this node is controller
CP_MEMBERS = env_list("CP_MEMBERS")
CP_TOKEN = env("CP_TOKEN")
CP_MEMBER_TOKENS = env_list("CP_MEMBER_TOKENS")
DEP_DOWNSTREAM = env_list("DEP_DOWNSTREAM")

# address book: "id=host:port,..." ; in Docker every id resolves to id:8000
ADDRS = dict(x.split("=", 1) for x in env_list("ADDRS"))


def addr(node_id):
    return ADDRS.get(node_id, f"{node_id}:8000")


STATE = {
    "node": NODE_ID,
    "compromised": False,
    "step": None,
    "via": None,
    "planes_owned": {},         # group -> step
    "acted_steps": [],
    "flags": {"I": INTERFACE, "X": EXEC_PATHWAY, "A": AUTHORITY},
}
LOCK = threading.Lock()


# ---------------------------------------------------------------- http ----

UNREACHABLE = set()   # targets that have gone away (Cut removal runs)


def http(method, target, path, body=None, timeout=1.5):
    if target in UNREACHABLE:
        return None, {}
    url = f"http://{addr(target)}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}
    except Exception:
        UNREACHABLE.add(target)
        return None, {}


def supplier_alive(node_id):
    status, _ = http("GET", node_id, "/status")
    return status == 200


# ---------------------------------------------------------- conditions ----

def has_i():
    """I for system-level delivery: the node-level flag or any admission
    relation (a zone peer). Node-level INTERFACE alone gates external entry."""
    return INTERFACE or bool(CONN_PEERS) or bool(CHANNEL_MEMBER_TOKENS) or bool(CP_MEMBER_TOKENS)


def has_x(delivery_confers_x):
    if EXEC_PATHWAY or delivery_confers_x:
        return True
    return any(supplier_alive(s) for s in X_SUPPLIERS)


def has_a(delivery_confers_a):
    if AUTHORITY or delivery_confers_a:
        return True
    return any(supplier_alive(s) for s in A_SUPPLIERS)


def process_payload(step, via, payload, confers_x=False, confers_a=False,
                    needs_interface=True):
    """The kill chain at this node. Returns (http status, message)."""
    if needs_interface and not has_i():
        return 403, "no interface"
    if not has_x(confers_x):
        return 409, "no execution pathway"
    if not has_a(confers_a):
        return 409, "no authority"
    with LOCK:
        if STATE["compromised"]:
            return 200, "already compromised"
        with open(STATE_PATH, "w") as f:       # the state change itself
            f.write(json.dumps({"step": step, "via": via, "payload": payload}))
        STATE.update(compromised=True, step=step, via=via)
    return 201, "state changed"


# --------------------------------------------------------------- acting ----

def act(step):
    """Execute outward relations. Called by the probe once per round."""
    with LOCK:
        if not STATE["compromised"] or STATE["step"] is None or STATE["step"] >= step:
            return {"acted": False, "reason": "not active this round"}
        STATE["acted_steps"].append(step)
    log = []
    body = {"step": step, "source": NODE_ID, "payload": f"payload-from-{NODE_ID}"}

    for peer in CONN_PEERS:
        s, r = http("POST", peer, "/deliver/connection", body)
        log.append(("connection", peer, s, r.get("msg")))

    for m in CHANNEL_MEMBERS:
        s, r = http("POST", m, "/deliver/channel", {**body, "token": CHANNEL_TOKEN})
        log.append(("channel", m, s, r.get("msg")))

    if CP_GROUP:
        with LOCK:
            owned_at = STATE["planes_owned"].get(CP_GROUP)
        if owned_at is None:
            with LOCK:
                STATE["planes_owned"][CP_GROUP] = step
            log.append(("control_plane", CP_GROUP, 200, "plane owned"))
        elif owned_at < step:
            for m in CP_MEMBERS:
                s, r = http("POST", m, "/deliver/cp", {**body, "token": CP_TOKEN})
                log.append(("control_plane", m, s, r.get("msg")))

    for d in DEP_DOWNSTREAM:
        s, r = http("POST", d, "/deliver/dependency", body)
        log.append(("dependency", d, s, r.get("msg")))

    return {"acted": True, "log": log}


# -------------------------------------------------------------- handler ----

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def do_GET(self):
        if self.path == "/status":
            with LOCK:
                return self._send(200, dict(STATE))
        self._send(404, {"msg": "not found"})

    def do_POST(self):
        b = self._body()
        step = int(b.get("step", 0))
        if self.path == "/act":
            return self._send(200, act(step))
        if self.path == "/deliver/entry":
            if not INTERFACE:
                code, msg = 403, "no interface"
            else:
                code, msg = process_payload(step, "entry", b.get("payload"))
        elif self.path == "/deliver/connection":
            code, msg = process_payload(step, "connection", b.get("payload"),
                                        needs_interface=False)
        elif self.path == "/deliver/channel":
            if b.get("token") not in CHANNEL_MEMBER_TOKENS:
                code, msg = 403, "not a channel member"
            else:
                code, msg = process_payload(step, "channel", b.get("payload"),
                                            confers_x=True, needs_interface=False)
        elif self.path == "/deliver/cp":
            if b.get("token") not in CP_MEMBER_TOKENS:
                code, msg = 403, "not a plane member"
            else:
                code, msg = process_payload(step, "control_plane", b.get("payload"),
                                            confers_a=True)
        elif self.path == "/deliver/dependency":
            code, msg = process_payload(step, "dependency", b.get("payload"),
                                        confers_x=True, needs_interface=False)
        else:
            code, msg = 404, "not found"
        self._send(code, {"msg": msg, "node": NODE_ID})


if __name__ == "__main__":
    ThreadingHTTPServer.allow_reuse_address = True
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[{NODE_ID}] listening on {PORT} I={INTERFACE} X={EXEC_PATHWAY} A={AUTHORITY}",
          file=sys.stderr, flush=True)
    srv.serve_forever()
