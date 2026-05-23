"""
Dashboard for jobs-auto-scanner.
Run: uv run python main.py dashboard  →  http://localhost:8765
"""
from __future__ import annotations
import json, os, signal, subprocess, threading, time, uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import config
from job_scanner.store import list_jobs, stats, update_status

PORT       = 8765
_PID_FILE  = Path("data/daemon.pid")

# ── Build queue + state ───────────────────────────────────────────────────────
_queue:      list[dict]       = []   # [{id, jd, hint, added_at}]
_builds:     dict[str, dict]  = {}   # id → {status, message, company, elapsed}
_active_id:  str | None       = None
_gen_paused: bool             = False
_q_lock    = threading.Lock()


def _scraper_running() -> bool:
    if not _PID_FILE.exists():
        return False
    try:
        pid = int(_PID_FILE.read_text().strip())
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _scraper_start() -> bool:
    if _scraper_running():
        return True
    try:
        log_path = Path(__file__).parent / "data" / "daemon.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_fh = open(log_path, "a")
        proc = subprocess.Popen(
            ["uv", "run", "python", "main.py", "daemon"],
            cwd=str(Path(__file__).parent),
            stdout=log_fh, stderr=log_fh,
        )
        _PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        _PID_FILE.write_text(str(proc.pid))
        return True
    except Exception:
        return False


def _scraper_stop() -> bool:
    if not _scraper_running():
        return True
    try:
        pid = int(_PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        _PID_FILE.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def _run_one(item: dict) -> None:
    global _active_id
    bid = item["id"]
    _active_id = bid
    _builds[bid] = {"status": "running", "message": "Analysing JD…", "hint": item.get("hint", ""), "started": time.time()}
    try:
        from graph.db import init_db
        from graph.schema import create_schema
        from resume_builder.pipeline import run_pipeline
        conn = init_db(); create_schema(conn)
        _builds[bid]["message"] = "Building resume…"
        result = run_pipeline(item["jd"], compile_pdf=True, generate_cover=True)
        if result.get("error"):
            _builds[bid].update({"status": "error", "message": f"Rejected: {result['error']}"})
        else:
            company = result.get("jd_analysis", {}).get("company_name", "Unknown")
            pages   = result.get("page_check", "?")
            _builds[bid].update({"status": "done", "message": f"Done · {pages}", "company": company})
    except Exception as e:
        _builds[bid].update({"status": "error", "message": str(e)[:180]})
    finally:
        _active_id = None


def _queue_worker() -> None:
    while True:
        if not _gen_paused:
            with _q_lock:
                item = _queue.pop(0) if _queue else None
            if item:
                _run_one(item)
        time.sleep(2)


threading.Thread(target=_queue_worker, daemon=True).start()


# ── HTML helpers ──────────────────────────────────────────────────────────────
def _esc(s: str) -> str:
    return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def _resume_exists(company: str) -> bool:
    from resume_builder.utils import sanitize_filename
    return (Path("output")/"resumes"/f"Pratham_Saraf_Resume_{sanitize_filename(company)}.pdf").exists()

def _cover_exists(company: str) -> bool:
    from resume_builder.utils import sanitize_filename
    return (Path("output")/"cover_letters"/f"Pratham_Saraf_CoverLetter_{sanitize_filename(company)}.pdf").exists()


# ── CSS ───────────────────────────────────────────────────────────────────────
_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=JetBrains+Mono:wght@400;500;700&display=swap');
:root {
  --bg:#F5F0E8; --sf:#FFFFFF; --sf2:#EDE8DF;
  --bd:rgba(31,18,6,0.10); --bds:rgba(31,18,6,0.18);
  --ac:#C85C20; --ac-sf:rgba(200,92,32,0.10);
  --gr:#1E7A3E; --gr-sf:rgba(30,122,62,0.10);
  --bl:#1A5FA8; --bl-sf:rgba(26,95,168,0.10);
  --am:#A86800; --rd:#B83030;
  --tx:#0F0A04; --t2:rgba(26,18,8,0.78); --t3:rgba(26,18,8,0.58);
  --t4:rgba(26,18,8,0.40); --t5:rgba(26,18,8,0.22);
  --fd:'Playfair Display',Georgia,serif; --fm:'JetBrains Mono',monospace;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{color-scheme:light;-webkit-font-smoothing:antialiased}
body{background:var(--bg);color:var(--tx);font-family:var(--fm);font-size:13px;
  line-height:1.5;min-height:100vh;
  background-image:linear-gradient(rgba(31,18,6,0.04) 1px,transparent 1px),
    linear-gradient(90deg,rgba(31,18,6,0.04) 1px,transparent 1px);
  background-size:52px 52px}

/* refresh bar */
.rbar{position:fixed;top:0;left:0;right:0;height:2px;background:var(--t5);z-index:100}
.rfill{height:100%;background:linear-gradient(90deg,var(--ac),var(--am));
  animation:countdown 20s linear forwards}
@keyframes countdown{from{width:100%}to{width:0%}}

.shell{max-width:1380px;margin:0 auto;padding:48px 28px 80px}

/* header */
.hdr{display:flex;align-items:flex-end;justify-content:space-between;
  gap:24px;margin-bottom:0;padding-bottom:22px;border-bottom:1px solid var(--bds)}
.hdr-ey{font-size:10px;letter-spacing:.22em;text-transform:uppercase;color:var(--ac);margin-bottom:8px}
.hdr-t{font-family:var(--fd);font-size:38px;font-weight:700;line-height:1;
  letter-spacing:-.02em;color:var(--tx)}
.hdr-meta{margin-top:11px;color:var(--t3);font-size:11px;letter-spacing:.04em;
  display:flex;gap:18px;flex-wrap:wrap}
.hdr-mi::before{content:"→ ";color:var(--ac);opacity:.65}
.hdr-r{text-align:right;color:var(--t3);font-size:11px;letter-spacing:.04em;flex-shrink:0;line-height:1.75}
.hdr-rl{font-size:9px;letter-spacing:.18em;text-transform:uppercase;color:var(--ac);
  margin-bottom:5px;font-weight:600;display:block}
.hdr-acts{display:flex;align-items:center;gap:10px;margin-top:10px}

/* tabs */
.tabs{display:flex;gap:2px;margin:22px 0 28px;border-bottom:1px solid var(--bd)}
.tab{padding:9px 18px;font-family:var(--fm);font-size:11px;font-weight:700;
  letter-spacing:.08em;text-transform:uppercase;cursor:pointer;
  border:none;background:none;color:var(--t3);border-bottom:2px solid transparent;
  margin-bottom:-1px;transition:color .15s,border-color .15s}
.tab:hover{color:var(--tx)}
.tab.active{color:var(--ac);border-bottom-color:var(--ac)}
.tabp{display:none}.tabp.active{display:block}

/* stat cards */
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:22px}
.sc{background:var(--sf);border:1px solid var(--bd);border-radius:8px;
  padding:18px 16px;position:relative;overflow:hidden;animation:up .4s ease both}
.sc::before{content:"";position:absolute;top:0;left:0;right:0;height:2px}
.sc.ct::before{background:var(--t5)}.sc.cn::before{background:var(--bl)}
.sc.ce::before{background:var(--gr)}.sc.cs::before{background:var(--t5)}
.sc:nth-child(1){animation-delay:.05s}.sc:nth-child(2){animation-delay:.10s}
.sc:nth-child(3){animation-delay:.15s}.sc:nth-child(4){animation-delay:.20s}
.sn{font-size:42px;font-weight:700;line-height:1;letter-spacing:-.05em;margin-bottom:6px}
.sc.cn .sn{color:var(--bl)}.sc.ce .sn{color:var(--gr)}.sc.ct .sn,.sc.cs .sn{color:var(--t2)}
.sl{font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--t3);font-weight:600}

