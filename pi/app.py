"""Botfia phone web app + host console (Phase 2, no hardware).

Run on the Pi:   python app.py
Players open:    http://<pi-ip>:5000
Host opens:      http://<pi-ip>:5000/host

One game lives in memory at a time. Phones poll for state. Narration is printed
as plain text in the public log for now (Phase 3 adds Claude + voice).
"""

import threading

from flask import Flask, request, jsonify, Response

from game.engine import GameEngine, Phase

app = Flask(__name__)
lock = threading.Lock()
game = GameEngine()

ROLE_DESC = {
    "mafia": "Mafia. Each night, choose someone to remove.",
    "doctor": "Doctor. Each night, choose someone to protect.",
    "detective": "Detective. Each night, check one person. You learn if they are mafia.",
    "villager": "Villager. You have no night action. Find the mafia by day.",
}


def seat_to_pid(seat):
    for p in game.players.values():
        if p.seat == seat:
            return p.id
    return None


# ---------- player API ----------
@app.route("/join", methods=["POST"])
def join():
    name = request.args.get("name", "")
    try:
        seat = int(request.args.get("seat", "0"))
    except ValueError:
        return jsonify(error="bad seat"), 400
    with lock:
        try:
            pid = game.add_player(name, seat)
        except ValueError as e:
            return jsonify(error=str(e)), 400
    return jsonify(pid=pid, seat=seat)


@app.route("/state")
def state():
    with lock:
        return jsonify(game.public_state())


@app.route("/me")
def me():
    pid = request.args.get("pid", "")
    with lock:
        view = game.player_view(pid)
    if view is None:
        return jsonify(error="unknown player"), 404
    view["role_desc"] = ROLE_DESC.get(view.get("role"), "")
    return jsonify(view)


@app.route("/night", methods=["POST"])
def night():
    pid = request.args.get("pid", "")
    target_seat = request.args.get("target")
    target_pid = seat_to_pid(int(target_seat)) if target_seat not in (None, "", "none") else None
    with lock:
        try:
            game.submit_night_action(pid, target_pid)
            if game.night_done():
                game.resolve_night()
        except ValueError as e:
            return jsonify(error=str(e)), 400
    return jsonify(ok=True)


@app.route("/vote", methods=["POST"])
def vote():
    pid = request.args.get("pid", "")
    target_seat = request.args.get("target")
    target_pid = seat_to_pid(int(target_seat)) if target_seat not in (None, "", "none") else None
    with lock:
        try:
            game.submit_vote(pid, target_pid)
            if game.vote_done():
                game.resolve_vote()
        except ValueError as e:
            return jsonify(error=str(e)), 400
    return jsonify(ok=True)


# ---------- host API ----------
@app.route("/host/start", methods=["POST"])
def host_start():
    with lock:
        try:
            game.start_game()
        except ValueError as e:
            return jsonify(error=str(e)), 400
    return jsonify(ok=True)


@app.route("/host/night", methods=["POST"])
def host_night():
    with lock:
        game.begin_night()
    return jsonify(ok=True)


@app.route("/host/vote", methods=["POST"])
def host_vote():
    with lock:
        game.begin_vote()
    return jsonify(ok=True)


@app.route("/host/reset", methods=["POST"])
def host_reset():
    global game
    with lock:
        game = GameEngine()
    return jsonify(ok=True)


# ---------- pages ----------
@app.route("/")
def player_page():
    return Response(PLAYER_HTML, mimetype="text/html")


@app.route("/host")
def host_page():
    return Response(HOST_HTML, mimetype="text/html")


