"""Bounded JavaScript experiment for Google's inline challenge, without a browser.

This deliberately small environment is not a real DOM or a proven fingerprint.
No Python callbacks, filesystem or network interfaces are exposed to scripts.
Returned cookies and redirects are private; callers must validate destinations.
"""
import json
import time
from urllib.parse import urlsplit, parse_qs
from .google_identity import PLATFORM, USER_AGENT

SHIM = r"""
var window=globalThis,self=globalThis,top=globalThis,parent=globalThis,frames=globalThis;
var __cookies={},__cookieWrites={},__timers=[],__redirects=[],__beacons=[],__timerId=0;
var location={href:'https://www.google.com/search?q=Python+official+website&hl=en&num=5',
 origin:'https://www.google.com',protocol:'https:',host:'www.google.com',hostname:'www.google.com',pathname:'/search',search:'?q=Python+official+website&hl=en&num=5',hash:'',
 replace:function(u){__redirects.push(String(u))},assign:function(u){__redirects.push(String(u))}};
function HTMLElement(){};function HTMLMediaElement(){};function Navigator(){};
var navigator={userAgent:'',languages:['en-US','en'],language:'en-US',platform:'',cookieEnabled:true,
 sendBeacon:function(u){__beacons.push(String(u));return true}};
var screen={width:1920,height:1080,availWidth:1920,availHeight:1040,colorDepth:24};
var __timeOrigin=Date.now();
var history={length:1};var performance={now:function(){return Date.now()-__timeOrigin},timeOrigin:__timeOrigin,timing:{navigationStart:__timeOrigin,responseStart:__timeOrigin}};
function element(tag){return {tagName:String(tag).toUpperCase(),style:{},children:[],appendChild:function(x){this.children.push(x);return x},removeChild:function(){},setAttribute:function(k,v){this[k]=v},getAttribute:function(k){return this[k]||null},getContext:function(){return null},addEventListener:function(){},removeEventListener:function(){},getBoundingClientRect:function(){return {x:0,y:0,width:0,height:0}},innerHTML:'',textContent:''}}
var document={readyState:'complete',visibilityState:'visible',documentElement:element('html'),body:element('body'),head:element('head'),createElement:element,
 getElementById:function(){return element('div')},querySelector:function(){return null},querySelectorAll:function(){return []},addEventListener:function(){},removeEventListener:function(){}};
Object.defineProperty(document,'cookie',{get:function(){return Object.keys(__cookies).map(k=>k+'='+__cookies[k]).join('; ')},set:function(v){var p=String(v).split(';')[0],i=p.indexOf('=');__cookies[p.slice(0,i)]=p.slice(i+1);__cookieWrites[p.slice(0,i)]=String(v)}});
function addEventListener(){};function removeEventListener(){};
var sessionStorage={getItem:function(){return null},setItem:function(){}};var localStorage=sessionStorage;
function setTimeout(f,delay,...args){var id=++__timerId;__timers.push({id:id,due:Date.now()+Math.max(0,Number(delay)||0),callback:f,args:args});return id};
function clearTimeout(id){__timers=__timers.filter(t=>t.id!==id)};function setInterval(){return 0};function clearInterval(){};
function Image(){return element('img')};var console={log:function(){},warn:function(){},error:function(){}};
var __alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
function atob(s){var out='',bits=0,v=0;for(var c of String(s).replace(/=+$/,'')){var n=__alphabet.indexOf(c);if(n<0)continue;v=(v<<6)|n;bits+=6;if(bits>=8){bits-=8;out+=String.fromCharCode((v>>bits)&255)}}return out}
function btoa(s){var out='',i=0;while(i<s.length){var a=s.charCodeAt(i++),b=s.charCodeAt(i++),c=s.charCodeAt(i++);out+=__alphabet[a>>2]+__alphabet[((a&3)<<4)|(isNaN(b)?0:b>>4)]+(isNaN(b)?'=':__alphabet[((b&15)<<2)|(isNaN(c)?0:c>>6)])+(isNaN(c)?'=':__alphabet[c&63])}return out}
"""