/* two-col layout */
.row2{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:22px}
@media(max-width:860px){.row2{grid-template-columns:1fr}}

/* cards */
.card{background:var(--sf);border:1px solid var(--bd);border-radius:8px;padding:20px 18px}
.card-ey{font-size:9px;letter-spacing:.2em;text-transform:uppercase;color:var(--t4);
  font-weight:700;margin-bottom:12px;display:flex;align-items:center;gap:8px}
.card-t{font-family:var(--fd);font-size:16px;font-weight:700;color:var(--tx);
  margin-bottom:4px;letter-spacing:-.01em}
.card-sub{font-size:11px;color:var(--t3);margin-bottom:16px}

/* status dot */
.dot{width:7px;height:7px;border-radius:50%;display:inline-block;flex-shrink:0}
.dot-gr{background:var(--gr)}.dot-rd{background:var(--rd)}
.dot-am{background:var(--am);animation:pulse .9s infinite alternate}
.dot-muted{background:var(--t5)}
@keyframes pulse{from{opacity:.5}to{opacity:1}}

/* active build progress */
.abuild{padding:14px 0 0}
.abuild-co{font-size:14px;font-weight:700;color:var(--tx);margin-bottom:3px}
.abuild-msg{font-size:11px;color:var(--t3);margin-bottom:12px}
.abuild-bar{height:3px;background:var(--t5);border-radius:2px;overflow:hidden;margin-bottom:8px}
.abuild-fill{height:100%;background:linear-gradient(90deg,var(--ac),var(--am));
  border-radius:2px;animation:indeterminate 1.6s ease-in-out infinite}
@keyframes indeterminate{
  0%{width:0%;margin-left:0}50%{width:60%;margin-left:20%}100%{width:0%;margin-left:100%}}
.abuild-elapsed{font-size:10px;color:var(--t4);letter-spacing:.04em}
.abuild-idle{font-size:11px;color:var(--t4);padding:18px 0;text-align:center;
  letter-spacing:.08em;text-transform:uppercase}

/* scraper controls */
.sctrl{display:flex;align-items:center;gap:10px;margin-bottom:14px}
.sctrl-label{font-size:12px;color:var(--t2);flex:1}
.sctrl-status{font-size:10px;letter-spacing:.1em;text-transform:uppercase;font-weight:700}
.sctrl-status.on{color:var(--gr)}.sctrl-status.off{color:var(--t4)}
.ctl-btn{padding:7px 14px;border-radius:5px;font-family:var(--fm);font-size:10px;
  font-weight:700;letter-spacing:.10em;text-transform:uppercase;cursor:pointer;
  border:1px solid var(--bd);background:var(--sf2);color:var(--t2);
  transition:background .12s,color .12s,border-color .12s}
