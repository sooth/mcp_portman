//! MCP Port Manager, native build. Same tools and registry file as the Python version
//! (~/.mcp_portman/registry.json), MCP over stdio as newline-delimited JSON-RPC.
// ponytail: macOS-only FFI for bind() and localtime_r(); add a Linux sockaddr_in (no sin_len) if it ever runs there.

use serde_json::{json, Map, Value};
use std::io::{self, BufRead, Write};
use std::path::PathBuf;

const PORT_MIN: i64 = 1024;
const PORT_MAX: i64 = 49151;

type Registry = Map<String, Value>;

fn registry_file() -> PathBuf {
    let home = std::env::var_os("HOME").map(PathBuf::from).unwrap_or_else(|| PathBuf::from("."));
    home.join(".mcp_portman").join("registry.json")
}

fn load_registry() -> Registry {
    std::fs::read_to_string(registry_file())
        .ok()
        .and_then(|s| serde_json::from_str::<Value>(&s).ok())
        .and_then(|v| if let Value::Object(m) = v { Some(m) } else { None })
        .unwrap_or_default()
}

fn save_registry(reg: &Registry) -> Result<(), String> {
    let path = registry_file();
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir).map_err(|e| e.to_string())?;
    }
    let text = serde_json::to_string_pretty(reg).map_err(|e| e.to_string())?;
    std::fs::write(&path, text).map_err(|e| e.to_string())
}

#[repr(C)]
struct SockaddrIn {
    sin_len: u8,
    sin_family: u8,
    sin_port: u16,
    sin_addr: u32,
    sin_zero: [u8; 8],
}

#[repr(C)]
struct Tm {
    sec: i32, min: i32, hour: i32, mday: i32, mon: i32, year: i32,
    wday: i32, yday: i32, isdst: i32, gmtoff: i64, zone: *const i8,
}

extern "C" {
    fn socket(domain: i32, ty: i32, proto: i32) -> i32;
    fn bind(fd: i32, addr: *const SockaddrIn, len: u32) -> i32;
    fn close(fd: i32) -> i32;
    fn localtime_r(t: *const i64, out: *mut Tm) -> *mut Tm;
}

/// Plain bind() on INADDR_ANY, no SO_REUSEADDR (std's TcpListener sets it, which would
/// report ports held by a 127.0.0.1 listener as free on macOS).
fn is_port_available(port: i64) -> bool {
    if !(0..=65535).contains(&port) {
        return false;
    }
    unsafe {
        let fd = socket(2 /* AF_INET */, 1 /* SOCK_STREAM */, 0);
        if fd < 0 {
            return false;
        }
        let addr = SockaddrIn {
            sin_len: std::mem::size_of::<SockaddrIn>() as u8,
            sin_family: 2,
            sin_port: (port as u16).to_be(),
            sin_addr: 0,
            sin_zero: [0; 8],
        };
        let ok = bind(fd, &addr, std::mem::size_of::<SockaddrIn>() as u32) == 0;
        close(fd);
        ok
    }
}

/// Local time like Python's datetime.now().isoformat(): 2026-11-06T11:27:01.123456
fn now_iso() -> String {
    let d = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_default();
    let secs = d.as_secs() as i64;
    let mut tm: Tm = unsafe { std::mem::zeroed() };
    unsafe { localtime_r(&secs, &mut tm) };
    format!(
        "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}.{:06}",
        tm.year + 1900, tm.mon + 1, tm.mday, tm.hour, tm.min, tm.sec, d.subsec_micros()
    )
}

fn arg_int(args: &Value, key: &str) -> Result<Option<i64>, String> {
    match args.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(v) => v.as_i64().map(Some).ok_or_else(|| format!("'{key}' must be an integer")),
    }
}

fn req_int(args: &Value, key: &str) -> Result<i64, String> {
    arg_int(args, key)?.ok_or_else(|| format!("missing required argument '{key}'"))
}

fn arg_str(args: &Value, key: &str) -> Result<Option<String>, String> {
    match args.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(s)) => Ok(Some(s.clone())),
        Some(_) => Err(format!("'{key}' must be a string")),
    }
}