PLAYER_HTML = r"""
<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Botfia</title>
<style>
  body{background:#0e0e10;color:#e4e4e4;font-family:system-ui,sans-serif;margin:0;padding:22px;max-width:480px}
  h1{font-size:15px;font-weight:600;letter-spacing:.03em;color:#aaa;margin:0 0 18px}
  .role{font-size:20px;font-weight:600;margin:6px 0}
  .desc{color:#9aa;font-size:14px;margin-bottom:18px}
  .line{color:#cfcfcf;font-size:15px;margin:10px 0}
  button{display:block;width:100%;background:#1b1b1f;color:#e4e4e4;border:1px solid #333;border-radius:8px;padding:13px;font-size:15px;margin:8px 0}
  button:active{background:#262630}
  button.sel{border-color:#5a7;background:#15241c}
  input{width:100%;background:#1b1b1f;color:#e4e4e4;border:1px solid #333;border-radius:8px;padding:12px;font-size:16px;box-sizing:border-box;margin:6px 0}
  .muted{color:#888;font-size:13px;margin-top:16px}
  .dead{color:#a66}
</style></head><body>
<h1>BOTFIA</h1>
<div id="app"></div>
<script>
let pid = localStorage.getItem('botfia_pid') || null;
let chosen = null;
function el(id){return document.getElementById(id)}
function post(url){return fetch(url,{method:'POST'}).then(r=>r.json())}

function renderJoin(){
  el('app').innerHTML =
    '<div class="line">Enter your name and pick a seat.</div>'+
    '<input id="name" placeholder="Name" maxlength="20">'+
    '<input id="seat" type="number" min="1" max="12" placeholder="Seat number">'+
    '<button onclick="doJoin()">Join</button><div class="muted" id="err"></div>';
}
function doJoin(){
  const name=el('name').value, seat=el('seat').value;
  if(!seat){el('err').textContent='Pick a seat.';return;}
  post('/join?name='+encodeURIComponent(name)+'&seat='+seat).then(r=>{
    if(r.error){el('err').textContent=r.error;return;}
    pid=r.pid; localStorage.setItem('botfia_pid',pid); tick();
  });
}

function peopleButtons(list, cb){
  return list.map(p=>'<button onclick="pick('+p.seat+',this)">Seat '+p.seat+' — '+p.name+'</button>').join('');
}
window.pick=function(seat,btn){
  chosen=seat;
  document.querySelectorAll('#choices button').forEach(b=>b.classList.remove('sel'));
  btn.classList.add('sel');
};

function render(me, st){
  const alive = st.players.filter(p=>p.alive && p.seat!==me.seat);
  const head = '<div class="line">Seat '+me.seat+' — '+me.name+(me.alive?'':' <span class="dead">(out)</span>')+'</div>';

  if(st.phase==='reveal'){
    el('app').innerHTML = head +
      '<div class="role">'+me.role.toUpperCase()+'</div>'+
      '<div class="desc">'+me.role_desc+'</div>'+
      '<div class="muted">Remember your role. Wait for the night.</div>';
    return;
  }
  if(st.phase==='night'){
    if(!me.alive){ el('app').innerHTML=head+'<div class="muted">You are out. Wait for morning.</div>'; return; }
    if(me.submitted_night){
      let extra='';
      if(me.detective_result){
        const r=me.detective_result;
        extra='<div class="line">Seat '+r.target_seat+' — '+r.target_name+' is '+(r.is_mafia?'MAFIA.':'not mafia.')+'</div>';
      }
      el('app').innerHTML=head+'<div class="line">Done.</div>'+extra+'<div class="muted">Waiting for the others.</div>';
      return;
    }
    if(me.role==='villager'){
      el('app').innerHTML=head+'<div class="line">The town is asleep. Close your eyes.</div>'+
        '<button onclick="sendNight(null)">Tap to continue</button>';
      return;
    }
    const prompt={mafia:'Choose someone to remove.',doctor:'Choose someone to protect.',detective:'Choose someone to check.'}[me.role];
    const list = me.role==='doctor' ? st.players.filter(p=>p.alive) : alive;
    el('app').innerHTML=head+'<div class="line">'+prompt+'</div>'+
      '<div id="choices">'+peopleButtons(list)+'</div>'+
      '<button onclick="sendNight(chosen)">Confirm</button>';
    return;
  }
  if(st.phase==='day'){
    el('app').innerHTML=head+st.log.slice(-3).map(l=>'<div class="line">'+l+'</div>').join('')+
      '<div class="muted">Discuss. Wait for the host.</div>';
    return;
  }
  if(st.phase==='vote'){
    if(!me.alive){ el('app').innerHTML=head+'<div class="muted">You are out. Wait for the result.</div>'; return; }
    if(me.submitted_vote){ el('app').innerHTML=head+'<div class="line">Vote in.</div><div class="muted">Waiting for the others.</div>'; return; }
    el('app').innerHTML=head+'<div class="line">Vote someone out.</div>'+
      '<div id="choices">'+peopleButtons(alive)+'</div>'+
      '<button onclick="sendVote(chosen)">Confirm</button>'+
      '<button onclick="sendVote(null)">Abstain</button>';
    return;
  }
  if(st.phase==='end'){
    const roles=(st.reveal||[]).map(p=>'<div class="line">Seat '+p.seat+' — '+p.name+': '+p.role+'</div>').join('');
    el('app').innerHTML=head+'<div class="role">'+(st.winner==='mafia'?'Mafia wins.':'Town wins.')+'</div>'+roles;
    return;
  }
  el('app').innerHTML=head+'<div class="muted">Waiting...</div>';
}

function tick(){
  if(!pid){ renderJoin(); return; }
  Promise.all([fetch('/me?pid='+pid).then(r=>r.json()), fetch('/state').then(r=>r.json())])
    .then(([me,st])=>{
      if(me.error){ localStorage.removeItem('botfia_pid'); pid=null; renderJoin(); return; }
      chosen=null; render(me,st);
    }).catch(()=>{});
}
window.sendNight=function(t){ post('/night?pid='+pid+(t?'&target='+t:'')).then(tick); };
window.sendVote=function(t){ post('/vote?pid='+pid+(t?'&target='+t:'')).then(tick); };
tick(); setInterval(tick, 1500);
</script>
</body></html>
"""

