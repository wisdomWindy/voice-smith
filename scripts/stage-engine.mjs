// Stage the vendored engine source into `src-tauri/resources/upstream` so the
// Tauri installer bundles it. Weight directories are *never* copied: they are
// runtime mounts from `<data>/assets` (see sidecar/engine_paths.py).
//
// Usage: node scripts/stage-engine.mjs [--check]

import { cpSync, existsSync, lstatSync, mkdirSync, readFileSync, readdirSync, realpathSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(scriptDir, '..')
const sourceRoot = join(repoRoot, 'vendor', 'GPT-SoVITS')
const resourceRoot = join(repoRoot, 'src-tauri', 'resources')
const targetRoot = join(resourceRoot, 'upstream', 'GPT-SoVITS')
const checkOnly = process.argv.includes('--check')

// Engine-relative directories that hold weights or generated artefacts.
const excludedDirs = new Set([
  'GPT_SoVITS/pretrained_models',
  'GPT_SoVITS/text/G2PWModel',
  'GPT_SoVITS/Accel/vendor',
  'GPT_SoVITS/BigVGAN/demo',
  'GPT_SoVITS/BigVGAN/filelists',
  'tools/uvr5/uvr5_weights',
  'tools/asr/models',
  'tools/AP_BWE_main/24kto48k',
  'tools/denoise-model',
  'runtime',
  '.venv',
  'TEMP',
  'output',
  '__pycache__',
])

// Directories created at runtime as junctions to <data>/assets (must not leak).
const mountedDirs = new Set([
  'GPT_SoVITS/pretrained_models',
  'GPT_SoVITS/text/G2PWModel',
  'tools/uvr5/uvr5_weights',
  'tools/asr/models',
  'tools/AP_BWE_main/24kto48k',
  'runtime',
])

const excludedExtensions = new Set(['.pyc', '.pth', '.pt', '.ckpt', '.onnx', '.bin', '.zip', '.pkl', '.dll', '.npy'])

function isReparsePoint(abs) {
  try {
    return realpathSync.native(abs).toLowerCase() !== resolve(abs).toLowerCase()
  } catch {
    return true
  }
}

function walk(dir, rel = '') {
  const entries = []
  for (const name of readdirSync(dir)) {
    const abs = join(dir, name)
    const relPath = rel ? `${rel}/${name}` : name
    const info = lstatSync(abs)
    if (info.isSymbolicLink() || isReparsePoint(abs)) {
      // Runtime junction/symlink to <data>/assets: never bundle weight bytes.
      continue
    }
    if (info.isDirectory()) {
      if (excludedDirs.has(relPath) || name === '__pycache__') continue
      entries.push(...walk(abs, relPath))
      continue
    }
    if (excludedExtensions.has(name.slice(name.lastIndexOf('.')).toLowerCase())) continue
    if (/_cache\.pickle$/i.test(name)) continue
    entries.push({ abs, relPath, bytes: info.size })
  }
  return entries
}

function fail(message) {
  console.error(`stage-engine: ${message}`)
  process.exit(1)
}

if (!existsSync(join(sourceRoot, 'GPT_SoVITS', 'TTS_infer_pack', 'TTS.py'))) {
  fail(`vendored engine source missing: ${sourceRoot}`)
}

const files = walk(sourceRoot)
const totalBytes = files.reduce((sum, item) => sum + item.bytes, 0)
const biggest = files.reduce((max, item) => (item.bytes > max.bytes ? item : max), { bytes: 0, relPath: '' })

for (const dir of mountedDirs) {
  if (existsSync(join(sourceRoot, dir))) {
    console.warn(`stage-engine: WARNING ${dir} exists in vendor/ (runtime mount leaked?) - it will be skipped`)
  }
}

if (biggest.bytes > 32 * 1024 * 1024) {
  fail(`refusing to stage ${biggest.relPath} (${(biggest.bytes / 1024 / 1024).toFixed(1)} MB): weights must not be bundled`)
}

if (checkOnly) {
  console.log(`stage-engine: OK ${files.length} files, ${(totalBytes / 1024 / 1024).toFixed(1)} MB (no weights)`)
  process.exit(0)
}

// Only the generated engine copy is replaced; resources/upstream/README.md stays
// tracked so a fresh clone already satisfies Tauri's compile-time resource check.
rmSync(targetRoot, { recursive: true, force: true })
mkdirSync(targetRoot, { recursive: true })

for (const file of files) {
  const target = join(targetRoot, ...file.relPath.split('/'))
  mkdirSync(dirname(target), { recursive: true })
  cpSync(file.abs, target)
}

const manifestPath = join(sourceRoot, 'VENDOR_MANIFEST.json')
let vendor = {}
if (existsSync(manifestPath)) {
  vendor = JSON.parse(readFileSync(manifestPath, 'utf-8'))
}
writeFileSync(
  join(targetRoot, 'SOURCE.json'),
  JSON.stringify(
    {
      stagedAt: new Date().toISOString(),
      source: 'vendor/GPT-SoVITS',
      files: files.length,
      bytes: totalBytes,
      vendorManifest: vendor.count ? { count: vendor.count, source: vendor.source, copiedAt: vendor.copied_at } : {},
      weights: 'installed separately into <data>/assets (see docs/packaging.md)',
    },
    null,
    2,
  ),
  'utf-8',
)

console.log(
  `stage-engine: bundled ${files.length} files (${(totalBytes / 1024 / 1024).toFixed(1)} MB) -> ${relative(repoRoot, targetRoot)}`,
)
if (biggest.bytes > 0) {
  console.log(`stage-engine: largest file ${biggest.relPath} (${(biggest.bytes / 1024).toFixed(0)} KB)`)
}
