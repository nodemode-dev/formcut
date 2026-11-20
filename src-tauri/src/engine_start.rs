use std::collections::VecDeque;
use std::path::{Path, PathBuf};
use std::time::Duration;

pub const APP: &str = "FormCut";
pub const SHELL_ENV: &str = "FORMCUT_SHELL_PID";
pub const ADDRESS_WAIT: Duration = Duration::from_secs(90);
pub const KEY_WAIT: Duration = Duration::from_secs(10);
pub const EXIT_WAIT: Duration = Duration::from_secs(1);
pub const BUSY_CODE: i32 = 2;
const DATA_NAME: &str = "formcut";
const DATA_ENV: &str = "FORMCUT_DATA_DIR";
const PORTABLE_NAME: &str = "portable";
const LOGS_NAME: &str = "logs";
const LOG_START: &str = "engine-";
const LOG_END: &str = ".log";
const KEY_MARK: &str = "window-key";
const TAIL_LINES: usize = 12;
const LINE_CHARS: usize = 300;

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Wait {
    Address,
    Key,
}

impl Wait {
    pub fn limit(self) -> Duration {
        match self {
            Wait::Address => ADDRESS_WAIT,
            Wait::Key => KEY_WAIT,
        }
    }

    pub fn what(self) -> &'static str {
        match self {
            Wait::Address => "its engine to say which address it serves on",
            Wait::Key => "its engine to hand over the key for the window",
        }
    }
}

#[derive(Debug, PartialEq)]
pub enum Failure {
    Missing,
    NotStarted(String),
    Stopped(Option<i32>),
    TimedOut(Wait),
    Window(String),
    Later(Option<i32>),
    Output(String),
}

impl Failure {
    pub fn ran(&self) -> bool {
        !matches!(self, Failure::Missing | Failure::NotStarted(_))
    }

    pub fn after_the_window(self) -> Failure {
        match self {
            Failure::Stopped(code) => Failure::Later(code),
            other => other,
        }
    }
}

#[derive(Default)]
pub struct Tail(VecDeque<String>);

impl Tail {
    pub fn push(&mut self, line: &str) {
        if line.contains(KEY_MARK) {
            return;
        }
        let clean: String = line
            .chars()
            .filter(|c| !c.is_control())
            .take(LINE_CHARS)
            .collect();
        if clean.trim().is_empty() {
            return;
        }
        if self.0.len() == TAIL_LINES {
            self.0.pop_front();
        }
        self.0.push_back(clean);
    }

    pub fn lines(&self) -> Vec<String> {
        self.0.iter().cloned().collect()
    }
}

pub fn sentence(failure: &Failure) -> String {
    match failure {
        Failure::Missing => format!(
            "{APP} could not start: its engine program is missing from the install. Installing {APP} again puts it back."
        ),
        Failure::NotStarted(reason) => format!("{APP} could not start its engine: {reason}"),
        Failure::Stopped(Some(BUSY_CODE)) => format!(
            "{APP} could not start: another copy of its engine holds its data folder. {APP} is probably open already; look for its window."
        ),
        Failure::Stopped(Some(code)) => format!(
            "{APP} could not start: its engine stopped with code {code} before the window could open."
        ),
        Failure::Stopped(None) => {
            format!("{APP} could not start: its engine stopped before the window could open.")
        }
        Failure::TimedOut(wait) => format!(
            "{APP} could not start: it waited {} seconds for {} and that did not happen.",
            wait.limit().as_secs(),
            wait.what()
        ),
        Failure::Window(reason) => format!("{APP} could not open its window: {reason}"),
        Failure::Later(Some(code)) => format!(
            "{APP}'s engine stopped with code {code} while {APP} was open. Open {APP} again to go on."
        ),
        Failure::Later(None) => {
            format!("{APP}'s engine stopped while {APP} was open. Open {APP} again to go on.")
        }
        Failure::Output(reason) => format!(
            "{APP} can no longer read what its engine says: {reason} Open {APP} again to go on."
        ),
    }
}

pub fn message(failure: &Failure, tail: &[String], log: Option<&Path>) -> String {
    let mut text = sentence(failure);
    if !tail.is_empty() {
        text.push_str("\n\nThe engine's last lines:\n");
        text.push_str(&tail.join("\n"));
    } else if matches!(
        failure,
        Failure::Stopped(_) | Failure::TimedOut(_) | Failure::Later(_)
    ) {
        text.push_str("\n\nThe engine wrote nothing before that.");
    }
    if let Some(path) = log {
        text.push_str("\n\nThe engine's log: ");
        text.push_str(&path.to_string_lossy());
    }
    text
}