.ctl-btn:hover{background:var(--ac);color:#fff;border-color:var(--ac)}
.ctl-btn.danger:hover{background:var(--rd);border-color:var(--rd);color:#fff}
.ctl-btn.primary{background:var(--ac);color:#fff;border-color:var(--ac)}
.ctl-btn.primary:hover{opacity:.85}

/* queue list */
.qlist{display:flex;flex-direction:column;gap:6px;margin-top:4px}
.qi{display:flex;align-items:center;gap:10px;padding:10px 12px;
  background:var(--sf2);border:1px solid var(--bd);border-radius:6px;
  animation:row-in .2s ease both}
.qi-num{font-size:10px;color:var(--t4);font-weight:700;width:18px;text-align:right;flex-shrink:0}
.qi-info{flex:1;min-width:0}
.qi-hint{font-size:12px;font-weight:700;color:var(--tx);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.qi-jd{font-size:10px;color:var(--t4);margin-top:1px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.qi-acts{display:flex;gap:6px;flex-shrink:0}
.qi-btn{padding:3px 8px;font-size:9px;letter-spacing:.08em;text-transform:uppercase;
  font-family:var(--fm);font-weight:700;cursor:pointer;border-radius:3px;
  border:1px solid var(--bd);background:none;color:var(--t3);transition:all .12s}
.qi-btn:hover{background:var(--rd);border-color:var(--rd);color:#fff}
.qi-btn.up:hover{background:var(--bl);border-color:var(--bl);color:#fff}
.qi-empty{font-size:10px;color:var(--t4);letter-spacing:.12em;
  text-transform:uppercase;padding:20px;text-align:center}

/* platform pills */
.plats{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:32px;align-items:center}
.plats-l{font-size:9px;letter-spacing:.2em;text-transform:uppercase;color:var(--t4);margin-right:4px}
.plat{background:var(--sf2);border:1px solid var(--bd);border-radius:4px;
  padding:4px 12px;font-size:12px;color:var(--t2);letter-spacing:.02em}
.plat b{color:var(--tx);font-weight:700;margin-left:5px}

/* sections */
.sec{margin-bottom:32px}
.sech{display:flex;align-items:center;gap:12px;margin-bottom:10px;cursor:pointer;user-select:none}
.sech:hover .sect{color:var(--tx)}
.secbar{width:3px;height:18px;border-radius:2px;flex-shrink:0}
.sec-nw .secbar{background:var(--bl)}.sec-em .secbar{background:var(--gr)}.sec-sk .secbar{background:var(--t5)}
.sect{font-family:var(--fd);font-size:15px;font-weight:700;color:var(--t2);
  letter-spacing:-.01em;transition:color .15s}
.secc{background:var(--sf2);border:1px solid var(--bd);border-radius:4px;
  padding:1px 8px;font-size:9.5px;color:var(--t3);font-weight:700;letter-spacing:.06em}
.secv{margin-left:auto;color:var(--t4);font-size:15px;
  transition:transform .22s ease;display:inline-block;line-height:1}
.secv.open{transform:rotate(90deg)}
.secbd{overflow:hidden;transition:max-height .3s ease;max-height:9999px}

/* data grid */
.dg{background:var(--sf);border:1px solid var(--bd);border-radius:8px;overflow:hidden;overflow-x:auto}
.dgh{display:grid;
  grid-template-columns:44px minmax(180px,1fr) 92px 76px minmax(100px,.65fr) 92px 72px 80px;
  padding:9px 16px;border-bottom:1px solid var(--bd);background:var(--sf2)}
.dgh span{font-size:10px;letter-spacing:.12em;text-transform:uppercase;
  color:var(--t3);font-weight:700;padding:0 6px}
.dgh span:first-child{padding-left:0}
.dgr{display:grid;
  grid-template-columns:44px minmax(180px,1fr) 92px 76px minmax(100px,.65fr) 92px 72px 80px;
  padding:10px 16px;border-bottom:1px solid var(--bd);
  align-items:center;transition:background .12s;animation:row-in .25s ease both}
.dgr:last-child{border-bottom:none}
.dgr:hover{background:rgba(31,18,6,0.03)}
.gc{padding:0 6px;min-width:0;overflow:hidden}
.gc:first-child{padding-left:0}
.jt{font-size:12.5px;font-weight:700;color:var(--tx);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;letter-spacing:-.01em}
.jco{font-size:12px;color:var(--t3);margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.jpl{font-size:12px;color:var(--t2)}.jdt{font-size:12px;color:var(--t3)}
.jrs{font-size:12px;color:var(--t2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.jdc{font-size:11px;font-weight:700;letter-spacing:.04em}
.jdc.y{color:var(--gr)}.jdc.n{color:var(--t5)}
.apla{display:inline-flex;align-items:center;gap:3px;padding:4px 10px;
  background:var(--ac-sf);border:1px solid rgba(200,92,32,0.28);border-radius:4px;
  color:var(--ac);font-size:9.5px;font-weight:700;text-decoration:none;
  letter-spacing:.08em;text-transform:uppercase;transition:background .12s;
  white-space:nowrap;font-family:var(--fm)}
.apla:hover{background:rgba(200,92,32,0.22);border-color:var(--ac)}
.empty{padding:40px;text-align:center;color:var(--t4);font-size:10px;letter-spacing:.14em;text-transform:uppercase}
.bdg{display:inline-flex;align-items:center;padding:4px 9px;border-radius:4px;
  font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase}
.bnw{background:var(--bl-sf);color:var(--bl);border:1px solid rgba(26,95,168,0.25)}
.bap{background:var(--gr-sf);color:var(--gr);border:1px solid rgba(30,122,62,0.25)}
.bsk{background:rgba(31,18,6,0.05);color:var(--t3);border:1px solid var(--bd)}
.ber{background:rgba(200,40,40,0.08);color:var(--rd);border:1px solid rgba(200,40,40,0.22)}

/* build btn */
.build-btn{display:inline-flex;align-items:center;gap:7px;padding:8px 16px;
  background:var(--ac);color:#fff;border:none;border-radius:6px;font-family:var(--fm);
  font-size:11px;font-weight:700;letter-spacing:.10em;text-transform:uppercase;cursor:pointer;
  transition:opacity .15s,transform .12s}
.build-btn:hover{opacity:.88;transform:translateY(-1px)}

/* modal */
.modal-ov{display:none;position:fixed;inset:0;background:rgba(15,10,4,0.50);
  backdrop-filter:blur(3px);z-index:200;align-items:center;justify-content:center}
.modal-ov.open{display:flex}
.modal{background:var(--sf);border:1px solid var(--bds);border-radius:10px;
  padding:28px 24px;width:620px;max-width:95vw;
  box-shadow:0 16px 48px rgba(15,10,4,0.14);animation:modal-in .22s ease}
@keyframes modal-in{from{opacity:0;transform:translateY(10px) scale(.98)}to{opacity:1;transform:none}}
.modal-ey{font-size:9px;letter-spacing:.22em;text-transform:uppercase;color:var(--ac);margin-bottom:8px}
.modal-title{font-family:var(--fd);font-size:20px;font-weight:700;color:var(--tx);
  margin-bottom:14px;letter-spacing:-.01em}
.modal-hint{width:100%;padding:8px 12px;background:var(--sf2);border:1px solid var(--bd);
  border-radius:5px;color:var(--tx);font-family:var(--fm);font-size:12px;outline:none;
  margin-bottom:10px;transition:border-color .15s}
.modal-hint:focus{border-color:var(--ac)}
.modal-ta{width:100%;height:200px;padding:11px 12px;background:var(--sf2);
  border:1px solid var(--bd);border-radius:5px;color:var(--tx);font-family:var(--fm);
  font-size:12px;line-height:1.55;resize:vertical;outline:none;transition:border-color .15s}
.modal-ta:focus{border-color:var(--ac)}
.modal-ta::placeholder,.modal-hint::placeholder{color:var(--t4)}
.modal-actions{display:flex;align-items:center;justify-content:space-between;margin-top:14px}
.modal-cancel{background:none;border:none;color:var(--t3);font-family:var(--fm);
  font-size:11px;letter-spacing:.06em;cursor:pointer;padding:8px 0;transition:color .12s}
.modal-cancel:hover{color:var(--tx)}
.modal-status{font-size:11px;color:var(--t3);letter-spacing:.04em;flex:1;text-align:center;padding:0 10px}
.modal-status.ok{color:var(--gr)}.modal-status.err{color:var(--rd)}.modal-status.run{color:var(--am)}

/* toast */
.toast{position:fixed;bottom:24px;right:24px;z-index:300;background:var(--tx);color:var(--bg);
  padding:11px 18px;border-radius:6px;font-size:12px;font-weight:600;letter-spacing:.03em;
  box-shadow:0 4px 20px rgba(15,10,4,0.18);animation:toast-in .25s ease;max-width:300px}
.toast.hidden{display:none}
@keyframes toast-in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}

/* footer */
.footer{margin-top:60px;padding-top:18px;border-top:1px solid var(--bd);
  display:flex;justify-content:space-between;font-size:10px;color:var(--t4);letter-spacing:.08em}

/* anims */
@keyframes up{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@keyframes row-in{from{opacity:0}to{opacity:1}}
::-webkit-scrollbar{width:4px;height:4px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(200,92,32,0.20);border-radius:2px}
::-webkit-scrollbar-thumb:hover{background:rgba(200,92,32,0.38)}
"""

# ── JS ────────────────────────────────────────────────────────────────────────
_JS = """
// ── Tabs ─────────────────────────────────────────────────────────────────────
function switchTab(t) {
  document.querySelectorAll('.tab').forEach(function(b){ b.classList.toggle('active', b.dataset.tab===t); });
  document.querySelectorAll('.tabp').forEach(function(p){ p.classList.toggle('active', p.id==='tab-'+t); });
  try { localStorage.setItem('activeTab', t); } catch(e) {}
}
(function() {
  var saved = localStorage.getItem('activeTab');
  if (saved && saved !== 'overview') switchTab(saved);
})();

// ── Scraper / gen controls ────────────────────────────────────────────────────
function ctlScraper(action) {
  fetch('/api/scraper/' + action, {method:'POST'}).then(function(){ setTimeout(pollOverview, 400); });
}
function ctlGen() {
  fetch('/api/generation/toggle', {method:'POST'}).then(function(){ setTimeout(pollOverview, 400); });
}

// ── Sections collapse ─────────────────────────────────────────────────────────
document.querySelectorAll('.sech').forEach(function(hdr) {
  var body = hdr.nextElementSibling;
  var chev = hdr.querySelector('.secv');
  chev.classList.add('open');
  hdr.addEventListener('click', function() {
    var isOpen = body.style.maxHeight !== '0px';
    if (isOpen) {
      body.style.maxHeight = body.scrollHeight + 'px';
      requestAnimationFrame(function(){ body.style.maxHeight = '0px'; });
    } else {
      body.style.maxHeight = body.scrollHeight + 'px';
      setTimeout(function(){ body.style.maxHeight = '9999px'; }, 310);
    }
    chev.classList.toggle('open', !isOpen);
  });
});
document.querySelectorAll('.dgr').forEach(function(row, i) { row.style.animationDelay = (i * 0.025) + 's'; });

// ── Overview live poll ────────────────────────────────────────────────────────
function pollOverview() {
  fetch('/api/overview').then(function(r){ return r.json(); }).then(function(d) {
    // scraper
    var sdot = document.getElementById('scraper-dot');
    var slbl = document.getElementById('scraper-lbl');
    var sstart = document.getElementById('scraper-start');
    var sstop  = document.getElementById('scraper-stop');
    if (sdot && slbl) {
      sdot.className = 'dot ' + (d.scraper ? 'dot-gr' : 'dot-muted');
      slbl.textContent = d.scraper ? 'Running' : 'Stopped';
      slbl.className = 'sctrl-status ' + (d.scraper ? 'on' : 'off');
      if (sstart) sstart.style.display = d.scraper ? 'none' : '';
      if (sstop)  sstop.style.display  = d.scraper ? '' : 'none';
    }
    // gen status dot (eyebrow on active build card)
    var gsdot = document.getElementById('gen-status-dot');
    if (gsdot) gsdot.className = 'dot ' + (d.gen_paused ? 'dot-muted' : (d.active ? 'dot-am' : 'dot-gr'));
    // gen pause controls
    var pdot = document.getElementById('gen-dot');
    var plbl = document.getElementById('gen-lbl');
    var pbtn = document.getElementById('gen-pause');
    if (pdot && plbl) {
      pdot.className = 'dot ' + (d.gen_paused ? 'dot-muted' : (d.active ? 'dot-am' : 'dot-gr'));
      plbl.textContent = d.gen_paused ? 'Paused' : (d.active ? 'Building…' : 'Idle');
      plbl.className = 'sctrl-status ' + (d.gen_paused ? 'off' : 'on');
      if (pbtn) pbtn.textContent = d.gen_paused ? 'Resume' : 'Pause';
    }
    // active build
    var ab = document.getElementById('active-build');
    if (ab) {
      if (d.active) {
        var elapsed = d.active.elapsed ? Math.round(d.active.elapsed) + 's' : '';
        ab.innerHTML =
          '<div class="abuild-co">' + (d.active.company || d.active.hint || 'Building…') + '</div>' +
          '<div class="abuild-msg">' + (d.active.message||'') + '</div>' +
          '<div class="abuild-bar"><div class="abuild-fill"></div></div>' +
          '<div class="abuild-elapsed">Elapsed: ' + elapsed + '</div>';
      } else {
        ab.innerHTML = '<div class="abuild-idle">No active build</div>';
      }
    }
    // queue
    var ql = document.getElementById('queue-list');
    if (ql) {
      if (!d.queue || d.queue.length === 0) {
        ql.innerHTML = '<div class="qi-empty">Queue is empty</div>';
      } else {
        ql.innerHTML = d.queue.map(function(item, i) {
          return '<div class="qi" data-id="'+item.id+'">' +
            '<span class="qi-num">'+(i+1)+'</span>' +
            '<div class="qi-info">' +
              '<div class="qi-hint">'+(item.hint||'Untitled JD')+'</div>' +
              '<div class="qi-jd">'+(item.jd||'').substring(0,80)+'…</div>' +
            '</div>' +
            '<div class="qi-acts">' +
              (i > 0 ? '<button class="qi-btn up" onclick="qMove(\\\''+item.id+'\\\',\\'up\\')">↑</button>' : '') +
              '<button class="qi-btn" onclick="qRemove(\\\''+item.id+'\\\')">✕</button>' +
            '</div>' +
          '</div>';
        }).join('');
      }
    }
  }).catch(function(){});
}
setInterval(pollOverview, 2500);
pollOverview();

function qMove(id, dir) {
  fetch('/api/queue/move', {method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:id,dir:dir})}).then(pollOverview);
}
function qRemove(id) {
  fetch('/api/queue/remove', {method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:id})}).then(pollOverview);
}
// ── Build modal ───────────────────────────────────────────────────────────────
var overlay  = document.getElementById('build-overlay');
var runBtn   = document.getElementById('build-run');
var statusEl = document.getElementById('build-status');
var toast    = document.getElementById('build-toast');

function openModal() { if(overlay) overlay.classList.add('open'); }
function closeModal() { if(overlay) overlay.classList.remove('open'); }
if(overlay) overlay.addEventListener('click', function(e){ if(e.target===overlay) closeModal(); });
document.addEventListener('keydown', function(e){ if(e.key==='Escape') closeModal(); });

function submitBuild() {
  var jd   = document.getElementById('build-ta').value.trim();
  var hint = document.getElementById('build-hint').value.trim();
  if (!jd) { statusEl.textContent='Paste a JD first.'; statusEl.className='modal-status err'; return; }
  runBtn.disabled=true; runBtn.textContent='Queued…';
  statusEl.textContent='Adding to queue…'; statusEl.className='modal-status run';
  fetch('/api/build',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({jd:jd,hint:hint})})
  .then(function(r){return r.json();})
  .then(function(d){
    statusEl.textContent='Added to queue (#'+(d.position||'?')+')';
    statusEl.className='modal-status ok';
    runBtn.disabled=false; runBtn.textContent='Add to Queue';
    showToast('Added to queue'+(hint?' — '+hint:''));
    pollOverview();
  })
  .catch(function(e){
    statusEl.textContent='Error: '+e; statusEl.className='modal-status err';
    runBtn.disabled=false; runBtn.textContent='Add to Queue';
  });
}

function showToast(msg) {
  toast.textContent=msg; toast.classList.remove('hidden');
  setTimeout(function(){ toast.classList.add('hidden'); }, 4500);
}
"""


# ── Render helpers ────────────────────────────────────────────────────────────
def _badge(status: str) -> str:
    m = {"new":("bnw","New"),"applied":("bap","Emailed"),"skip":("bsk","Skipped"),"error":("ber","Error")}
    cls, label = m.get(status, ("bsk", status.title()))
    return f'<span class="bdg {cls}">{label}</span>'


def _score_arc(score: int) -> str:
    circ = 81.68; dash = (score/100)*circ; gap = circ-dash
    color = "#A86800" if score>=85 else "#1A5FA8" if score>=65 else "rgba(26,18,8,0.20)"
    return (
        f'<svg width="34" height="34" viewBox="0 0 36 36" style="display:block">'
        f'<circle cx="18" cy="18" r="13" fill="none" stroke="rgba(26,18,8,0.08)" stroke-width="2.5"/>'
        f'<circle cx="18" cy="18" r="13" fill="none" stroke="{color}" stroke-width="2.5"'
        f' stroke-dasharray="{dash:.1f} {gap:.1f}" stroke-linecap="round" transform="rotate(-90 18 18)"/>'
        f'<text x="18" y="22" text-anchor="middle" fill="{color}"'
        f' font-size="9" font-family="JetBrains Mono,monospace" font-weight="700">{score}</text>'
        f'</svg>'
    )


def _jobs_grid(jobs: list[dict]) -> str:
    if not jobs:
        return '<div class="empty">No jobs</div>'
    rows = []
    for j in jobs:
        co=_esc(j.get("company",""));ti=_esc(j.get("title",""))
        pl=_esc(j.get("platform","—"));dt=(j.get("posted_date") or "")[:10] or "—"
        sc=j.get("score",0);st=j.get("status","new")
        url=_esc(j.get("url",""));rs=_esc(j.get("score_reason",""))
        rr="y" if _resume_exists(j.get("company","")) else "n"
        cr="y" if _cover_exists(j.get("company","")) else "n"
        rs_sym="&#x2713;" if rr=="y" else "&mdash;"; cs_sym="&#x2713;" if cr=="y" else "&mdash;"
        docs=f'<span class="jdc {rr}">R{rs_sym}</span>&nbsp;<span class="jdc {cr}">C{cs_sym}</span>'
        apply=f'<a href="{url}" target="_blank" class="apla">Apply &#x2197;</a>' if url else ""
        rows.append(
            f'<div class="dgr">'
            f'<div class="gc">{_score_arc(sc)}</div>'
            f'<div class="gc"><div class="jt" title="{ti}">{ti}</div><div class="jco">{co}</div></div>'
            f'<div class="gc"><span class="jpl">{pl}</span></div>'
            f'<div class="gc"><span class="jdt">{dt}</span></div>'
            f'<div class="gc"><span class="jrs" title="{rs}">{rs}</span></div>'
            f'<div class="gc">{_badge(st)}</div>'
            f'<div class="gc" style="white-space:nowrap">{docs}</div>'
            f'<div class="gc">{apply}</div>'
            f'</div>'
        )
    hdr=(
        '<div class="dgh"><span></span><span>Role / Company</span><span>Source</span>'
        '<span>Posted</span><span>Match</span><span>Status</span><span>Docs</span><span></span></div>'
    )
    return f'<div class="dg">{hdr}{"".join(rows)}</div>'


def _render_page() -> str:
    s=stats(); by_status=s.get("by_status",{}); total=s.get("total",0)
    all_jobs=list_jobs(limit=200)
    new_jobs=[j for j in all_jobs if j["status"]=="new"]
    applied =[j for j in all_jobs if j["status"]=="applied"]
    skipped =[j for j in all_jobs if j["status"] in ("skip","error")]
    nc=by_status.get("new",0); ec=by_status.get("applied",0)
    sc_n=by_status.get("skip",0)+by_status.get("error",0)
    plats=s.get("by_platform",{})
    plat_pills=" ".join(f'<span class="plat">{_esc(p)}<b>{c}</b></span>' for p,c in sorted(plats.items(),key=lambda x:-x[1])) or '<span class="plat">none yet</span>'

    stat_cards=(
        f'<div class="sc ct"><div class="sn">{total}</div><div class="sl">Total</div></div>'
        f'<div class="sc cn"><div class="sn">{nc}</div><div class="sl">New · Queued</div></div>'
        f'<div class="sc ce"><div class="sn">{ec}</div><div class="sl">Emailed</div></div>'
        f'<div class="sc cs"><div class="sn">{sc_n}</div><div class="sl">Skipped</div></div>'
    )

    def sec(title, jobs, cls):
        if not jobs: return ""
        return (
            f'<div class="sec {cls}"><div class="sech">'
            f'<div class="secbar"></div><span class="sect">{title}</span>'
            f'<span class="secc">{len(jobs)}</span><span class="secv">&#x203A;</span>'
            f'</div><div class="secbd">{_jobs_grid(jobs)}</div></div>'
        )

    jobs_tab=(
        f'<div class="plats"><span class="plats-l">Sources</span>{plat_pills}</div>'
        + sec("New &mdash; Queued for Resume Build", new_jobs, "sec-nw")
        + sec("Emailed", applied, "sec-em")
        + sec("Skipped / Error", skipped, "sec-sk")
    )

    scraper_on = _scraper_running()
    scan_mins  = config.SCAN_INTERVAL_SECONDS // 60

    overview_tab = (
        f'<div class="stats">{stat_cards}</div>'
        f'<div class="row2">'

        # ── Active Build card
        f'<div class="card">'
        f'<div class="card-ey"><span class="dot dot-am" id="gen-status-dot"></span>&nbsp;Resume Generator</div>'
        f'<div class="card-t">Active Build</div>'
        f'<div class="card-sub">Currently generating</div>'
        f'<div id="active-build"><div class="abuild-idle">Loading&#8230;</div></div>'
        f'</div>'

        # ── Controls card
        f'<div class="card">'
        f'<div class="card-ey">Controls</div>'
        f'<div class="card-t">System</div>'
        f'<div class="card-sub">Manage scraper and generator</div>'

        f'<div class="sctrl">'
        f'<span class="dot {"dot-gr" if scraper_on else "dot-muted"}" id="scraper-dot"></span>'
        f'<span class="sctrl-label">Job Scraper &nbsp;<small style="color:var(--t4)">every {scan_mins}m</small></span>'
        f'<span class="sctrl-status {"on" if scraper_on else "off"}" id="scraper-lbl">{"Running" if scraper_on else "Stopped"}</span>'
        f'<button class="ctl-btn" id="scraper-start" onclick="ctlScraper(\'start\')" style="{"display:none" if scraper_on else ""}">Start</button>'
        f'<button class="ctl-btn danger" id="scraper-stop" onclick="ctlScraper(\'stop\')" style="{"" if scraper_on else "display:none"}">Stop</button>'
        f'</div>'

        f'<div class="sctrl" style="margin-top:10px">'
        f'<span class="dot {"dot-muted" if _gen_paused else "dot-gr"}" id="gen-dot"></span>'
        f'<span class="sctrl-label">Resume Generator</span>'
        f'<span class="sctrl-status {"off" if _gen_paused else "on"}" id="gen-lbl">{"Paused" if _gen_paused else "Idle"}</span>'
        f'<button class="ctl-btn" id="gen-pause" onclick="ctlGen()">{"Resume" if _gen_paused else "Pause"}</button>'
        f'</div>'
        f'</div>'  # end card
        f'</div>'  # end row2

        # ── Queue
        f'<div class="card" style="margin-top:14px">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">'
        f'<div>'
        f'<div class="card-ey" style="margin-bottom:4px">Generation Queue</div>'
        f'<div class="card-t">Pending Builds</div>'
        f'</div>'
        f'<button class="build-btn" id="build-open" onclick="openModal()">&#x2b;&nbsp;Add JD</button>'
        f'</div>'
        f'<div id="queue-list"><div class="qi-empty">Loading…</div></div>'
        f'</div>'
    )

    return (
        f'<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        f'  <meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f'  <meta http-equiv="refresh" content="20">\n'
        f'  <title>Jobs Auto Scanner</title>\n'
        f'  <style>{_CSS}</style>\n'
        f'</head>\n<body>\n'
        f'  <div class="rbar"><div class="rfill"></div></div>\n'
        f'  <div class="shell">\n'

        f'    <header class="hdr">\n'
        f'      <div>\n'
        f'        <div class="hdr-ey">Auto Scanner &middot; Live</div>\n'
        f'        <h1 class="hdr-t">Job Hunt</h1>\n'
        f'        <div class="hdr-meta">\n'
        f'          <span class="hdr-mi">Refresh 20s</span>\n'
        f'          <span class="hdr-mi">Score &ge; {config.MIN_SCORE_TO_EMAIL}</span>\n'
        f'          <span class="hdr-mi">Cap {config.DB_KEEP_TOP}</span>\n'
        f'        </div>\n'
        f'      </div>\n'
        f'      <div class="hdr-r">\n'
        f'        <span class="hdr-rl">Destination</span>\n'
        f'        {_esc(config.GMAIL_RECIPIENT)}\n'
        f'      </div>\n'
        f'    </header>\n'

        f'    <nav class="tabs">\n'
        f'      <button class="tab active" data-tab="overview" onclick="switchTab(\'overview\')">Overview</button>\n'
        f'      <button class="tab" data-tab="jobs" onclick="switchTab(\'jobs\')">Jobs ({total})</button>\n'
        f'    </nav>\n'

        f'    <div class="tabp active" id="tab-overview">{overview_tab}</div>\n'
        f'    <div class="tabp" id="tab-jobs">{jobs_tab}</div>\n'

        f'    <footer class="footer">\n'
        f'      <span>Jobs Auto Scanner</span>\n'
        f'      <span>Auto-refreshes every 20s</span>\n'
        f'    </footer>\n'
        f'  </div>\n'

        f'  <div class="modal-ov" id="build-overlay">\n'
        f'    <div class="modal">\n'
        f'      <div class="modal-ey">Resume Builder</div>\n'
        f'      <div class="modal-title">Add Job to Queue</div>\n'
        f'      <input class="modal-hint" id="build-hint" placeholder="Company / role hint (optional)">\n'
        f'      <textarea class="modal-ta" id="build-ta" placeholder="Paste the full job description here…"></textarea>\n'
        f'      <div class="modal-actions">\n'
        f'        <button class="modal-cancel" id="build-cancel" onclick="closeModal()">Cancel</button>\n'
        f'        <span class="modal-status" id="build-status"></span>\n'
        f'        <button class="build-btn" id="build-run" onclick="submitBuild()">Add to Queue</button>\n'
        f'      </div>\n'
        f'    </div>\n'
        f'  </div>\n'
        f'  <div class="toast hidden" id="build-toast"></div>\n'
        f'  <script>{_JS}</script>\n'
        f'</body>\n</html>'
    )


# ── HTTP handler ──────────────────────────────────────────────────────────────
class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass

    def _json(self, data: dict, code: int = 200) -> None:
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urlparse(self.path)

        if p.path == "/":
            body = _render_page().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if p.path == "/api/stats":
            self._json(stats()); return

        if p.path == "/api/overview":
            active_info = None
            if _active_id and _active_id in _builds:
                b = _builds[_active_id]
                active_info = {
                    "id": _active_id,
                    "status": b.get("status"),
                    "message": b.get("message"),
                    "company": b.get("company") or b.get("hint", ""),
                    "hint": b.get("hint", ""),
                    "elapsed": round(time.time() - b["started"]) if "started" in b else 0,
                }
            # Merge daemon's active build if dashboard queue is idle
            if not active_info:
                try:
                    sf = Path("data/active_build.json")
                    if sf.exists():
                        d = json.loads(sf.read_text())
                        active_info = {
                            "id": "daemon",
                            "status": "running",
                            "message": d.get("message", "Building…"),
                            "company": d.get("company", ""),
                            "hint": d.get("title", ""),
                            "elapsed": round(time.time() - d["started"]) if "started" in d else 0,
                        }
                except Exception:
                    pass
            with _q_lock:
                queue_snapshot = [{"id": i["id"], "hint": i.get("hint",""), "jd": i["jd"][:60]} for i in _queue]
            self._json({
                "scraper": _scraper_running(),
                "gen_paused": _gen_paused,
                "active": active_info,
                "queue": queue_snapshot,
                "queue_len": len(queue_snapshot),
            }); return

        if p.path == "/api/build/status":
            bid = parse_qs(p.query).get("id", [None])[0]
            self._json(_builds.get(bid, {"status": "unknown", "message": "not found"})); return

        self.send_response(404); self.end_headers()

    def do_POST(self):
        global _gen_paused
        length  = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        p       = self.path

        if p == "/api/build":
            jd   = payload.get("jd", "").strip()
            hint = payload.get("hint", "").strip()
            if not jd:
                self._json({"error": "empty JD"}, 400); return
            bid = uuid.uuid4().hex[:12]
            with _q_lock:
                _queue.append({"id": bid, "jd": jd, "hint": hint, "added": time.time()})
                pos = len(_queue)
            _builds[bid] = {"status": "queued", "message": "Waiting in queue…", "hint": hint}
            self._json({"id": bid, "position": pos}); return

        if p == "/api/scraper/start":
            self._json({"ok": _scraper_start()}); return

        if p == "/api/scraper/stop":
            self._json({"ok": _scraper_stop()}); return

        if p == "/api/generation/toggle":
            _gen_paused = not _gen_paused
            self._json({"paused": _gen_paused}); return

        if p == "/api/queue/remove":
            bid = payload.get("id")
            with _q_lock:
                before = len(_queue)
                _queue[:] = [i for i in _queue if i["id"] != bid]
            self._json({"removed": len(_queue) < before}); return

        if p == "/api/queue/move":
            bid = payload.get("id"); direction = payload.get("dir", "up")
            with _q_lock:
                idx = next((i for i, x in enumerate(_queue) if x["id"] == bid), None)
                if idx is not None:
                    new_idx = max(0, idx-1) if direction == "up" else min(len(_queue)-1, idx+1)
                    _queue.insert(new_idx, _queue.pop(idx))
            self._json({"ok": True}); return

        self.send_response(404); self.end_headers()


def run_dashboard(port: int = PORT) -> None:
    server = HTTPServer(("", port), _Handler)
    print(f"Dashboard → http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
