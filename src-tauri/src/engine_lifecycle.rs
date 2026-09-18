use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::time::{Duration, Instant};

use tauri::{Manager, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_dialog::DialogExt;
use tauri_plugin_shell::process::CommandEvent;

fn healthy(port: u16) -> bool {
    let address = SocketAddr::from(([127, 0, 0, 1], port));
    let Ok(mut stream) = TcpStream::connect_timeout(&address, Duration::from_secs(1)) else { return false; };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(1)));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(1)));
    let request = format!("GET /api/health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n");
    if stream.write_all(request.as_bytes()).is_err() { return false; }
    let mut response = String::new();
    stream.read_to_string(&mut response).is_ok() && response.starts_with("HTTP/1.1 200") && response.contains("\"status\":\"ok\"")
}

pub async fn supervise(handle: tauri::AppHandle, mut rx: tauri::async_runtime::Receiver<CommandEvent>) {
    let deadline = Instant::now() + Duration::from_secs(40);
    let pattern = regex::Regex::new(r"http://127\.0\.0\.1:(\d+)").expect("static port pattern");
    let mut ready = false;
    let mut pending = String::new();
    let mut failure = String::from("The local engine did not become ready within 40 seconds.");
    loop {
        let event = if ready { rx.recv().await } else {
            let remaining = deadline.saturating_duration_since(Instant::now());
            match tokio::time::timeout(remaining, rx.recv()).await { Ok(event) => event, Err(_) => break }
        };
        let Some(event) = event else { break; };
        match event {
            CommandEvent::Stdout(bytes) | CommandEvent::Stderr(bytes) => {
                if ready { continue; }
                pending.push_str(&String::from_utf8_lossy(&bytes));
                if let Some(captures) = pattern.captures(&pending) {
                    if let Ok(port) = captures[1].parse::<u16>() {
                        let ok = tauri::async_runtime::spawn_blocking(move || healthy(port)).await.unwrap_or(false);
                        if ok {
                            let url = format!("http://127.0.0.1:{port}").parse().expect("loopback URL");
                            let (width, height) = handle.primary_monitor().ok().flatten().map(|monitor| {
                                let size = monitor.size();
                                let scale = monitor.scale_factor();
                                (f64::min(1600.0, size.width as f64 / scale * crate::SCREEN_FRACTION), f64::min(1100.0, size.height as f64 / scale * crate::SCREEN_FRACTION))
                            }).unwrap_or(crate::FALLBACK_LOGICAL);
                            match WebviewWindowBuilder::new(&handle, "main", WebviewUrl::External(url))
                                .title("formcut")
                                .inner_size(width, height)
                                .min_inner_size(crate::MIN_LOGICAL.0.min(width), crate::MIN_LOGICAL.1.min(height))
                                .center().build() {
                                Ok(_) => { ready = true; pending.clear(); },
                                Err(error) => { failure = format!("The editor window could not open: {error}"); break; },
                            }
                        }
                    }
                }
                if pending.len() > 8192 { pending.clear(); }
            },
            CommandEvent::Terminated(payload) => {
                failure = format!("The local engine stopped (exit {:?}). Reopen FormCut to restart it.", payload.code);
                break;
            },
            CommandEvent::Error(error) => { failure = error; break; },
            _ => {},
        }
    }
    if !ready || handle.get_webview_window("main").is_some() {
        handle.dialog().message(failure).blocking_show();
    }
    crate::kill_backend(&handle);
    handle.exit(1);
}