pub fn data_folder(
    os: &str,
    var: &dyn Fn(&str) -> Option<String>,
    home: Option<&Path>,
    beside: Option<&Path>,
    there: &dyn Fn(&Path) -> bool,
) -> Option<PathBuf> {
    if let Some(raw) = var(DATA_ENV).filter(|value| !value.is_empty()) {
        return match (raw.strip_prefix('~'), home) {
            (Some(rest), Some(home))
                if rest.is_empty() || rest.starts_with('/') || rest.starts_with('\\') =>
            {
                Some(home.join(rest.trim_start_matches(['/', '\\'])))
            }
            _ => Some(PathBuf::from(raw)),
        };
    }
    if let Some(portable) = beside.map(|folder| folder.join(PORTABLE_NAME)) {
        if there(&portable) {
            return Some(portable);
        }
    }
    let base = match os {
        "macos" => home?.join("Library").join("Application Support"),
        "windows" => match var("LOCALAPPDATA") {
            Some(local) => PathBuf::from(local),
            None => home?.to_path_buf(),
        },
        _ => match var("XDG_DATA_HOME") {
            Some(share) => PathBuf::from(share),
            None => home?.join(".local").join("share"),
        },
    };
    Some(base.join(DATA_NAME))
}

pub fn logs_folder(
    os: &str,
    var: &dyn Fn(&str) -> Option<String>,
    home: Option<&Path>,
    beside: Option<&Path>,
    there: &dyn Fn(&Path) -> bool,
) -> Option<PathBuf> {
    data_folder(os, var, home, beside, there).map(|folder| folder.join(LOGS_NAME))
}

pub fn newest_log(names: &[String]) -> Option<&String> {
    names
        .iter()
        .filter(|name| name.starts_with(LOG_START) && name.ends_with(LOG_END))
        .max()
}

