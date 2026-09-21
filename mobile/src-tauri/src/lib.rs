//! formcut on phones: a shell around the formcut running on the person's computer.
//!
//! The app shows one local page that asks for the computer's address, then
//! navigates there. The computer's engine serves its pairing page and, once the
//! phone is paired, the whole interface. The shell holds nothing of its own and
//! grants the pages it loads no native access.

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running formcut");
}
