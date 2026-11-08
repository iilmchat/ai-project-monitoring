#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpListener;
use std::sync::Mutex;

use tauri::{Manager, RunEvent, State};
use tauri_plugin_shell::{process::CommandChild, ShellExt};

struct BackendState {
    child: Mutex<Option<CommandChild>>,
    url: Mutex<String>,
}

#[tauri::command]
fn backend_url(state: State<'_, BackendState>) -> String {
    state
        .url
        .lock()
        .map(|value| value.clone())
        .unwrap_or_default()
}

fn free_port() -> Result<u16, Box<dyn std::error::Error>> {
    let listener = TcpListener::bind("127.0.0.1:0")?;
    Ok(listener.local_addr()?.port())
}

fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let port = free_port()?;
            let data_dir = app.path().app_data_dir()?.join("IIRuchating");
            std::fs::create_dir_all(&data_dir)?;
            let url = format!("http://127.0.0.1:{port}");
            let port_text = port.to_string();
            let data_text = data_dir.to_string_lossy().to_string();

            // tauri-plugin-shell applies CREATE_NO_WINDOW to the sidecar on
            // Windows; backend child processes (git/pip/pnpm) use the same
            // flag via app.core.subprocess_flags.
            let sidecar = app
                .shell()
                .sidecar("iiruchating-backend")?
                .set_process_group(true)
                .kill_on_drop(true)
                .args(["--port", &port_text, "--data-dir", &data_text]);
            let (mut events, child) = sidecar.spawn()?;

            app.manage(BackendState {
                child: Mutex::new(Some(child)),
                url: Mutex::new(url),
            });

            tauri::async_runtime::spawn(async move {
                while let Some(event) = events.recv().await {
                    if let tauri_plugin_shell::process::CommandEvent::Error(message) = event {
                        eprintln!("sidecar error: {message}");
                    }
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![backend_url])
        .build(tauri::generate_context!())
        .expect("error while building IIRuchating");

    app.run(|app_handle, event| {
        if let RunEvent::Exit = event {
            if let Some(state) = app_handle.try_state::<BackendState>() {
                if let Ok(mut guard) = state.child.lock() {
                    if let Some(child) = guard.take() {
                        let _ = child.kill();
                    }
                }
            }
        }
    });
}