fn app_of(entry: &Value) -> &str {
    entry.get("app_name").and_then(Value::as_str).unwrap_or("")
}

fn with_fields(entry: &Value, extra: Value) -> Value {
    let mut m = entry.as_object().cloned().unwrap_or_default();
    if let Value::Object(e) = extra {
        m.extend(e);
    }
    Value::Object(m)
}

fn get_free_port(a: &Value) -> Result<Value, String> {
    let reg = load_registry();
    if let Some(p) = arg_int(a, "preferred_port")? {
        if !(PORT_MIN..=PORT_MAX).contains(&p) {
            return Ok(json!({"port": null, "message": format!("Port {p} is outside valid range ({PORT_MIN}-{PORT_MAX})")}));
        }
        let entry = reg.get(&p.to_string());
        let os_ok = is_port_available(p);
        if entry.is_none() && os_ok {
            return Ok(json!({"port": p, "message": format!("Port {p} is available")}));
        }
        let mut why = Vec::new();
        if let Some(e) = entry {
            why.push(format!("registered to '{}'", app_of(e)));
        }
        if !os_ok {
            why.push("in use by OS".to_string());
        }
        return Ok(json!({"port": null, "message": format!("Port {p} is not available ({})", why.join(", "))}));
    }
    for p in PORT_MIN..=PORT_MAX {
        if !reg.contains_key(&p.to_string()) && is_port_available(p) {
            return Ok(json!({"port": p, "message": format!("Found available port {p}")}));
        }
    }
    Ok(json!({"port": null, "message": "No free ports available in range"}))
}

fn lookup_by_port(a: &Value) -> Result<Value, String> {
    let p = req_int(a, "port")?;
    let reg = load_registry();
    Ok(match reg.get(&p.to_string()) {
        Some(e) => with_fields(e, json!({"port": p, "registered": true, "os_available": is_port_available(p)})),
        None => json!({"port": p, "registered": false, "os_available": is_port_available(p),
                       "message": "Port not registered in MCP Port Manager"}),
    })
}

fn lookup_by_application(a: &Value) -> Result<Value, String> {
    let name = arg_str(a, "app_name")?.ok_or("missing required argument 'app_name'")?;
    let want = name.to_lowercase();
    let reg = load_registry();
    let mut ports: Vec<(i64, Value)> = reg
        .iter()
        .filter(|(_, e)| app_of(e).to_lowercase() == want)
        .filter_map(|(k, e)| k.parse::<i64>().ok().map(|p| (p, e)))
        .map(|(p, e)| (p, with_fields(e, json!({"port": p, "os_available": is_port_available(p)}))))
        .collect();
    ports.sort_by_key(|(p, _)| *p);
    let count = ports.len();
    Ok(json!({"app_name": name, "ports": ports.into_iter().map(|(_, v)| v).collect::<Vec<_>>(), "count": count}))
}

fn register_port(a: &Value) -> Result<Value, String> {
    let p = req_int(a, "port")?;
    let app = arg_str(a, "app_name")?.ok_or("missing required argument 'app_name'")?;
    let desc = arg_str(a, "description")?.unwrap_or_default();
    if !(PORT_MIN..=PORT_MAX).contains(&p) {
        return Ok(json!({"success": false, "message": format!("Port {p} is outside valid range ({PORT_MIN}-{PORT_MAX})")}));
    }
    let mut reg = load_registry();
    let key = p.to_string();
    if let Some(e) = reg.get(&key) {
        return Ok(json!({"success": false, "message": format!("Port {p} is already registered to \"{}\"", app_of(e)),
                         "existing_registration": e}));
    }
    reg.insert(key, json!({"app_name": app, "description": desc, "registered_at": now_iso()}));
    save_registry(&reg)?;
    Ok(json!({"success": true, "message": format!("Successfully registered port {p} to \"{app}\""),
              "port": p, "app_name": app, "description": desc, "os_available": is_port_available(p)}))
}

fn unregister_port(a: &Value) -> Result<Value, String> {
    let p = req_int(a, "port")?;
    let mut reg = load_registry();
    let Some(removed) = reg.remove(&p.to_string()) else {
        return Ok(json!({"success": false, "message": format!("Port {p} is not registered")}));
    };
    save_registry(&reg)?;
    Ok(json!({"success": true, "message": format!("Successfully unregistered port {p}"),
              "removed_registration": with_fields(&removed, json!({"port": p}))}))
}

