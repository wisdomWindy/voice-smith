use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs::{self, OpenOptions};
use std::io::Read;
use std::net::{TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};
use tauri::{Emitter, Manager, State};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

// Bump only when the runtime dependency layout changes; UI-only releases keep
// the installed runtime instead of forcing another multi-GB download.
const RUNTIME_REVISION: &str = "v5-deps-2026-11-24.1";

#[derive(Clone, Serialize)]
struct RuntimeProgress {
    percent: u8,
    stage: String,
}

fn emit_runtime_progress(app: &tauri::AppHandle, percent: u8, stage: &str) {
    let _ = app.emit(
        "runtime-progress",
        RuntimeProgress {
            percent,
            stage: stage.to_string(),
        },
    );
}

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

fn install_root() -> PathBuf {    if cfg!(debug_assertions) {
        return project_root();
    }
    std::env::current_exe()
        .ok()
        .and_then(|path| path.parent().map(|parent| parent.to_path_buf()))
        .unwrap_or_else(project_root)
}

fn runtime_root() -> PathBuf {
    if let Ok(explicit) = std::env::var("VOICE_SMITH_RUNTIME") {
        let trimmed = explicit.trim();
        if !trimmed.is_empty() {
            return PathBuf::from(trimmed);
        }
    }
    install_root().join("runtime")
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

fn python_exe_name() -> &'static str {
    if cfg!(target_os = "windows") {
        "python.exe"
    } else {
        "python"
    }
}

/// The engine source is vendored with the app; weights live in `<data>/assets`.
/// Resolution order mirrors `sidecar/engine_paths.py`.
fn has_engine_source(path: &Path) -> bool {
    path.join("GPT_SoVITS")
        .join("TTS_infer_pack")
        .join("TTS.py")
        .is_file()
}

fn engine_source_candidates(
    dev_root: &Path,
    install_root: &Path,
    resource_root: &Path,
    data_dir: &Path,
) -> Vec<PathBuf> {
    let mut candidates = Vec::new();
    if cfg!(debug_assertions) {
        candidates.push(dev_root.join("vendor").join("GPT-SoVITS"));
    }
    candidates.extend([
        resource_root.join("upstream").join("GPT-SoVITS"),
        resource_root.join("resources").join("upstream").join("GPT-SoVITS"),
        install_root.join("resources").join("upstream").join("GPT-SoVITS"),
        install_root.join("upstream").join("GPT-SoVITS"),
        // legacy: one offline pack installed source + weights under <install>/engine
        install_root.join("engine").join("GPT-SoVITS"),
        data_dir.join("engine").join("GPT-SoVITS"),
    ]);
    candidates
}

fn resolve_engine_source(
    dev_root: &Path,
    install_root: &Path,
    resource_root: &Path,
    data_dir: &Path,
) -> PathBuf {
    if let Ok(explicit) = std::env::var("VOICE_SMITH_ENGINE") {
        let trimmed = explicit.trim();
        if !trimmed.is_empty() {
            return PathBuf::from(trimmed);
        }
    }
    engine_source_candidates(dev_root, install_root, resource_root, data_dir)
        .into_iter()
        .find(|path| has_engine_source(path))
        .unwrap_or_else(|| {
            if cfg!(debug_assertions) {
                dev_root.join("vendor").join("GPT-SoVITS")
            } else {
                install_root.join("engine").join("GPT-SoVITS")
            }
        })
}

