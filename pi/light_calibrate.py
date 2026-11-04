"""Botfia light-switch calibration page.

Run on the Pi:   python light_calibrate.py
Then open:       http://<pi-ip>:8000   (or http://botfia.local:8000)

Drag a slider to move the arm live. Set ON, OFF, and REST, then Save. The angles
are written to light_config.json so they survive a reboot.
"""

from flask import Flask, request, jsonify, Response

from light_switch import LightSwitch

app = Flask(__name__)
sw = LightSwitch()

# Minimal dark page. Plain, no decoration — per the style rules.
PAGE = r"""
<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Botfia lights</title>
<style>
  body{background:#111;color:#ddd;font-family:system-ui,sans-serif;margin:0;padding:24px;max-width:520px}
  h1{font-size:16px;font-weight:600;letter-spacing:.02em;margin:0 0 4px}
  .sub{color:#888;font-size:13px;margin-bottom:24px}
  .row{margin:20px 0}
  label{display:flex;justify-content:space-between;font-size:14px;margin-bottom:8px}
  .val{color:#9ad}
  input[type=range]{width:100%}
  .btns{display:flex;gap:10px;margin-top:8px}
  button{flex:1;background:#222;color:#ddd;border:1px solid #333;border-radius:6px;padding:10px;font-size:14px}
  button:active{background:#333}
  .save{margin-top:28px;border-color:#2a4}
  .state{margin-top:24px;color:#888;font-size:13px}
</style></head><body>
<h1>Botfia light switch</h1>
<div class="sub">Drag a slider to move the arm live. Set ON, OFF, and REST, then Save.</div>

<div class="row">
  <label>ON angle <span class="val" id="onv"></span></label>
  <input type="range" min="0" max="180" id="on">
</div>
<div class="row">
  <label>OFF angle <span class="val" id="offv"></span></label>
  <input type="range" min="0" max="180" id="off">
</div>
<div class="row">
  <label>REST angle <span class="val" id="restv"></span></label>
  <input type="range" min="0" max="180" id="rest">
</div>

<div class="btns">
  <button onclick="test('on')">Test ON</button>
  <button onclick="test('off')">Test OFF</button>
  <button onclick="park()">Go to REST</button>
</div>

<button class="save" onclick="save()">Save to Pi</button>
<div class="state" id="state"></div>

<script>
const ids=['on','off','rest'];
function el(i){return document.getElementById(i)}
function line(s){el('state').textContent='State: '+s.state+(s.simulated?'  ·  SIMULATION':'')}
function refresh(){fetch('/status').then(r=>r.json()).then(s=>{
  for(const i of ids){el(i).value=s.angles[i];el(i+'v').textContent=s.angles[i]}
  line(s);
})}
for(const i of ids){
  el(i).addEventListener('input',()=>{
    el(i+'v').textContent=el(i).value;
    fetch('/servo?angle='+el(i).value,{method:'POST'});
  });
}
function test(which){fetch('/lights/'+which,{method:'POST'}).then(r=>r.json()).then(line)}
function park(){fetch('/servo?angle='+el('rest').value,{method:'POST'})}
function save(){
  fetch('/config?on='+el('on').value+'&off='+el('off').value+'&rest='+el('rest').value,{method:'POST'})
    .then(r=>r.json()).then(s=>{line(s);el('state').textContent='Saved. '+el('state').textContent})
}
refresh();
</script>
</body></html>
"""


@app.route("/")
def root():
    return Response(PAGE, mimetype="text/html")


@app.route("/status")
def status():
    return jsonify(sw.status())


@app.route("/servo", methods=["POST"])
def servo():
    angle = request.args.get("angle")
    if angle is None:
        return jsonify(error="missing angle"), 400
    sw.move_to(int(angle))
    return jsonify(ok=True)


@app.route("/lights/on", methods=["POST"])
def lights_on():
    sw.on()
    return jsonify(sw.status())


@app.route("/lights/off", methods=["POST"])
def lights_off():
    sw.off()
    return jsonify(sw.status())


@app.route("/config", methods=["POST"])
def config():
    sw.set_angles(
        on=request.args.get("on"),
        off=request.args.get("off"),
        rest=request.args.get("rest"),
    )
    return jsonify(sw.status())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
