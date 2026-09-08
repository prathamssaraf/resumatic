"""
Dashboard for jobs-auto-scanner (scan-only).
Run: uv run python main.py dashboard  →  http://localhost:8765
"""
from __future__ import annotations
import json, os, signal, subprocess, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

import config
from job_scanner.store import list_jobs, stats, update_status
from job_scanner.xr_store import list_xr_jobs, xr_stats

# ── Google XR tracker state (completely separate feature — own table, own
# scraper, no LLM, no daemon involvement; a scan only runs when triggered from
# this tab's Refresh button, in a background thread) ───────────────────────────
_xr_scanning = False

PORT       = 8765
_PID_FILE  = Path("data/daemon.pid")


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


# ── Google XR tracker: background scan trigger ─────────────────────────────────
def _xr_scan_start() -> bool:
    """Fire the standalone XR scraper in a background thread. Never touches the
    main `jobs` table, the LLM, or the daemon — fully isolated side effect."""
    global _xr_scanning
    if _xr_scanning:
        return False
    _xr_scanning = True

    def _run():
        global _xr_scanning
        try:
            import asyncio as _asyncio
            from job_scanner.sources.google_xr import scrape_google_xr
            from job_scanner.xr_store import save_xr_jobs
            jobs = _asyncio.run(scrape_google_xr())
            save_xr_jobs(jobs)
        except Exception:
            pass
        finally:
            _xr_scanning = False

    threading.Thread(target=_run, daemon=True).start()
    return True


# ── HTML helpers ──────────────────────────────────────────────────────────────
def _esc(s: str) -> str:
    return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")


def _xr_grid(jobs: list[dict]) -> str:
    """Independent grid renderer for the Google XR tab — deliberately NOT
    reusing _jobs_grid, since that one is wired to the main `jobs` table's
    score/status/mark-applied logic. Same visual language (.dg/.dgr CSS), own
    columns: title/company, location, posted date, link."""
    if not jobs:
        return '<div class="empty">No XR roles tracked yet &mdash; hit Scan Now.</div>'
    rows = []
    for j in jobs:
        title = _esc(j.get("title", "")); loc = _esc(j.get("location", ""))
        dt = (j.get("posted_date") or "")[:10] or "—"
        url = _esc(j.get("url", ""))
        apply = f'<a href="{url}" target="_blank" class="apla">View &#x2197;</a>' if url else ""
        rows.append(
            f'<div class="dgr" data-date="{_esc(j.get("posted_date","") or "")}">'
            f'<div class="gc"><div class="jt" title="{title}">{title}</div><div class="jco">Google</div></div>'
            f'<div class="gc"><span class="jpl">{loc}</span></div>'
            f'<div class="gc"><span class="jdt">{dt}</span></div>'
            f'<div class="gc">{apply}</div>'
            f'</div>'
        )
    hdr = (
        '<div class="dgh" style="grid-template-columns:minmax(220px,1fr) minmax(160px,.9fr) 92px 80px">'
        '<span>Role</span><span>Location</span><span>Posted</span><span></span></div>'
    )
    rows_html = "".join(rows).replace(
        'class="dgr"', 'class="dgr" style="grid-template-columns:minmax(220px,1fr) minmax(160px,.9fr) 92px 80px"'
    )
    return f'<div class="dg" id="xr-grid">{hdr}{rows_html}</div>'




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
  grid-template-columns:44px minmax(180px,1fr) 92px 76px minmax(100px,.6fr) 88px 150px;
  padding:9px 16px;border-bottom:1px solid var(--bd);background:var(--sf2)}
.dgh span{font-size:10px;letter-spacing:.12em;text-transform:uppercase;
  color:var(--t3);font-weight:700;padding:0 6px}