fn log_tail(path: &Path, lines: usize) -> String {
    fs::read_to_string(path)
        .unwrap_or_default()
        .lines()
        .rev()
        .take(lines)
        .collect::<Vec<_>>()
        .into_iter()
        .rev()
        .collect::<Vec<_>>()
        .join("\n")
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
    let runtime_root = runtime_root();
    let embedded_python = runtime_root.join(python_exe_name());
    let embedded_script = runtime_root.join("sidecar").join("app.py");
    let deps_ready = runtime_root.join("deps").join("core").is_dir()
        && runtime_root.join("deps").join("torch").is_dir();
    let revision_ok = fs::read_to_string(runtime_root.join(".voicesmith-runtime"))
        .map(|value| value.trim() == RUNTIME_REVISION)
        .unwrap_or(false);
    let embedded_ready =
        embedded_python.exists() && embedded_script.exists() && deps_ready && revision_ok;
    let packaged = if embedded_ready {
        None
    } else {
        find_packaged_engine(&resource_root, &dev_root, &install_root())
    };
    let dev_script = dev_root.join("sidecar").join("app.py");
    if !embedded_ready && packaged.is_none() && !(cfg!(debug_assertions) && dev_script.exists()) {
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

    let (working_root, mut command) = if embedded_ready {
        let mut command = Command::new(&embedded_python);
        command.arg(&embedded_script);
        (runtime_root.clone(), command)
    } else if let Some(exe) = packaged {
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

    // Engine source ships with the app (vendor/upstream); weights and tools are
    // downloaded into <data>/assets. The sidecar mounts them into the engine tree.
    let install_dir = install_root();
    let engine_root = resolve_engine_source(&dev_root, &install_dir, &resource_root, &data_dir);
    let assets_dir = data_dir.join("assets");
    if std::env::var_os("VOICE_SMITH_ENGINE").is_none() {
        command.env("VOICE_SMITH_ENGINE", &engine_root);
    }
    if std::env::var_os("VOICE_SMITH_ASSETS_DIR").is_none() {
        command.env("VOICE_SMITH_ASSETS_DIR", &assets_dir);
    }
    command.env("VOICE_SMITH_DATA_DIR", &data_dir);

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

    let address = format!("127.0.0.1:{port}");
    for _ in 0..120 {
        if TcpStream::connect(&address).is_ok() {
            return Ok(state.info.lock().unwrap().clone());
        }
        std::thread::sleep(std::time::Duration::from_millis(250));
    }
    let tail = log_tail(&log_path, 12);
    stop_engine(state);
    Err(format!(
        "sidecar did not start. Log: {}\n{}",
        log_path.display(),
        tail
    ))
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

#[derive(Clone, Deserialize)]
struct PackPart {
    url: String,
    #[serde(default)]
    size: Option<u64>,
}

#[derive(Clone, Deserialize)]
struct PackManifest {
    #[serde(default)]
    sha256: String,
    #[serde(default)]
    size: Option<u64>,
    #[serde(default)]
    parts: Vec<PackPart>,
}

#[derive(Deserialize)]
struct BundleComponent {
    name: String,
    manifest: String,
    #[serde(default)]
    sha256: String,
    #[serde(default)]
    size: Option<u64>,
}

#[derive(Deserialize)]
struct RuntimeBundle {
    #[serde(default)]
    components: Vec<BundleComponent>,
}

struct ComponentPlan {
    name: String,
    manifest: PackManifest,
    sha256: String,
    size: Option<u64>,
}

fn curl_program() -> &'static str {
    if cfg!(target_os = "windows") {
        "curl.exe"
    } else {
        "curl"
    }
}

fn download_url(url: &str, target: &Path) -> Result<(), String> {
    let mut last_error = String::new();
    for attempt in 0..5 {
        let mut curl = Command::new(curl_program());
        curl.args([
            "-L",
            "--fail",
            "--http1.1",
            "--retry",
            "8",
            "--retry-delay",
            "3",
            "--retry-all-errors",
            "--connect-timeout",
            "20",
            "--speed-time",
            "90",
            "--speed-limit",
            "1024",
            "-C",
            "-",
            "-o",
        ])
        .arg(target)
        .arg(url);
        #[cfg(target_os = "windows")]
        curl.creation_flags(CREATE_NO_WINDOW);
        let status = curl.status().map_err(|e| format!("curl failed: {e}"))?;
        if status.success() {
            return Ok(());
        }
        let code = status.code().unwrap_or(-1);
        last_error = format!("download failed: {status} (curl code {code})");
        // Only drop the partial file when the server rejects range resume.
        // Network resets (56) and timeouts keep the bytes for the next attempt.
        if code == 33 && target.exists() {
            let _ = fs::remove_file(target);
        }
        std::thread::sleep(std::time::Duration::from_secs(3 * (attempt + 1)));
    }
    Err(last_error)
}

fn download_range(url: &str, target: &Path, start: u64, end: u64) -> Result<(), String> {
    let mut curl = Command::new(curl_program());
    curl.args([
        "-L",
        "--fail",
        "--http1.1",
        "--retry",
        "8",
        "--retry-delay",
        "3",
        "--retry-all-errors",
        "--connect-timeout",
        "20",
        "--speed-time",
        "90",
        "--speed-limit",
        "1024",
        "--range",
        &format!("{start}-{end}"),
        "-o",
    ])
    .arg(target)
    .arg(url);
    #[cfg(target_os = "windows")]
    curl.creation_flags(CREATE_NO_WINDOW);
    let status = curl.status().map_err(|e| format!("curl failed: {e}"))?;
    if !status.success() {
        return Err(format!("range download failed: {status}"));
    }
    Ok(())
}

fn download_part(url: &str, target: &Path, size: Option<u64>) -> Result<(), String> {
    let Some(size) = size else {
        return download_url(url, target);
    };
    if size < 900 * 1024 * 1024 {
        return download_url(url, target);
    }
    let half = size / 2;
    let left = target.with_extension("part-a");
    let right = target.with_extension("part-b");
    let _ = fs::remove_file(&left);
    let _ = fs::remove_file(&right);
    let result = std::thread::scope(|scope| {
        let a = scope.spawn(|| download_range(url, &left, 0, half - 1));
        let b = scope.spawn(|| download_range(url, &right, half, size - 1));
        let first = a.join().map_err(|_| "range worker panicked".to_string())?;
        let second = b.join().map_err(|_| "range worker panicked".to_string())?;
        first?;
        second?;
        Ok::<(), String>(())
    });
    if let Err(error) = result {
        let _ = fs::remove_file(&left);
        let _ = fs::remove_file(&right);
        return Err(error);
    }
    let mut output = fs::File::create(target).map_err(|e| e.to_string())?;
    for chunk in [&left, &right] {
        let mut input = fs::File::open(chunk).map_err(|e| e.to_string())?;
        std::io::copy(&mut input, &mut output).map_err(|e| e.to_string())?;
    }
    let _ = fs::remove_file(&left);
    let _ = fs::remove_file(&right);
    Ok(())
}

fn runtime_dir(_app: &tauri::AppHandle) -> PathBuf {
    runtime_root()
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
    let dir = runtime_dir(&app);
    let frozen = dir.join(engine_exe_name());
    let py = dir.join(python_exe_name());
    let script = dir.join("sidecar").join("app.py");
    let deps = dir.join("deps");
    let split_ready = py.exists()
        && script.exists()
        && deps.join("core").is_dir()
        && deps.join("torch").is_dir();
    let marker_ok = fs::read_to_string(dir.join(".voicesmith-runtime"))
        .map(|value| value.trim() == RUNTIME_REVISION)
        .unwrap_or(false);
    let installed = frozen.exists() || (split_ready && marker_ok);
    RuntimeStatus {
        installed,
        path: if frozen.exists() { frozen } else { py }.to_string_lossy().to_string(),
    }
}

#[tauri::command]
async fn install_runtime(
    app: tauri::AppHandle,
    url: String,
    sha256: Option<String>,
) -> Result<EngineInfo, String> {
    let app_for_task = app.clone();
    {
        let state = app.state::<EngineState>();
        stop_engine(state.inner());
    }
    let result = tauri::async_runtime::spawn_blocking(move || {
        let state = app_for_task.state::<EngineState>();
        install_runtime_blocking(&app_for_task, state.inner(), url, sha256)
    })
    .await
    .map_err(|e| format!("runtime install task failed: {e}"))?;
    if result.is_ok() {
        let _ = fs::write(
            runtime_dir(&app).join(".voicesmith-runtime"),
            RUNTIME_REVISION,
        );
        emit_runtime_progress(&app, 100, "Runtime installed");
    }
    result
}

fn parse_json<T>(text: &str) -> Result<T, String>
where
    T: for<'de> Deserialize<'de>,
{
    serde_json::from_str(text.trim_start_matches('\u{feff}').trim()).map_err(|e| e.to_string())
}

fn valid_sha256(value: &str) -> bool {
    value.len() == 64 && value.chars().all(|c| c.is_ascii_hexdigit())
}

fn ensure_manifest(manifest: &PackManifest, label: &str) -> Result<(), String> {
    if manifest.parts.is_empty() {
        return Err(format!("{label} has no parts"));
    }
    if manifest.parts.iter().any(|part| part.url.trim().is_empty()) {
        return Err(format!("{label} has an empty part URL"));
    }
    Ok(())
}

fn download_json(url: &str, target: &Path) -> Result<String, String> {
    download_url(url, target)?;
    let text = fs::read_to_string(target).map_err(|e| e.to_string())?;
    let _ = fs::remove_file(target);
    Ok(text)
}

/// Parse either a runtime bundle (base/core/torch components) or a legacy
/// single-pack manifest. A direct .7z URL is also accepted for compatibility.
fn resolve_runtime_plan(
    data_dir: &Path,
    url: &str,
    sha256: Option<String>,
) -> Result<Vec<ComponentPlan>, String> {
    let url = url.trim();
    if !url.to_lowercase().ends_with(".json") {
        let manifest = PackManifest {
            sha256: sha256.unwrap_or_default().trim().to_string(),
            size: None,
            parts: vec![PackPart {
                url: url.to_string(),
                size: None,
            }],
        };
        let expected = manifest.sha256.clone();
        return Ok(vec![ComponentPlan {
            name: "runtime".into(),
            manifest,
            sha256: expected,
            size: None,
        }]);
    }

    let text = download_json(url, &data_dir.join("runtime-install.json"))?;
    let value: serde_json::Value = parse_json(&text)?;
    if value.get("components").is_none() {
        let manifest: PackManifest = serde_json::from_value(value).map_err(|e| e.to_string())?;
        ensure_manifest(&manifest, "runtime manifest")?;
        let mut expected = sha256.unwrap_or_default().trim().to_string();
        if expected.is_empty() {
            expected = manifest.sha256.trim().to_string();
        }
        let size = manifest.size;
        return Ok(vec![ComponentPlan {
            name: "runtime".into(),
            manifest,
            sha256: expected,
            size,
        }]);
    }

    let bundle: RuntimeBundle = serde_json::from_value(value).map_err(|e| e.to_string())?;
    if bundle.components.is_empty() {
        return Err("runtime bundle has no components".into());
    }
    let mut plans: Vec<ComponentPlan> = Vec::new();
    for component in bundle.components {
        let name = component.name.trim().to_lowercase();
        if !matches!(name.as_str(), "base" | "core" | "torch") {
            return Err(format!("unknown runtime component: {}", component.name));
        }
        if plans.iter().any(|plan| plan.name == name) {
            return Err(format!("duplicate runtime component: {name}"));
        }
        let manifest_url = component.manifest.trim();
        if manifest_url.is_empty() {
            return Err(format!("{name} component manifest URL is empty"));
        }
        let text = download_json(
            manifest_url,
            &data_dir.join(format!("runtime-{name}-manifest.json")),
        )?;
        let manifest: PackManifest = parse_json(&text)?;
        ensure_manifest(&manifest, &format!("{name} manifest"))?;
        let manifest_sha = manifest.sha256.trim().to_lowercase();
        let bundle_sha = component.sha256.trim().to_lowercase();
        if !manifest_sha.is_empty() && !bundle_sha.is_empty() && manifest_sha != bundle_sha {
            return Err(format!("{name} manifest sha256 does not match runtime-bundle.json"));
        }
        if let (Some(manifest_size), Some(bundle_size)) = (manifest.size, component.size) {
            if manifest_size != bundle_size {
                return Err(format!("{name} manifest size does not match runtime-bundle.json"));
            }
        }
        let expected = if !manifest_sha.is_empty() {
            manifest_sha
        } else {
            bundle_sha
        };
        if !valid_sha256(&expected) {
            return Err(format!("{name} component is missing a valid sha256"));
        }
        let size = manifest.size.or(component.size);
        plans.push(ComponentPlan {
            name,
            manifest,
            sha256: expected,
            size,
        });
    }
    for required in ["base", "core", "torch"] {
        if !plans.iter().any(|plan| plan.name == required) {
            return Err(format!("runtime bundle is missing the {required} component"));
        }
    }
    plans.sort_by_key(|plan| match plan.name.as_str() {
        "base" => 0,
        "core" => 1,
        _ => 2,
    });
    Ok(plans)
}

fn component_progress(downloaded: u64, total: u64) -> u8 {
    if total == 0 {
        return 15;
    }
    (6 + downloaded.saturating_mul(84) / total).min(92) as u8
}

fn download_component(
    app: &tauri::AppHandle,
    data_dir: &Path,
    plan: &ComponentPlan,
    downloaded: &mut u64,
    total: u64,
) -> Result<PathBuf, String> {
    let pack = data_dir.join(format!("runtime-{}.7z", plan.name));
    let _ = fs::remove_file(&pack);
    let mut output = fs::File::create(&pack).map_err(|e| e.to_string())?;
    let part_count = plan.manifest.parts.len();
    for (index, part) in plan.manifest.parts.iter().enumerate() {
        let part_path = data_dir.join(format!("runtime-{}-part-{index:02}.bin", plan.name));
        let _ = fs::remove_file(&part_path);
        download_part(part.url.trim(), &part_path, part.size)?;
        let actual_size = fs::metadata(&part_path).map_err(|e| e.to_string())?.len();
        if let Some(expected_size) = part.size {
            if actual_size != expected_size {
                let _ = fs::remove_file(&part_path);
                return Err(format!(
                    "{} part {index} size mismatch: {actual_size} != {expected_size}",
                    plan.name
                ));
            }
        }
        let mut input = fs::File::open(&part_path).map_err(|e| e.to_string())?;
        std::io::copy(&mut input, &mut output).map_err(|e| e.to_string())?;
        drop(input);
        let _ = fs::remove_file(&part_path);
        *downloaded = downloaded.saturating_add(actual_size);
        emit_runtime_progress(
            app,
            component_progress(*downloaded, total),
            &format!(
                "Downloading {} ({}/{})",
                plan.name,
                index + 1,
                part_count
            ),
        );
    }
    drop(output);

    if let Some(expected_size) = plan.size {
        let actual_size = fs::metadata(&pack).map_err(|e| e.to_string())?.len();
        if actual_size != expected_size {
            let _ = fs::remove_file(&pack);
            return Err(format!(
                "{} pack size mismatch: {actual_size} != {expected_size}",
                plan.name
            ));
        }
    }
    if !plan.sha256.trim().is_empty() {
        emit_runtime_progress(app, 92, &format!("Verifying {}", plan.name));
        let actual = sha256_file(&pack)?;
        if !actual.eq_ignore_ascii_case(plan.sha256.trim()) {
            let _ = fs::remove_file(&pack);
            return Err(format!("{} sha256 mismatch: {actual}", plan.name));
        }
    }
    Ok(pack)
}

fn extract_7zr(seven: &Path, pack: &Path, dest: &Path) -> Result<(), String> {
    fs::create_dir_all(dest).map_err(|e| e.to_string())?;
    let mut command = Command::new(seven);
    command
        .arg("x")
        .arg(pack)
        .arg(format!("-o{}", dest.display()))
        .arg("-y")
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(target_os = "windows")]
    command.creation_flags(CREATE_NO_WINDOW);
    let status = command
        .status()
        .map_err(|e| format!("7zr failed: {e}"))?;
    if !status.success() {
        return Err(format!("7zr extract failed: {status}"));
    }
    Ok(())
}

fn move_dir_contents(from: &Path, to: &Path) -> Result<(), String> {
    fs::create_dir_all(to).map_err(|e| e.to_string())?;
    for entry in fs::read_dir(from).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        fs::rename(entry.path(), to.join(entry.file_name())).map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// Base pack layout is `python/` + `sidecar/`. The Python payload is flattened
/// into <runtime> so the runtime is <runtime>\\python.exe with <runtime>\\sidecar.
fn remove_runtime_dir(runtime: &Path) -> Result<(), String> {
    if !runtime.exists() {
        return Ok(());
    }
    fs::remove_dir_all(runtime).map_err(|e| {
        format!(
            "无法清理旧运行时，可能仍被 VoiceSmith 占用；请重启应用后重试: {e}"
        )
    })
}

fn install_runtime_base(
    seven: &Path,
    pack: &Path,
    runtime: &Path,
    staging: &Path,
) -> Result<(), String> {
    let _ = fs::remove_dir_all(staging);
    extract_7zr(seven, pack, staging)?;
    let python_dir = staging.join("python");
    let has_python_dir = python_dir.is_dir();
    remove_runtime_dir(runtime)?;
    fs::create_dir_all(runtime).map_err(|e| e.to_string())?;
    if has_python_dir {
        move_dir_contents(&python_dir, runtime)?;
        for entry in fs::read_dir(staging).map_err(|e| e.to_string())? {
            let entry = entry.map_err(|e| e.to_string())?;
            if entry.file_name().to_string_lossy() == "python" {
                continue;
            }
            fs::rename(entry.path(), runtime.join(entry.file_name()))
                .map_err(|e| e.to_string())?;
        }
    } else {
        move_dir_contents(staging, runtime)?;
    }
    let _ = fs::remove_dir_all(staging);
    let python = runtime.join(python_exe_name());
    if !python.exists() {
        return Err(format!("runtime base is missing {}", python.display()));
    }
    Ok(())
}

fn contains_wheel(dir: &Path) -> bool {
    let Ok(entries) = fs::read_dir(dir) else {
        return false;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            if contains_wheel(&path) {
                return true;
            }
        } else if path
            .extension()
            .map(|ext| ext.eq_ignore_ascii_case("whl"))
            .unwrap_or(false)
        {
            return true;
        }
    }
    false
}

/// Wheel packs are archives rooted at `core/` or `torch/`, extracted under
/// <runtime>\\deps so bootstrap.py finds <runtime>\\deps\\{core,torch}.
fn install_runtime_deps(
    seven: &Path,
    pack: &Path,
    runtime: &Path,
    kind: &str,
) -> Result<(), String> {
    let deps = runtime.join("deps");
    let target = deps.join(kind);
    let _ = fs::remove_dir_all(&target);
    fs::create_dir_all(&deps).map_err(|e| e.to_string())?;
    extract_7zr(seven, pack, &deps)?;
    if !target.is_dir() {
        return Err(format!("{kind} pack did not contain {kind}/"));
    }
    if !contains_wheel(&target) {
        return Err(format!("{kind} pack contains no .whl files"));
    }
    Ok(())
}

fn install_legacy_pack(
    seven: &Path,
    pack: &Path,
    runtime: &Path,
    staging: &Path,
) -> Result<(), String> {
    let _ = fs::remove_dir_all(staging);
    extract_7zr(seven, pack, staging)?;
    remove_runtime_dir(runtime)?;
    fs::create_dir_all(runtime).map_err(|e| e.to_string())?;
    move_dir_contents(staging, runtime)?;
    let _ = fs::remove_dir_all(staging);
    Ok(())
}

fn run_runtime_bootstrap(python: &Path, runtime: &Path, log_path: &Path) -> Result<(), String> {
    let script = runtime.join("sidecar").join("bootstrap.py");
    if !script.exists() {
        return Err(format!("bootstrap script not found: {}", script.display()));
    }
    if let Some(parent) = log_path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let log = OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_path)
        .map_err(|e| e.to_string())?;
    let log_err = log.try_clone().map_err(|e| e.to_string())?;
    let mut command = Command::new(python);
    command
        .arg(&script)
        .current_dir(runtime)
        .env("PIP_DISABLE_PIP_VERSION_CHECK", "1")
        .env("PYTHONUTF8", "1")
        .stdout(Stdio::from(log))
        .stderr(Stdio::from(log_err));
    #[cfg(target_os = "windows")]
    command.creation_flags(CREATE_NO_WINDOW);
    let status = command
        .status()
        .map_err(|e| format!("bootstrap failed to start: {e}"))?;
    if !status.success() {
        return Err(format!(
            "python bootstrap failed: {status}. Log: {}\n{}",
            log_path.display(),
            log_tail(log_path, 12)
        ));
    }
    Ok(())
}

