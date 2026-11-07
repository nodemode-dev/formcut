#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod engine_lifecycle;
mod reveal;
use std::sync::Mutex;

use tauri::menu::{
    AboutMetadata, MenuBuilder, MenuItemBuilder, PredefinedMenuItem, SubmenuBuilder,
};
use tauri::{Manager, RunEvent};
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

struct Backend(Mutex<Option<CommandChild>>);

const FALLBACK_LOGICAL: (f64, f64) = (1323.0, 860.0);
const MIN_LOGICAL: (f64, f64) = (980.0, 640.0);
const SCREEN_FRACTION: f64 = 0.9;

fn kill_backend(handle: &tauri::AppHandle) {
    if let Some(child) = handle.state::<Backend>().0.lock().unwrap().take() {
        let _ = child.kill();
    }
}

fn main() {
    reveal::mark_launch();
    let app = tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![reveal::app_ready])
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(Backend(Mutex::new(None)))
        .setup(|app| {
            reveal::round_splash(app.handle());
            let file_new = MenuItemBuilder::new("New Project")
                .id("file-new")
                .accelerator("CmdOrCtrl+N")
                .build(app)?;
            let file_save = MenuItemBuilder::new("Save Project")
                .id("file-save")
                .accelerator("CmdOrCtrl+S")
                .build(app)?;
            let app_menu = SubmenuBuilder::new(app, "FormCut")
                .about(Some(AboutMetadata::default()))
                .separator()
                .services()
                .separator()
                .hide()
                .hide_others()
                .show_all()
                .separator()
                .quit()
                .build()?;
            let file = SubmenuBuilder::new(app, "File")
                .item(&file_new)
                .item(&file_save)
                .build()?;
            let history_undo = MenuItemBuilder::new("Undo").id("edit-undo").accelerator("CmdOrCtrl+Z").build(app)?;
            let history_redo = MenuItemBuilder::new("Redo").id("edit-redo").accelerator("CmdOrCtrl+Shift+Z").build(app)?;
            let edit = SubmenuBuilder::new(app, "Edit")
                .item(&history_undo)
                .item(&history_redo)
                .separator()
                .cut()
                .copy()
                .paste()
                .select_all()
                .build()?;
            let view = SubmenuBuilder::new(app, "View")
                .item(&PredefinedMenuItem::fullscreen(app, None)?)
                .build()?;
            let window = SubmenuBuilder::new(app, "Window")
                .minimize()
                .separator()
                .close_window()
                .build()?;
            #[cfg(target_os = "macos")]
            window.set_as_windows_menu_for_nsapp()?;
            let help_version = MenuItemBuilder::new(format!("formcut v{}", env!("CARGO_PKG_VERSION")))
                .id("help-version")
                .enabled(false)
                .build(app)?;
            let help = SubmenuBuilder::new(app, "Help").item(&help_version).build()?;
            #[cfg(target_os = "macos")]
            help.set_as_help_menu_for_nsapp()?;
            let menu = MenuBuilder::new(app)
                .items(&[&app_menu, &file, &edit, &view, &window, &help])
                .build()?;
            app.set_menu(menu)?;
            app.on_menu_event(|handle, event| {
                let script = match event.id().as_ref() {
                    "file-new" => "window.formcut && window.formcut.actions.newProject()",
                    "file-save" => "window.formcut && window.formcut.actions.save()",
                    "edit-undo" => "document.activeElement?.matches(\"input,textarea,[contenteditable=true]\") ? document.execCommand(\"undo\") : window.formcut?.engine.dispatch(\"history.undo\")",
                    "edit-redo" => "document.activeElement?.matches(\"input,textarea,[contenteditable=true]\") ? document.execCommand(\"redo\") : window.formcut?.engine.dispatch(\"history.redo\")",
                    _ => return,
                };
                if let Some(webview) = handle.get_webview_window("main") {
                    let _ = webview.eval(script);
                }
            });

            let handle = app.handle().clone();
            let (rx, child) = app
                .shell()
                .sidecar("formcut-engine")
                .expect("sidecar binary is bundled")
                .env("FORMCUT_PORT", "0")
                .spawn()
                .expect("the formcut engine failed to spawn");
            app.state::<Backend>().0.lock().unwrap().replace(child);

            tauri::async_runtime::spawn(engine_lifecycle::supervise(handle, rx));
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("tauri app should build");

    app.run(|handle, event| {
        if let RunEvent::Exit = event {
            kill_backend(handle);
        }
    });
}
