use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs::{self, OpenOptions};
use std::io::Read;
use std::net::TcpListener;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};
use tauri::{Manager, State};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

#[derive(Clone, Serialize)]
struct EngineInfo {
    port: u16,
    token: String,
    status: String,
    pid: Option<u32>,
    error: Option<String>,
}

impl Default for EngineInfo {
    fn default() -> Self {
        Self {
            port: 0,
            token: String::new(),
            status: "idle".into(),
            pid: None,
            error: None,
        }
    }
}

#[derive(Default)]
struct EngineState {
    info: Mutex<EngineInfo>,
    child: Mutex<Option<Child>>,
}

fn pick_port() -> Result<u16, String> {
    let listener = TcpListener::bind("127.0.0.1:0").map_err(|e| e.to_string())?;
    let port = listener.local_addr().map_err(|e| e.to_string())?.port();
    drop(listener);
    Ok(port)
}

fn make_token() -> String {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or_default();
    format!("vs_{:x}_{:x}", nanos, std::process::id())
}

fn project_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .map(|p| p.to_path_buf())
        .unwrap_or_else(|| PathBuf::from("."))
}

fn install_root() -> PathBuf {
    if cfg!(debug_assertions) {
        return project_root();
    }
    std::env::current_exe()
        .ok()
        .and_then(|path| path.parent().map(|parent| parent.to_path_buf()))
        .unwrap_or_else(project_root)
}

fn resolve_python(root: &PathBuf) -> PathBuf {
    if let Ok(explicit) = std::env::var("VOICE_SMITH_PYTHON") {
        if !explicit.trim().is_empty() {
            return PathBuf::from(explicit);
        }
    }
    let venv = root.join("sidecar").join(".venv").join("Scripts").join("python.exe");
    if venv.exists() {
        return venv;
    }
    PathBuf::from("python")
}

fn find_packaged_engine(resource_root: &PathBuf, dev_root: &PathBuf, data_dir: &Path) -> Option<PathBuf> {
    if let Ok(explicit) = std::env::var("VOICE_SMITH_ENGINE_EXE") {
        let path = PathBuf::from(explicit);
        if path.exists() {
            return Some(path);
        }
    }
    let exe_name = engine_exe_name();
    let candidates = [
        data_dir.join("runtime").join(exe_name),
        resource_root.join("voicesmith-engine").join(exe_name),
        resource_root.join("resources").join("voicesmith-engine").join(exe_name),
        resource_root.join("engine").join("voicesmith-engine").join(exe_name),
    ];
    let mut candidates = candidates.to_vec();
    if cfg!(debug_assertions) {
        candidates.push(dev_root.join("sidecar").join("voicesmith-engine").join(exe_name));
    }
    if let Some(exe_dir) = std::env::current_exe().ok().and_then(|path| path.parent().map(|p| p.to_path_buf())) {
        for candidate in [
            exe_dir.join("voicesmith-engine").join("voicesmith-engine.exe"),
            exe_dir.join("resources").join("voicesmith-engine").join("voicesmith-engine.exe"),
        ] {
            if candidate.exists() {
                return Some(candidate);
            }
        }
    }
    candidates.into_iter().find(|path| path.exists())
}

fn stop_engine(state: &EngineState) {
    let mut guard = state.child.lock().unwrap();
    if let Some(mut child) = guard.take() {
        let _ = child.kill();
        let _ = child.wait();
    }
    let mut info = state.info.lock().unwrap();
    info.status = "stopped".into();
    info.pid = None;
}