fn verify_runtime_imports(python: &Path, runtime: &Path) -> Result<(), String> {
    let mut command = Command::new(python);
    command
        .args([
            "-c",
            "import fastapi, uvicorn, pydantic, torch, transformers, peft, matplotlib, ffmpeg",
        ])
        .current_dir(runtime);
    #[cfg(target_os = "windows")]
    command.creation_flags(CREATE_NO_WINDOW);
    let output = command
        .output()
        .map_err(|e| format!("runtime verification failed to start: {e}"))?;
    if output.status.success() {
        return Ok(());
    }
    let detail = String::from_utf8_lossy(&output.stderr);
    Err(format!(
        "运行时依赖不完整，请释放磁盘空间后重新安装运行时：{}",
        detail.trim().chars().take(800).collect::<String>()
    ))
}

fn install_runtime_blocking(
    app: &tauri::AppHandle,
    state: &EngineState,
    url: String,
    sha256: Option<String>,
) -> Result<EngineInfo, String> {
    if url.trim().is_empty() {
        return Err("runtime pack URL is empty".into());
    }
    emit_runtime_progress(app, 2, "Preparing runtime");
    let data_dir = install_root();
    fs::create_dir_all(&data_dir).map_err(|e| e.to_string())?;
    let free = fs2::available_space(&data_dir).map_err(|e| e.to_string())?;
    if free < 15 * 1024 * 1024 * 1024 {
        return Err(format!(
            "磁盘空间不足：运行时安装至少需要 15GB 可用空间，当前仅 {:.1}GB",
            free as f64 / 1024.0 / 1024.0 / 1024.0
        ));
    }
    emit_runtime_progress(app, 4, "Reading runtime bundle");
    let plans = resolve_runtime_plan(&data_dir, url.trim(), sha256)?;
    let bundle_install = plans.iter().any(|plan| plan.name != "runtime");
    let total: u64 = plans.iter().filter_map(|plan| plan.size).sum();
    let mut downloaded = 0u64;
    let mut packs = Vec::new();
    for plan in &plans {
        emit_runtime_progress(
            app,
            component_progress(downloaded, total),
            &format!("Downloading {} runtime component", plan.name),
        );
        packs.push(download_component(
            app,
            &data_dir,
            plan,
            &mut downloaded,
            total,
        )?);
    }

    let seven = find_7zr(app).ok_or("7zr.exe not found")?;
    let target = runtime_dir(app);
    let staging = data_dir.join("runtime-staging");
    stop_engine(state);
    if bundle_install {
        let base_index = plans
            .iter()
            .position(|plan| plan.name == "base")
            .ok_or("runtime bundle is missing base")?;
        let core_index = plans
            .iter()
            .position(|plan| plan.name == "core")
            .ok_or("runtime bundle is missing core")?;
        let torch_index = plans
            .iter()
            .position(|plan| plan.name == "torch")
            .ok_or("runtime bundle is missing torch")?;
        emit_runtime_progress(app, 94, "Installing runtime base");
        install_runtime_base(&seven, &packs[base_index], &target, &staging)?;
        emit_runtime_progress(app, 96, "Installing core dependencies");
        install_runtime_deps(&seven, &packs[core_index], &target, "core")?;
        emit_runtime_progress(app, 97, "Installing torch dependencies");
        install_runtime_deps(&seven, &packs[torch_index], &target, "torch")?;
        for pack in &packs {
            let _ = fs::remove_file(pack);
        }
        emit_runtime_progress(app, 98, "Installing Python dependencies");
        let logs_dir = install_root().join("data").join("logs");
        fs::create_dir_all(&logs_dir).map_err(|e| e.to_string())?;
        let python = target.join(python_exe_name());
        run_runtime_bootstrap(&python, &target, &logs_dir.join("bootstrap.log"))?;
        verify_runtime_imports(&python, &target)?;
        fs::write(target.join(".voicesmith-runtime"), RUNTIME_REVISION).map_err(|e| e.to_string())?;
        emit_runtime_progress(app, 99, "Starting engine");
    } else {
        emit_runtime_progress(app, 90, "Extracting runtime");
        install_legacy_pack(&seven, &packs[0], &target, &staging)?;
        for pack in &packs {
            let _ = fs::remove_file(pack);
        }
        emit_runtime_progress(app, 99, "Starting engine");
    }
    start_engine(app, state)
}