type ToolFn = fn(&Value) -> Result<Value, String>;

fn tools() -> Vec<(&'static str, &'static str, Value, ToolFn)> {
    let int = |d: &str| json!({"type": "integer", "description": d});
    let s = |d: &str| json!({"type": "string", "description": d});
    vec![
        ("get_free_port",
         "Find and return an available port. Checks both the registry and OS-level availability. If preferred_port is not given, searches 1024-49151. Returns 'port' (or null) and 'message'.",
         json!({"type": "object", "properties": {"preferred_port": int("Optional specific port to check")}}),
         get_free_port),
        ("lookup_by_port",
         "Look up a port: app_name, description, registered_at and OS availability, or registered=false if not in the registry.",
         json!({"type": "object", "properties": {"port": int("The port number to look up")}, "required": ["port"]}),
         lookup_by_port),
        ("lookup_by_application",
         "Find all ports registered to an application (case-insensitive). Returns 'app_name', 'ports' and 'count'.",
         json!({"type": "object", "properties": {"app_name": s("Application name (case-insensitive)")}, "required": ["app_name"]}),
         lookup_by_application),
        ("register_port",
         "Register a port (1024-49151) to an application with an optional description. Fails if already registered.",
         json!({"type": "object", "properties": {"port": int("Port number to register"), "app_name": s("Application using this port"),
                "description": s("What the port is used for")}, "required": ["port", "app_name"]}),
         register_port),
        ("unregister_port",
         "Remove a port registration. Returns the removed registration.",
         json!({"type": "object", "properties": {"port": int("Port number to unregister")}, "required": ["port"]}),
         unregister_port),
    ]
}

fn handle(msg: &Value) -> Option<Value> {
    let id = msg.get("id")?.clone(); // no id = notification, no reply
    let method = msg.get("method").and_then(Value::as_str).unwrap_or("");
    let params = msg.get("params").cloned().unwrap_or(json!({}));
    let ok = |r: Value| json!({"jsonrpc": "2.0", "id": id, "result": r});
    let err = |code: i32, m: String| json!({"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": m}});
    Some(match method {
        "initialize" => ok(json!({
            "protocolVersion": params.get("protocolVersion").cloned().unwrap_or(json!("2025-06-18")),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "Port Manager", "version": env!("CARGO_PKG_VERSION")},
        })),
        "ping" => ok(json!({})),
        "tools/list" => ok(json!({"tools": tools().into_iter()
            .map(|(n, d, sch, _)| json!({"name": n, "description": d, "inputSchema": sch}))
            .collect::<Vec<_>>()})),
        "tools/call" => {
            let name = params.get("name").and_then(Value::as_str).unwrap_or("");
            let Some((_, _, _, f)) = tools().into_iter().find(|t| t.0 == name) else {
                return Some(err(-32602, format!("Unknown tool: {name}")));
            };
            let args = params.get("arguments").cloned().unwrap_or(json!({}));
            match f(&args) {
                Ok(r) => ok(json!({"content": [{"type": "text", "text": r.to_string()}], "structuredContent": r, "isError": false})),
                Err(e) => ok(json!({"content": [{"type": "text", "text": format!("Error: {e}")}], "isError": true})),
            }
        }
        _ => err(-32601, format!("Method not found: {method}")),
    })
}

fn main() {
    let stdin = io::stdin();
    let mut out = io::stdout().lock();
    for line in stdin.lock().lines() {
        let Ok(line) = line else { break };
        if line.trim().is_empty() {
            continue;
        }
        let reply = match serde_json::from_str::<Value>(&line) {
            Ok(msg) => handle(&msg),
            Err(_) => Some(json!({"jsonrpc": "2.0", "id": null, "error": {"code": -32700, "message": "Parse error"}})),
        };
        if let Some(r) = reply {
            if writeln!(out, "{r}").and_then(|_| out.flush()).is_err() {
                break;
            }
        }
    }
}