HOST_HTML = r"""
<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Botfia — host</title>
<style>
  body{background:#0e0e10;color:#e4e4e4;font-family:system-ui,sans-serif;margin:0;padding:22px;max-width:560px}
  h1{font-size:15px;letter-spacing:.03em;color:#aaa;margin:0 0 6px}
  .phase{font-size:18px;font-weight:600;margin:10px 0}
  .p{font-size:14px;margin:4px 0}
  .dead{color:#a66}
  .log{background:#141417;border:1px solid #2a2a30;border-radius:8px;padding:10px;margin:14px 0;font-size:13px;color:#bbb}
  button{background:#1b1b1f;color:#e4e4e4;border:1px solid #333;border-radius:8px;padding:11px 16px;font-size:14px;margin:4px 6px 4px 0}
  button:active{background:#262630}
  .url{color:#8ad;font-size:13px}
</style></head><body>
<h1>BOTFIA — HOST</h1>
<div class="url" id="url"></div>
<div class="phase" id="phase"></div>
<div id="players"></div>
<div class="log" id="log"></div>
<div id="controls"></div>
<script>
function post(u){return fetch(u,{method:'POST'}).then(r=>r.json()).then(()=>load())}
function load(){
  fetch('/state').then(r=>r.json()).then(st=>{
    document.getElementById('url').textContent='Players join at: '+location.origin;
    document.getElementById('phase').textContent='Phase: '+st.phase+(st.day_number?'  (round '+st.day_number+')':'');
    document.getElementById('players').innerHTML='<div class="p">'+st.players.length+' players:</div>'+
      st.players.map(p=>'<div class="p">Seat '+p.seat+' — '+p.name+(p.alive?'':' <span class="dead">(out)</span>')+'</div>').join('');
    document.getElementById('log').innerHTML=st.log.map(l=>'<div>'+l+'</div>').join('') || '<div>(no events yet)</div>';
    let c='';
    if(st.phase==='lobby') c='<button onclick="post(\'/host/start\')">Start game</button>';
    else if(st.phase==='reveal') c='<button onclick="post(\'/host/night\')">Start night</button>';
    else if(st.phase==='day') c='<button onclick="post(\'/host/vote\')">Start vote</button> <button onclick="post(\'/host/night\')">Start night</button>';
    else if(st.phase==='night'||st.phase==='vote') c='<div class="p">Waiting for players to submit…</div>';
    if(st.phase!=='lobby') c+=' <button onclick="if(confirm(\'New game?\'))post(\'/host/reset\')">New game</button>';
    document.getElementById('controls').innerHTML=c;
  });
}
load(); setInterval(load, 1500);
</script>
</body></html>
"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