fn start_engine(app: &tauri::AppHandle, state: &EngineState) -> Result<EngineInfo, String> {
    stop_engine(state);

    let dev_root = project_root();
    let resource_root = app
        .path()
        .resource_dir()
        .unwrap_or_else(|_| dev_root.clone());
    let data_dir = if cfg!(debug_assertions) {
        app.path()
            .app_data_dir()
            .unwrap_or_else(|_| dev_root.join(".data"))
    } else {
        install_root().join("data")
    };
    fs::create_dir_all(&data_dir).map_err(|e| e.to_string())?;
    let packaged = find_packaged_engine(&resource_root, &dev_root, &install_root());
    let dev_script = dev_root.join("sidecar").join("app.py");
    if packaged.is_none() && !(cfg!(debug_assertions) && dev_script.exists()) {
        let mut info = state.info.lock().unwrap();
        *info = EngineInfo {
            port: 0,
            token: String::new(),
            status: "runtime_missing".into(),
            pid: None,
            error: None,
        };
        return Ok(info.clone());
    }

    let port = pick_port()?;
    let token = make_token();
    let logs_dir = data_dir.join("logs");
    fs::create_dir_all(&logs_dir).map_err(|e| e.to_string())?;
    let log_path = logs_dir.join("sidecar.log");
    let log = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)
        .map_err(|e| e.to_string())?;
    let log_err = log.try_clone().map_err(|e| e.to_string())?;

    let (working_root, mut command) = if let Some(exe) = packaged {
        let root = exe.parent().map(|p| p.to_path_buf()).unwrap_or_else(|| dev_root.clone());
        (root, Command::new(&exe))
    } else {
        let script = dev_root.join("sidecar").join("app.py");
        if !script.exists() {
            return Err(format!("sidecar script not found: {}", script.display()));
        }
        let python = resolve_python(&dev_root);
        let mut command = Command::new(&python);
        command.arg(&script);
        (dev_root.clone(), command)
    };

    command
        .arg("--port")
        .arg(port.to_string())
        .arg("--token")
        .arg(&token)
        .arg("--data-dir")
        .arg(&data_dir)
        .current_dir(&working_root)
        .stdout(Stdio::from(log))
        .stderr(Stdio::from(log_err));

    let engine_root = install_root().join("engine").join("GPT-SoVITS");
    if std::env::var("VOICE_SMITH_ENGINE").is_err() {
        command.env("VOICE_SMITH_ENGINE", engine_root);
    }

    #[cfg(target_os = "windows")]
    command.creation_flags(CREATE_NO_WINDOW);

    let child = command
        .spawn()
        .map_err(|e| format!("failed to start sidecar in {}: {e}", working_root.display()))?;
    let pid = child.id();

    {
        let mut info = state.info.lock().unwrap();
        *info = EngineInfo {
            port,
            token,
            status: "starting".into(),
            pid: Some(pid),
            error: None,
        };
    }
    *state.child.lock().unwrap() = Some(child);

    Ok(state.info.lock().unwrap().clone())
}

#[tauri::command]
fn get_engine_info(state: State<EngineState>) -> EngineInfo {
    let mut info = state.info.lock().unwrap().clone();
    let mut child_guard = state.child.lock().unwrap();
    if let Some(child) = child_guard.as_mut() {
        if let Ok(Some(status)) = child.try_wait() {
            info.status = "error".into();
            info.error = Some(format!("sidecar exited: {status}"));
        }
    }
    info
}

#[tauri::command]
fn restart_engine(app: tauri::AppHandle, state: State<EngineState>) -> Result<EngineInfo, String> {
    start_engine(&app, state.inner())
}

#[derive(Serialize)]
struct RuntimeStatus {
    installed: bool,
    path: String,
}

#[derive(Deserialize)]
struct PackPart {
    url: String,
}

#[derive(Deserialize)]
struct PackManifest {
    #[serde(default)]
    sha256: String,
    parts: Vec<PackPart>,
}

fn curl_program() -> &'static str {
    if cfg!(target_os = "windows") {
        "curl.exe"
    } else {
        "curl"
    }
}

fn download_url(url: &str, target: &Path) -> Result<(), String> {
    let mut curl = Command::new(curl_program());
    curl.args(["-L", "--fail", "--retry", "3", "-o"])
        .arg(target)
        .arg(url);
    #[cfg(target_os = "windows")]
    curl.creation_flags(CREATE_NO_WINDOW);
    let status = curl.status().map_err(|e| format!("curl failed: {e}"))?;
    if !status.success() {
        return Err(format!("download failed: {status}"));
    }
    Ok(())
}

fn runtime_dir(_app: &tauri::AppHandle) -> PathBuf {
    install_root().join("runtime")
}

fn find_7zr(app: &tauri::AppHandle) -> Option<PathBuf> {
    let resource_root = app.path().resource_dir().ok()?;
    let mut candidates = vec![
        resource_root.join("7zr.exe"),
        resource_root.join("7zr"),
        resource_root.join("resources").join("7zr.exe"),
        resource_root.join("resources").join("7zr"),
    ];
    if let Some(exe_dir) = std::env::current_exe().ok().and_then(|p| p.parent().map(|v| v.to_path_buf())) {
        candidates.push(exe_dir.join("7zr.exe"));
        candidates.push(exe_dir.join("7zr"));
    }
    candidates.into_iter().find(|p| p.exists())
}

