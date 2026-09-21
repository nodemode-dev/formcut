// Desktop builds of the shell exist only to develop it; phones start from the library's entry point.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    formcut_mobile_lib::run();
}