.dgh span:first-child{padding-left:0}
.dgr{display:grid;
  grid-template-columns:44px minmax(180px,1fr) 92px 76px minmax(100px,.6fr) 88px 150px;
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

/* mark applied button */
.mark-applied-btn{padding:4px 10px;border-radius:4px;font-family:var(--fm);font-size:9.5px;
  font-weight:700;letter-spacing:.08em;text-transform:uppercase;cursor:pointer;
  border:1px solid rgba(30,122,62,0.35);background:var(--gr-sf);color:var(--gr);
  transition:background .12s,color .12s,border-color .12s;white-space:nowrap}
.mark-applied-btn:hover{background:var(--gr);color:#fff;border-color:var(--gr)}
.mark-applied-btn:disabled{opacity:.5;cursor:default}
.mark-applied-done{font-size:9.5px;font-weight:700;letter-spacing:.08em;
  text-transform:uppercase;color:var(--gr);white-space:nowrap}

/* sort bar */
.sortbar{display:flex;align-items:center;gap:8px;margin:0 0 10px;flex-wrap:wrap}
.sortbar-l{font-size:9px;letter-spacing:.18em;text-transform:uppercase;color:var(--t4);font-weight:700}
.search-box{flex:1;min-width:180px;max-width:360px;padding:6px 12px;border-radius:5px;
  border:1px solid var(--bd);background:var(--sf);color:var(--tx);font-family:var(--fm);
  font-size:12px;outline:none;transition:border-color .12s}
.search-box:focus{border-color:var(--ac)}
.search-box::placeholder{color:var(--t4)}
.search-count{font-size:10px;color:var(--t4);letter-spacing:.04em;white-space:nowrap}
.sort-btn{padding:5px 12px;border-radius:5px;font-family:var(--fm);font-size:10px;font-weight:700;
  letter-spacing:.08em;text-transform:uppercase;cursor:pointer;border:1px solid var(--bd);
  background:var(--sf2);color:var(--t2);transition:all .12s}
.sort-btn:hover{border-color:var(--ac);color:var(--ac)}
.sort-btn.active{background:var(--ac);color:#fff;border-color:var(--ac)}
.sort-btn .arr{margin-left:5px;opacity:.8}

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

// ── Google XR tracker (fully independent of the main scanner) ─────────────────
function ctlXrScan() {
  var btn = document.getElementById('xr-scan-btn');
  var lbl = document.getElementById('xr-lbl');
  var dot = document.getElementById('xr-dot');
  if (btn) { btn.disabled = true; }
  if (lbl) { lbl.textContent = 'Scanning…'; lbl.className = 'sctrl-status off'; }
  if (dot) { dot.className = 'dot dot-am'; }
  fetch('/api/xr/scan', {method:'POST'}).then(function(){
    var poll = setInterval(function(){
      fetch('/api/xr/status').then(function(r){return r.json();}).then(function(d){
        if (!d.scanning) { clearInterval(poll); window.location.reload(); }
      }).catch(function(){});
    }, 3000);
  });
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
    // tab counts + stat cards
    var tabs = document.querySelectorAll('.tab');
    tabs.forEach(function(t) {
      if (t.dataset.tab === 'approved') t.textContent = 'Approved (' + d.approved_count + ')';
      if (t.dataset.tab === 'rejected') t.textContent = 'Rejected (' + d.rejected_count + ')';
    });
    var cards = document.querySelectorAll('.sc .sn');
    if (cards.length >= 4) {
      cards[0].textContent = d.total;
      cards[1].textContent = d.approved_count;
      cards[2].textContent = d.applied_count;
      cards[3].textContent = d.rejected_count;
    }
  }).catch(function(){});
}
setInterval(pollOverview, 2500);
pollOverview();

var toast = document.getElementById('build-toast');

function showToast(msg) {
  toast.textContent=msg; toast.classList.remove('hidden');
  setTimeout(function(){ toast.classList.add('hidden'); }, 4500);
}

function markApplied(jobId, btn) {
  btn.disabled = true;
  btn.textContent = 'Saving…';
  fetch('/api/job/mark_applied', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:jobId})})
  .then(function(r){ return r.json(); })
  .then(function(d){
    if (d.ok) {
      btn.outerHTML = '<span class="mark-applied-done">&#x2713; Applied</span>';
      showToast('Marked as applied');
    } else {
      btn.disabled = false; btn.textContent = '✓ Mark Applied';
    }
  })
  .catch(function(){ btn.disabled = false; btn.textContent = '✓ Mark Applied'; });
}