#[tauri::command]
fn delete_output(path: String) -> Result<(), String> {
    let target = PathBuf::from(&path).canonicalize().map_err(|e| e.to_string())?;
    let root = install_root().join("data").join("outputs");
    let root = root.canonicalize().map_err(|e| e.to_string())?;
    if !target.starts_with(&root) {
        return Err("refusing to delete outside outputs".into());
    }
    fs::remove_file(&target).map_err(|e| e.to_string())
}

#[tauri::command]
fn create_project(name: Option<String>) -> Result<String, String> {
    let root = install_root().join("projects");
    fs::create_dir_all(&root).map_err(|e| e.to_string())?;
    let raw = name.unwrap_or_default();
    let mut clean = String::new();
    for ch in raw.trim().trim_matches('.').chars() {
        if ch.is_control() || r#"<>:"/\|?*"#.contains(ch) {
            continue;
        }
        clean.push(ch);
    }
    let clean = clean.trim();
    if clean.is_empty() {
        return Err("项目名称不能为空".into());
    }
    let clean: String = clean.chars().take(60).collect();
    if clean.is_empty() {
        return Err("项目名称不能为空".into());
    }
    let path = root.join(&clean);
    if path.exists() {
        return Err("项目名称已存在".into());
    }
    for child in ["datasets", "training", "outputs", "logs"] {
        fs::create_dir_all(path.join(child)).map_err(|e| e.to_string())?;
    }
    Ok(path.to_string_lossy().to_string())
}