fn sha256_file(path: &Path) -> Result<String, String> {
    let mut file = fs::File::open(path).map_err(|e| e.to_string())?;
    let mut hasher = Sha256::new();
    let mut buffer = vec![0u8; 1024 * 1024];
    loop {
        let read = file.read(&mut buffer).map_err(|e| e.to_string())?;
        if read == 0 {
            break;
        }
        hasher.update(&buffer[..read]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

#[tauri::command]
fn platform_tag() -> &'static str {
    if cfg!(target_os = "windows") {
        "windows-x64"
    } else if cfg!(target_os = "macos") && cfg!(target_arch = "aarch64") {
        "macos-arm64"
    } else if cfg!(target_os = "macos") {
        "macos-intel"
    } else {
        "unsupported"
    }
}

#[tauri::command]
fn runtime_status(app: tauri::AppHandle) -> RuntimeStatus {
    let path = runtime_dir(&app).join(engine_exe_name());
    RuntimeStatus {
        installed: path.exists(),
        path: path.to_string_lossy().to_string(),
    }
}

#[tauri::command]
fn install_runtime(
    app: tauri::AppHandle,
    state: State<EngineState>,
    url: String,
    sha256: Option<String>,
) -> Result<EngineInfo, String> {
    if url.trim().is_empty() {
        return Err("runtime pack URL is empty".into());
    }
    let data_dir = install_root();
    fs::create_dir_all(&data_dir).map_err(|e| e.to_string())?;
    let pack = data_dir.join("runtime-pack.7z");
    let mut expected = sha256.unwrap_or_default();
    let mut urls = vec![url.trim().to_string()];
    if url.trim().to_lowercase().ends_with(".json") {
        let manifest_path = data_dir.join("runtime-manifest.json");
        download_url(url.trim(), &manifest_path)?;
        let text = fs::read_to_string(&manifest_path).map_err(|e| e.to_string())?;
        let text = text.trim_start_matches('\u{feff}');
        let manifest: PackManifest = serde_json::from_str(text).map_err(|e| e.to_string())?;
        if !manifest.sha256.is_empty() {
            expected = manifest.sha256;
        }
        urls = manifest.parts.into_iter().map(|part| part.url).collect();
        let _ = fs::remove_file(&manifest_path);
    }
    let mut output = fs::File::create(&pack).map_err(|e| e.to_string())?;
    for (index, part_url) in urls.iter().enumerate() {
        let part = data_dir.join(format!("runtime-part-{index:02}.bin"));
        download_url(part_url, &part)?;
        let mut input = fs::File::open(&part).map_err(|e| e.to_string())?;
        std::io::copy(&mut input, &mut output).map_err(|e| e.to_string())?;
        let _ = fs::remove_file(&part);
    }
    drop(output);
    if !expected.trim().is_empty() {
        let actual = sha256_file(&pack)?;
        if actual.to_lowercase() != expected.trim().to_lowercase() {
            let _ = fs::remove_file(&pack);
            return Err(format!("runtime sha256 mismatch: {actual}"));
        }
    }
    let seven = find_7zr(&app).ok_or("7zr.exe not found")?;
    let target = runtime_dir(&app);
    let staging = data_dir.join("runtime-staging");
    let _ = fs::remove_dir_all(&staging);
    fs::create_dir_all(&staging).map_err(|e| e.to_string())?;
    let mut extract = Command::new(&seven);
    extract
        .arg("x")
        .arg(&pack)
        .arg(format!("-o{}", staging.display()))
        .arg("-y");
    #[cfg(target_os = "windows")]
    extract.creation_flags(CREATE_NO_WINDOW);
    let status = extract
        .status()
        .map_err(|e| format!("7zr failed: {e}"))?;
    let _ = fs::remove_file(&pack);
    if !status.success() {
        return Err(format!("runtime extract failed: {status}"));
    }
    let _ = fs::remove_dir_all(&target);
    fs::create_dir_all(&target).map_err(|e| e.to_string())?;
    for entry in fs::read_dir(&staging).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        let dest = target.join(entry.file_name());
        fs::rename(entry.path(), dest).map_err(|e| e.to_string())?;
    }
    let _ = fs::remove_dir_all(&staging);
    start_engine(&app, state.inner())
}

#[tauri::command]
fn pick_audio_file() -> Option<String> {
    rfd::FileDialog::new()
        .add_filter("Audio", &["wav", "mp3", "flac"])
        .pick_file()
        .map(|path| path.to_string_lossy().to_string())
}

#[tauri::command]
fn pick_training_file() -> Option<String> {
    rfd::FileDialog::new()
        .add_filter("Dataset list", &["list", "txt"])
        .pick_file()
        .map(|path| path.to_string_lossy().to_string())
}

fn engine_exe_name() -> &'static str {
    if cfg!(target_os = "windows") {
        "voicesmith-engine.exe"
    } else {
        "voicesmith-engine"
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .manage(EngineState::default())
        .invoke_handler(tauri::generate_handler![
            get_engine_info,
            restart_engine,
            platform_tag,
            runtime_status,
            install_runtime,
            pick_audio_file,
            pick_training_file
        ])
        .setup(|app| {
            let handle = app.handle().clone();
            let state = app.state::<EngineState>();
            if let Err(error) = start_engine(&handle, state.inner()) {
                eprintln!("VoiceSmith: {error}");
                let mut info = state.info.lock().unwrap();
                info.status = "error".into();
                info.error = Some(error);
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building VoiceSmith")
        .run(|app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                let state = app_handle.state::<EngineState>();
                stop_engine(state.inner());
            }
        });
}