// ── Approved-grid sorting (client-side, persisted) ────────────────────────────
function _applySort(gridId, key, dir) {
  var grid = document.getElementById(gridId);
  if (!grid) return;
  var rows = Array.prototype.slice.call(grid.querySelectorAll('.dgr'));
  rows.sort(function(a, b) {
    var va, vb;
    if (key === 'score')      { va = parseFloat(a.dataset.score) || 0; vb = parseFloat(b.dataset.score) || 0; }
    else if (key === 'added') { va = a.dataset.added || ''; vb = b.dataset.added || ''; }
    else                      { va = a.dataset.date || ''; vb = b.dataset.date || ''; }
    if (va < vb) return dir === 'asc' ? -1 : 1;
    if (va > vb) return dir === 'asc' ?  1 : -1;
    return 0;
  });
  rows.forEach(function(r){
    grid.appendChild(r);
    // appendChild re-inserts the row, which can leave its one-shot 'row-in'
    // fade-in animation (opacity 0 -> 1, fill-mode both) stuck at the STARTING
    // keyframe (opacity:0) instead of replaying or holding at the end state —
    // rows then render as fully invisible even though they're in the DOM.
    // Strip the animation and force full opacity so a re-sort can never hide rows.
    r.style.animation = 'none';
    r.style.opacity = '1';
  });
  // Each grid's own sort bar (identified by data-grid) updates independently —
  // separate grids can reuse the same .sort-btn class without stomping on
  // each other's active/label state.
  var labels = {date: 'Date', score: 'Rating', added: 'Added'};
  var bar = document.querySelector('.sortbar[data-grid="' + gridId + '"]');
  if (bar) {
    bar.querySelectorAll('.sort-btn').forEach(function(btn) {
      var active = btn.dataset.key === key;
      btn.classList.toggle('active', active);
      btn.innerHTML = labels[btn.dataset.key] + (active ? '<span class="arr">' + (dir === 'asc' ? '↑' : '↓') + '</span>' : '');
    });
  }
}
function sortGrid(gridId, key) {
  var storeKey = 'sort:' + gridId;
  var saved = {};
  try { saved = JSON.parse(localStorage.getItem(storeKey) || '{}'); } catch(e) {}
  var dir = (saved.key === key && saved.dir === 'desc') ? 'asc' : 'desc';
  _applySort(gridId, key, dir);
  try { localStorage.setItem(storeKey, JSON.stringify({key: key, dir: dir})); } catch(e) {}
}