def evaluate_challenge(body, url, *, initial_cookies=None):
    import quickjs
    from lxml import html

    if len(body) > 1_000_000:
        raise ValueError("Challenge body exceeds experiment limit")
    context = quickjs.Context()
    context.set_memory_limit(64 * 1024 * 1024)
    context.set_max_stack_size(512 * 1024)
    context.set_time_limit(1)
    context.eval(SHIM)
    u = urlsplit(url)
    location = {"href": url, "origin": f"{u.scheme}://{u.netloc}", "protocol": u.scheme + ":",
                "host": u.netloc, "hostname": u.hostname, "pathname": u.path,
                "search": "?" + u.query if u.query else "", "hash": "#" + u.fragment if u.fragment else ""}
    context.eval("Object.assign(location," + json.dumps(location) + ")")
    context.eval("Object.assign(navigator," + json.dumps({"userAgent": USER_AGENT, "platform": PLATFORM}) + ")")
    context.eval("Object.assign(__cookies," + json.dumps(initial_cookies or {}) + ")")
    errors = []
    deadline = time.perf_counter() + 5
    jobs, timers = 0, 0

    def drain_microtasks():
        nonlocal jobs
        while time.perf_counter() < deadline:
            if jobs >= 200:
                errors.append({"stage": "job_budget"})
                return False
            try:
                if not context.execute_pending_job():
                    return True
            except quickjs.JSException:
                errors.append({"stage": "job", "index": jobs})
                return False
            jobs += 1
        errors.append({"stage": "deadline"})
        return False

    scripts = html.fromstring(body).xpath("//script[not(@src)]")
    for index, script in enumerate(scripts[:20]):
        if time.perf_counter() >= deadline:
            errors.append({"stage": "deadline"})
            break
        try:
            context.eval(script.text or "")
        except quickjs.JSException:
            errors.append({"stage": "script", "index": index})
        if not drain_microtasks():
            break
    for index in range(200):
        if time.perf_counter() >= deadline:
            errors.append({"stage": "deadline"})
            break
        try:
            # A microtask checkpoint drains Promises before the next timer task.
            if not drain_microtasks():
                break
            if context.eval("__redirects.length"):
                break  # A navigation abandons the old page's delayed timers.
            delay = context.eval("__timers.length ? Math.max(0,Math.min(...__timers.map(t=>t.due))-Date.now()) : -1")
            if delay < 0 or delay / 1000 > deadline - time.perf_counter():
                break
            if delay:
                time.sleep(min(delay / 1000, 0.02))
                continue
            context.eval("(function(){__timers.sort((a,b)=>a.due-b.due||a.id-b.id);var t=__timers.shift();if(typeof t.callback==='function')t.callback(...t.args)})()")
            timers += 1
        except quickjs.JSException:
            errors.append({"stage": "job", "index": index})
            break
    state = json.loads(context.eval("JSON.stringify({cookies:__cookies,cookie_writes:__cookieWrites,redirects:__redirects,beacons:__beacons})"))
    # Never expose cookie/token values or script exception strings in diagnostics.
    state["diagnostics"] = {"errors": errors, "script_count": min(len(scripts), 20),
                            "cookie_names": sorted(state["cookie_writes"]),
                            "cookie_lengths": {k: len(state["cookies"][k]) for k in state["cookie_writes"]},
                            "initial_cookie_count": len(initial_cookies or {}),
                            "microtasks_executed": jobs, "timers_executed": timers,
                            "beacon_codes": sorted({parse_qs(urlsplit(u).query).get("cad", [""])[0]
                                for u in state["beacons"] if parse_qs(urlsplit(u).query).get("cad", [""])[0]
                                in {"sg_trbl", "sg_b_e"}}),
                            "redirect_count": len(state["redirects"])}
    return state