pub fn engine_log() -> Option<PathBuf> {
    let var = |name: &str| std::env::var(name).ok();
    let own = std::env::current_exe().ok();
    let beside = own.as_deref().and_then(Path::parent);
    let folder = logs_folder(
        std::env::consts::OS,
        &var,
        std::env::home_dir().as_deref(),
        beside,
        &|path| path.is_dir(),
    )?;
    let folder = match std::env::current_dir() {
        Ok(here) if folder.is_relative() => here.join(folder),
        _ => folder,
    };
    let names: Vec<String> = std::fs::read_dir(&folder)
        .map(|entries| {
            entries
                .flatten()
                .filter_map(|entry| entry.file_name().into_string().ok())
                .collect()
        })
        .unwrap_or_default();
    match newest_log(&names) {
        Some(name) => Some(folder.join(name)),
        None => Some(folder),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn only(name: &'static str, value: &'static str) -> impl Fn(&str) -> Option<String> {
        move |asked| (asked == name).then(|| value.to_string())
    }

    #[test]
    fn the_tail_keeps_the_last_lines_and_never_the_window_key() {
        let mut tail = Tail::default();
        for n in 0..15 {
            tail.push(&format!("line {n}"));
        }
        tail.push("formcut-window-key: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA");
        tail.push("   ");
        tail.push(&"x".repeat(1000));
        let lines = tail.lines();
        assert_eq!(lines.len(), TAIL_LINES);
        assert_eq!(lines[0], "line 4");
        assert_eq!(lines[TAIL_LINES - 1].len(), LINE_CHARS);
        assert!(lines.iter().all(|line| !line.contains("window-key")));
    }

    #[test]
    fn every_failure_has_its_sentence_the_last_lines_and_the_log() {
        let log = Path::new("/data/logs/engine-20261120-070000.log");
        let said = vec!["formcut is already running on /data (engine process 7).".to_string()];
        let busy = message(&Failure::Stopped(Some(BUSY_CODE)), &said, Some(log));
        assert!(busy.starts_with(
            "FormCut could not start: another copy of its engine holds its data folder."
        ));
        assert!(!busy.contains("Some("));
        assert!(busy.contains(
            "The engine's last lines:\nformcut is already running on /data (engine process 7)."
        ));
        assert!(busy.ends_with("The engine's log: /data/logs/engine-20261120-070000.log"));
        assert!(message(&Failure::Stopped(Some(3)), &[], Some(log)).contains("stopped with code 3"));
        assert!(message(&Failure::Stopped(None), &[], None)
            .ends_with("The engine wrote nothing before that."));
        assert!(message(&Failure::Missing, &[], None).ends_with("puts it back."));
        assert!(
            sentence(&Failure::NotStarted("Access is denied.".to_string()))
                .ends_with("its engine: Access is denied.")
        );
        assert_eq!(
            sentence(&Failure::Window("no display".to_string())),
            "FormCut could not open its window: no display"
        );
    }

    #[test]
    fn an_engine_that_stops_under_an_open_window_is_said_in_its_own_words() {
        assert_eq!(
            Failure::Stopped(Some(1)).after_the_window(),
            Failure::Later(Some(1))
        );
        assert_eq!(
            Failure::TimedOut(Wait::Key).after_the_window(),
            Failure::TimedOut(Wait::Key)
        );
        assert_eq!(
            sentence(&Failure::Later(Some(1))),
            "FormCut's engine stopped with code 1 while FormCut was open. Open FormCut again to go on."
        );
        assert_eq!(
            sentence(&Failure::Later(None)),
            "FormCut's engine stopped while FormCut was open. Open FormCut again to go on."
        );
        assert!(sentence(&Failure::Output("broken pipe.".to_string())).contains("broken pipe."));
        assert!(Failure::Later(None).ran());
        assert!(!Failure::Missing.ran());
        assert!(!Failure::NotStarted(String::new()).ran());
    }

    #[test]
    fn a_wait_that_runs_out_says_how_long_and_for_what() {
        assert!(sentence(&Failure::TimedOut(Wait::Address))
            .contains("waited 90 seconds for its engine to say which address it serves on"));
        assert!(sentence(&Failure::TimedOut(Wait::Key))
            .contains("waited 10 seconds for its engine to hand over the key for the window"));
    }

    #[test]
    fn the_logs_are_where_the_engine_writes_them() {
        let home = Path::new("/home/u");
        let beside = Path::new("/opt/app");
        let none = |_: &str| None;
        let nothing = |_: &Path| false;
        let end = Path::new("formcut").join("logs");
        assert_eq!(
            logs_folder("linux", &none, Some(home), Some(beside), &nothing),
            Some(home.join(".local").join("share").join(&end))
        );
        assert_eq!(
            logs_folder(
                "linux",
                &only("XDG_DATA_HOME", "/x/share"),
                Some(home),
                None,
                &nothing
            ),
            Some(Path::new("/x/share").join(&end))
        );
        assert_eq!(
            logs_folder("macos", &none, Some(home), None, &nothing),
            Some(home.join("Library").join("Application Support").join(&end))
        );
        assert_eq!(
            logs_folder(
                "windows",
                &only("LOCALAPPDATA", "/local"),
                Some(home),
                None,
                &nothing
            ),
            Some(Path::new("/local").join(&end))
        );
        assert_eq!(
            logs_folder("windows", &none, Some(home), None, &nothing),
            Some(home.join(&end))
        );
        assert_eq!(
            logs_folder(
                "windows",
                &only("FORMCUT_DATA_DIR", "/d/x"),
                None,
                Some(beside),
                &|_: &Path| true
            ),
            Some(Path::new("/d/x").join("logs"))
        );
        assert_eq!(
            logs_folder(
                "linux",
                &only("FORMCUT_DATA_DIR", "~/x"),
                Some(home),
                None,
                &nothing
            ),
            Some(home.join("x").join("logs"))
        );
        assert_eq!(
            logs_folder("linux", &none, Some(home), Some(beside), &|path: &Path| {
                path == beside.join("portable")
            }),
            Some(beside.join("portable").join("logs"))
        );
        assert_eq!(logs_folder("linux", &none, None, None, &nothing), None);
    }

    #[test]
    fn the_newest_run_log_is_the_one_named() {
        let names: Vec<String> = [
            "engine-20261119-235959.log",
            "formcut-engine-errors.log",
            "engine-20261120-070000.log",
            "engine-20261120-065959.log",
            "engine-99999999-000000.txt",
        ]
        .iter()
        .map(|name| name.to_string())
        .collect();
        assert_eq!(
            newest_log(&names),
            Some(&"engine-20261120-070000.log".to_string())
        );
        assert_eq!(newest_log(&["notes.txt".to_string()]), None);
    }
}