#[tauri::command]
fn pick_audio_file() -> Option<String> {
    rfd::FileDialog::new()
        .add_filter("Audio", &["wav", "mp3", "flac"])
        .pick_file()
        .map(|path| path.to_string_lossy().to_string())
}

#[tauri::command]
fn pick_audio_files() -> Vec<String> {
    rfd::FileDialog::new()
        .add_filter("Audio", &["wav", "mp3", "flac"])
        .pick_files()
        .unwrap_or_default()
        .into_iter()
        .map(|path| path.to_string_lossy().to_string())
        .collect()
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
            pick_audio_files,
            create_project,
            delete_output,
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

#[cfg(all(test, target_os = "windows"))]
mod tests {
    use super::*;

    fn seven_zip() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("sidecar")
            .join("7zr.exe")
    }

    fn make_archive(source: &Path, pack: &Path) {
        let seven = seven_zip();
        assert!(seven.exists(), "missing 7zr: {}", seven.display());
        let status = Command::new(seven)
            .arg("a")
            .arg("-t7z")
            .arg(pack)
            .arg(source)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .expect("failed to run 7zr");
        assert!(status.success(), "7zr failed for {}", source.display());
    }

    fn test_root(name: &str) -> PathBuf {
        let root = std::env::temp_dir().join(format!(
            "voicesmith-{name}-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(&root).unwrap();
        root
    }

    #[test]
    fn parses_runtime_bundle() {
        let json = r#"{
            "version": "0.2.3",
            "platform": "windows-x64",
            "components": [
                {"name": "base", "manifest": "https://example/base.json", "sha256": "aa", "size": 10},
                {"name": "core", "manifest": "https://example/core.json", "sha256": "bb", "size": 20},
                {"name": "torch", "manifest": "https://example/torch.json", "sha256": "cc", "size": 30}
            ]
        }"#;
        let value: serde_json::Value = parse_json(json).unwrap();
        assert!(value.get("components").is_some());
        let bundle: RuntimeBundle = serde_json::from_value(value).unwrap();
        assert_eq!(bundle.components.len(), 3);
        assert_eq!(bundle.components[0].name, "base");
    }

    #[test]
    fn sha_and_progress_helpers() {
        assert!(valid_sha256(&"a".repeat(64)));
        assert!(!valid_sha256("abc"));
        assert!(!valid_sha256(&"g".repeat(64)));
        assert_eq!(component_progress(0, 0), 15);
        assert_eq!(component_progress(0, 100), 6);
        assert!(component_progress(100, 100) <= 92);
        assert!(component_progress(100, 100) > 80);
    }

    #[test]
    fn installs_base_and_deps_layout() {
        let root = test_root("runtime-layout");
        let seven = seven_zip();

        fs::create_dir_all(root.join("base/python")).unwrap();
        fs::write(root.join("base/python/python.exe"), b"stub").unwrap();
        fs::write(root.join("base/python/python311._pth"), b"Lib").unwrap();
        fs::create_dir_all(root.join("base/sidecar")).unwrap();
        fs::write(root.join("base/sidecar/app.py"), b"print('app')").unwrap();
        let base_pack = root.join("base.7z");
        make_archive(&root.join("base").join("*"), &base_pack);

        let runtime = root.join("runtime");
        install_runtime_base(&seven, &base_pack, &runtime, &root.join("staging")).unwrap();
        assert!(runtime.join("python.exe").is_file());
        assert!(runtime.join("python311._pth").is_file());
        assert!(runtime.join("sidecar/app.py").is_file());

        for kind in ["core", "torch"] {
            let stage = root.join(format!("{kind}-stage"));
            fs::create_dir_all(stage.join(kind)).unwrap();
            fs::write(
                stage.join(kind).join(format!("{kind}-1.0-py3-none-any.whl")),
                b"wheel",
            )
            .unwrap();
            let pack = root.join(format!("{kind}.7z"));
            make_archive(&stage.join("*"), &pack);
            install_runtime_deps(&seven, &pack, &runtime, kind).unwrap();
            assert!(contains_wheel(&runtime.join("deps").join(kind)));
        }

        let _ = fs::remove_dir_all(root);
    }

    fn make_engine(root: &Path) {
        let engine = root.join("GPT_SoVITS").join("TTS_infer_pack");
        fs::create_dir_all(&engine).unwrap();
        fs::write(engine.join("TTS.py"), b"# engine").unwrap();
    }

    #[test]
    fn engine_source_prefers_vendored_checkout() {
        let root = test_root("engine-vendor");
        let dev = root.join("repo");
        make_engine(&dev.join("vendor").join("GPT-SoVITS"));

        let found = engine_source_candidates(
            &dev,
            &root.join("install"),
            &root.join("resources"),
            &root.join("data"),
        )
        .into_iter()
        .find(|path| has_engine_source(path))
        .expect("vendored engine missing");
        assert_eq!(found, dev.join("vendor").join("GPT-SoVITS"));
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn engine_source_finds_bundled_upstream() {
        let root = test_root("engine-upstream");
        let install = root.join("install");
        make_engine(&install.join("resources").join("upstream").join("GPT-SoVITS"));

        let found = engine_source_candidates(
            &root.join("repo"),
            &install,
            &install.join("resources"),
            &root.join("data"),
        )
        .into_iter()
        .find(|path| has_engine_source(path))
        .expect("bundled engine missing");
        assert!(found.ends_with("upstream/GPT-SoVITS") || found.ends_with("upstream\\GPT-SoVITS"));
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn engine_source_falls_back_to_legacy_engine_dir() {
        let root = test_root("engine-legacy");
        let install = root.join("install");
        make_engine(&install.join("engine").join("GPT-SoVITS"));

        let found = engine_source_candidates(
            &root.join("repo"),
            &install,
            &install.join("resources"),
            &root.join("data"),
        )
        .into_iter()
        .find(|path| has_engine_source(path))
        .expect("legacy engine missing");
        assert_eq!(found, install.join("engine").join("GPT-SoVITS"));
        let _ = fs::remove_dir_all(root);
    }
}
