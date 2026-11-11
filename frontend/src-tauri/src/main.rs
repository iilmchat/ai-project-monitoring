#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpListener;
use std::path::PathBuf;
use std::sync::Mutex;

use tauri::{Manager, RunEvent, State};
use tauri_plugin_log::{RotationStrategy, Target, TargetKind, TimezoneStrategy};
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

/// Desktop log directory: `%APPDATA%/IIRuchating/logs` on Windows.
fn logs_dir_path() -> PathBuf {
    #[cfg(windows)]
    {
        if let Ok(appdata) = std::env::var("APPDATA") {
            return PathBuf::from(appdata).join("IIRuchating").join("logs");
        }
    }

    PathBuf::from("logs")
}

/// Expose the log directory to the "Open logs folder" settings button.
#[tauri::command]
fn logs_dir() -> String {
    logs_dir_path().to_string_lossy().into_owned()
}

#[derive(serde::Serialize)]
struct LogsOpenResult {
    opened: bool,
    path: String,
}

/// Create the log directory (when missing) and reveal it in the OS file
/// manager.  When the native opener fails the path is returned so the
/// frontend can copy it to the clipboard and show a toast.
#[tauri::command]
#[allow(deprecated)] // tauri-plugin-opener is not bundled yet
fn open_logs_folder(app: tauri::AppHandle) -> Result<LogsOpenResult, String> {
    let directory = logs_dir_path();
    std::fs::create_dir_all(&directory).map_err(|error| error.to_string())?;
    let path = directory.to_string_lossy().into_owned();
    match app.shell().open(path.clone(), None) {
        Ok(()) => Ok(LogsOpenResult { opened: true, path }),
        Err(error) => {
            eprintln!("open logs folder failed: {error}");
            Ok(LogsOpenResult {
                opened: false,
                path,
            })
        }
    }
}

fn main() {
    let log_level = if cfg!(debug_assertions) {
        log::LevelFilter::Debug
    } else {
        log::LevelFilter::Info
    };

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .plugin(
            tauri_plugin_log::Builder::new()
                .clear_targets()
                .target(Target::new(TargetKind::Stdout))
                .target(Target::new(TargetKind::Folder {
                    path: logs_dir_path(),
                    file_name: Some("app".to_string()),
                }))
                .level(log_level)
                // Rotate once the file reaches 5 MiB, keeping one backup.
                .max_file_size(5 * 1024 * 1024)
                .rotation_strategy(RotationStrategy::KeepOne)
                .timezone_strategy(TimezoneStrategy::UseLocal)
                .build(),
        )
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
        .invoke_handler(tauri::generate_handler![
            backend_url,
            logs_dir,
            open_logs_folder
        ])
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