// ── Per-grid search (client-side, persisted, namespaced by gridId so the
// Approved tab and the Google XR tab never share state) ──────────────────────
function filterGrid(gridId, query) {
  var grid = document.getElementById(gridId);
  if (!grid) return;
  var q = (query || '').trim().toLowerCase();
  var shown = 0, total = 0;
  grid.querySelectorAll('.dgr').forEach(function(row) {
    total++;
    var hit = !q || row.textContent.toLowerCase().indexOf(q) !== -1;
    row.style.display = hit ? '' : 'none';
    if (hit) shown++;
  });
  var lbl = document.getElementById(gridId.replace('-grid','') + '-search-count');
  if (lbl) lbl.textContent = q ? (shown + ' / ' + total + ' match') : '';
  try { localStorage.setItem('search:' + gridId, query || ''); } catch(e) {}
}
function _restoreGridState(gridId, searchInputId, defaultKey, defaultDir) {
  var grid = document.getElementById(gridId);
  if (!grid) return;
  var q = '';
  try { q = localStorage.getItem('search:' + gridId) || ''; } catch(e) {}
  if (q) {
    var box = document.getElementById(searchInputId);
    if (box) { box.value = q; filterGrid(gridId, q); }
  }
  var saved = null;
  try { saved = JSON.parse(localStorage.getItem('sort:' + gridId) || 'null'); } catch(e) {}
  if (!saved) saved = {key: defaultKey, dir: defaultDir};
  _applySort(gridId, saved.key, saved.dir);
}
_restoreGridState('approved-grid', 'approved-search', 'date', 'desc');
_restoreGridState('rejected-grid', 'rejected-search', 'date', 'desc');
_restoreGridState('xr-grid', 'xr-search', 'date', 'desc');
"""


# ── Render helpers ────────────────────────────────────────────────────────────
def _badge(status: str) -> str:
    m = {"approved":("bap","Approved"),"applied":("bnw","Applied"),
         "rejected":("bsk","Rejected"),"skip":("bsk","Skipped"),"error":("ber","Error")}
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


def _jobs_grid(jobs: list[dict], mark_applied: bool = True, grid_id: str = "") -> str:
    if not jobs:
        return '<div class="empty">No jobs</div>'
    rows = []
    for j in jobs:
        co=_esc(j.get("company",""));ti=_esc(j.get("title",""))
        date_raw=(j.get("posted_date") or "")
        pl=_esc(j.get("platform","—"));dt=date_raw[:10] or "—"
        sc=j.get("score",0);st=j.get("status","new")
        jid=j.get("id","")
        url=_esc(j.get("url",""));rs=_esc(j.get("score_reason",""))
        apply=f'<a href="{url}" target="_blank" class="apla">Apply &#x2197;</a>' if url else ""
        if mark_applied and st != "applied":
            mark_btn = f'<button class="mark-applied-btn" onclick="markApplied(\'{jid}\', this)">&#x2713; Mark Applied</button>'
        elif mark_applied and st == "applied":
            mark_btn = '<span class="mark-applied-done">&#x2713; Applied</span>'
        else:
            mark_btn = ""
        actions = f'<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">{apply}{mark_btn}</div>'
        added_raw=_esc(j.get("created_at","") or "")
        rows.append(
            f'<div class="dgr" data-score="{sc}" data-date="{_esc(date_raw)}" data-added="{added_raw}">'
            f'<div class="gc">{_score_arc(sc)}</div>'
            f'<div class="gc"><div class="jt" title="{ti}">{ti}</div><div class="jco">{co}</div></div>'
            f'<div class="gc"><span class="jpl">{pl}</span></div>'
            f'<div class="gc"><span class="jdt">{dt}</span></div>'
            f'<div class="gc"><span class="jrs" title="{rs}">{rs}</span></div>'
            f'<div class="gc">{_badge(st)}</div>'
            f'<div class="gc">{actions}</div>'
            f'</div>'
        )
    hdr=(
        '<div class="dgh"><span></span><span>Role / Company</span><span>Source</span>'
        '<span>Posted</span><span>Match</span><span>Status</span><span></span></div>'
    )
    idattr = f' id="{grid_id}"' if grid_id else ""
    return f'<div class="dg"{idattr}>{hdr}{"".join(rows)}</div>'


def _render_page() -> str:
    s=stats(); by_status=s.get("by_status",{}); total=s.get("total",0)
    # Fetch each status list separately so a view shows a full list, not a slice.
    approved_jobs=list_jobs(status="approved", limit=500)
    applied      =list_jobs(status="applied",  limit=500)
    rejected     =list_jobs(status="rejected", limit=500)
    apc=by_status.get("approved",0); ac=by_status.get("applied",0)
    rc=by_status.get("rejected",0)+by_status.get("skip",0)+by_status.get("error",0)
    plats=s.get("by_platform",{})
    plat_pills=" ".join(f'<span class="plat">{_esc(p)}<b>{c}</b></span>' for p,c in sorted(plats.items(),key=lambda x:-x[1])) or '<span class="plat">none yet</span>'

    stat_cards=(
        f'<div class="sc ct"><div class="sn">{total}</div><div class="sl">Total Screened</div></div>'
        f'<div class="sc ce"><div class="sn">{apc}</div><div class="sl">Approved</div></div>'
        f'<div class="sc cn"><div class="sn">{ac}</div><div class="sl">Applied</div></div>'
        f'<div class="sc cs"><div class="sn">{rc}</div><div class="sl">Rejected</div></div>'
    )

    def sec(title, jobs, cls, grid_id=""):
        if not jobs: return ""
        return (
            f'<div class="sec {cls}"><div class="sech">'
            f'<div class="secbar"></div><span class="sect">{title}</span>'
            f'<span class="secc">{len(jobs)}</span><span class="secv">&#x203A;</span>'
            f'</div><div class="secbd">{_jobs_grid(jobs, grid_id=grid_id)}</div></div>'
        )

    # Sort toolbar for the approved grid (client-side, persisted in localStorage)
    sort_bar = (
        '<div class="sortbar" data-grid="approved-grid">'
        '<input class="search-box" id="approved-search" type="search" '
        'placeholder="Search title, company, location, reason…" '
        'oninput="filterGrid(\'approved-grid\', this.value)">'
        '<span class="search-count" id="approved-search-count"></span>'
        '<span class="sortbar-l">Sort by</span>'
        '<button class="sort-btn" data-key="date" onclick="sortGrid(\'approved-grid\',\'date\')">Date</button>'
        '<button class="sort-btn" data-key="score" onclick="sortGrid(\'approved-grid\',\'score\')">Rating</button>'
        '<button class="sort-btn" data-key="added" onclick="sortGrid(\'approved-grid\',\'added\')">Added</button>'
        '</div>'
    )

    # ── Approved view: approved jobs + the ones you've already applied to ──────
    approved_tab=(
        f'<div class="plats"><span class="plats-l">Sources</span>{plat_pills}</div>'
        + (((sort_bar + sec("Approved &mdash; Passed All Criteria", approved_jobs, "sec-em", "approved-grid")))
           if approved_jobs else '<div class="empty">No approved jobs yet &mdash; screening in progress…</div>')
        + sec("Applied", applied, "sec-nw")
    )

    # ── Rejected view: jobs that failed at least one criterion ────────────────
    rejected_sort_bar = (
        '<div class="sortbar" data-grid="rejected-grid">'
        '<input class="search-box" id="rejected-search" type="search" '
        'placeholder="Search title, company, location, reason…" '
        'oninput="filterGrid(\'rejected-grid\', this.value)">'
        '<span class="search-count" id="rejected-search-count"></span>'
        '<span class="sortbar-l">Sort by</span>'
        '<button class="sort-btn" data-key="date" onclick="sortGrid(\'rejected-grid\',\'date\')">Date</button>'
        '<button class="sort-btn" data-key="score" onclick="sortGrid(\'rejected-grid\',\'score\')">Rating</button>'
        '<button class="sort-btn" data-key="added" onclick="sortGrid(\'rejected-grid\',\'added\')">Added</button>'
        '</div>'
    )
    rejected_tab=(
        (rejected_sort_bar + sec("Rejected &mdash; Failed a Criterion", rejected, "sec-sk", "rejected-grid"))
        if rejected else '<div class="empty">No rejected jobs yet.</div>'
    )

    # ── Google XR tracker — fully separate feature: own table (xr_jobs), own
    # scraper, no LLM screening, no daemon involvement. Only 3 deterministic
    # checks: non-senior title, US-based, XR/AR/VR related. Scan is manual
    # (Scan Now button) so it never runs unprompted or touches the main flow.
    xr_jobs_list = list_xr_jobs()
    xr_s = xr_stats()
    xr_sort_bar = (
        '<div class="sortbar">'
        '<input class="search-box" id="xr-search" type="search" '
        'placeholder="Search title, location…" '
        'oninput="filterGrid(\'xr-grid\', this.value)">'
        '<span class="search-count" id="xr-search-count"></span>'
        '<span class="sortbar-l">Sort by</span>'
        '<button class="sort-btn" data-key="date" onclick="sortGrid(\'xr-grid\',\'date\')">Date</button>'
        '</div>'
    )
    xr_tab = (
        f'<div class="card" style="margin-bottom:14px">'
        f'<div class="card-ey">Google XR / AR / VR Tracker</div>'
        f'<div class="card-t">Independent Tracker</div>'
        f'<div class="card-sub">Non-senior &middot; US-based &middot; XR/AR/VR only &mdash; independent of the main scan, no LLM screening. '
        f'Auto-scans every 30 min in the daemon; use Scan Now for an on-demand refresh. '
        f'Last scan: {_esc(xr_s["last_scan"] or "never")}</div>'
        f'<div class="sctrl">'
        f'<span class="dot {"dot-am" if _xr_scanning else "dot-muted"}" id="xr-dot"></span>'
        f'<span class="sctrl-label">{xr_s["total"]} roles tracked &nbsp;<small style="color:var(--t4)">every 30m</small></span>'
        f'<span class="sctrl-status {"off" if _xr_scanning else "on"}" id="xr-lbl">{"Scanning…" if _xr_scanning else "Idle"}</span>'
        f'<button class="ctl-btn primary" id="xr-scan-btn" onclick="ctlXrScan()" {"disabled" if _xr_scanning else ""}>Scan Now</button>'
        f'</div>'
        f'</div>'
        + xr_sort_bar
        + _xr_grid(xr_jobs_list)
    )

    from job_scanner.quality import CRITERIA
    _n_criteria = len(CRITERIA)
    scraper_on = _scraper_running()
    scan_mins  = config.SCAN_INTERVAL_SECONDS // 60

    overview_tab = (
        f'<div class="stats">{stat_cards}</div>'

        # ── Controls card
        f'<div class="card">'
        f'<div class="card-ey">Controls</div>'
        f'<div class="card-t">Scanner</div>'
        f'<div class="card-sub">Start or stop the background scan loop</div>'

        f'<div class="sctrl">'
        f'<span class="dot {"dot-gr" if scraper_on else "dot-muted"}" id="scraper-dot"></span>'
        f'<span class="sctrl-label">Job Scraper &nbsp;<small style="color:var(--t4)">every {scan_mins}m</small></span>'
        f'<span class="sctrl-status {"on" if scraper_on else "off"}" id="scraper-lbl">{"Running" if scraper_on else "Stopped"}</span>'
        f'<button class="ctl-btn" id="scraper-start" onclick="ctlScraper(\'start\')" style="{"display:none" if scraper_on else ""}">Start</button>'
        f'<button class="ctl-btn danger" id="scraper-stop" onclick="ctlScraper(\'stop\')" style="{"" if scraper_on else "display:none"}">Stop</button>'
        f'</div>'
        f'</div>'  # end card
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
        f'          <span class="hdr-mi">{_n_criteria} LLM criteria</span>\n'
        f'          <span class="hdr-mi">Strong fit &ge; {config.MIN_SCORE_GOOD}</span>\n'
        f'        </div>\n'
        f'      </div>\n'
        f'      <div class="hdr-r">\n'
        f'        <span class="hdr-rl">Scan every</span>\n'
        f'        {scan_mins} min\n'
        f'      </div>\n'
        f'    </header>\n'

        f'    <nav class="tabs">\n'
        f'      <button class="tab active" data-tab="overview" onclick="switchTab(\'overview\')">Overview</button>\n'
        f'      <button class="tab" data-tab="approved" onclick="switchTab(\'approved\')">Approved ({apc})</button>\n'
        f'      <button class="tab" data-tab="rejected" onclick="switchTab(\'rejected\')">Rejected ({rc})</button>\n'
        f'      <button class="tab" data-tab="xr" onclick="switchTab(\'xr\')">Google XR ({xr_s["total"]})</button>\n'
        f'    </nav>\n'

        f'    <div class="tabp active" id="tab-overview">{overview_tab}</div>\n'
        f'    <div class="tabp" id="tab-approved">{approved_tab}</div>\n'
        f'    <div class="tabp" id="tab-rejected">{rejected_tab}</div>\n'
        f'    <div class="tabp" id="tab-xr">{xr_tab}</div>\n'

        f'    <footer class="footer">\n'
        f'      <span>Jobs Auto Scanner</span>\n'
        f'      <span>Auto-refreshes every 20s</span>\n'
        f'    </footer>\n'
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

        if p.path == "/api/overview":
            job_stats = stats()
            by_status = job_stats.get("by_status", {})
            self._json({
                "scraper": _scraper_running(),
                "total": job_stats.get("total", 0),
                "approved_count": by_status.get("approved", 0),
                "applied_count": by_status.get("applied", 0),
                "rejected_count": by_status.get("rejected", 0) + by_status.get("skip", 0) + by_status.get("error", 0),
            }); return

        if p.path == "/api/xr/status":
            self._json({"scanning": _xr_scanning}); return

        self.send_response(404); self.end_headers()

    def do_POST(self):
        length  = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        p       = self.path

        if p == "/api/scraper/start":
            self._json({"ok": _scraper_start()}); return

        if p == "/api/scraper/stop":
            self._json({"ok": _scraper_stop()}); return

        if p == "/api/job/mark_applied":
            jid = payload.get("id", "").strip()
            if jid:
                update_status(jid, "applied")
                self._json({"ok": True}); return
            self._json({"ok": False}, 400); return

        if p == "/api/xr/scan":
            self._json({"ok": _xr_scan_start()}); return

        self.send_response(404); self.end_headers()


def run_dashboard(port: int = PORT) -> None:
    server = HTTPServer(("", port), _Handler)
    print(f"Dashboard → http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
