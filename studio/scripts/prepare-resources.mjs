import https from 'https'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'
import { execSync } from 'child_process'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const studioDir = path.join(__dirname, '..')
const resourcesDir = path.join(studioDir, 'resources')
const pythonDir = path.join(resourcesDir, 'python')
const wheelsDir = path.join(resourcesDir, 'wheels')
const repoRoot = path.join(studioDir, '..')

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true })
    console.log(`Created directory: ${dir}`)
  }
}

function download(url, destPath) {
  return new Promise((resolve, reject) => {
    console.log(`Downloading ${url} ...`)
    const file = fs.createWriteStream(destPath)

    function get(currentUrl) {
      https.get(currentUrl, (res) => {
        if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          file.close()
          get(res.headers.location)
          return
        }
        if (res.statusCode !== 200) {
          file.close()
          fs.unlink(destPath, () => {})
          reject(new Error(`Download failed: HTTP ${res.statusCode} for ${currentUrl}`))
          return
        }
        res.pipe(file)
        file.on('finish', () => {
          file.close()
          resolve()
        })
        file.on('error', (err) => {
          file.close()
          fs.unlink(destPath, () => {})
          reject(err)
        })
      }).on('error', (err) => {
        file.close()
        fs.unlink(destPath, () => {})
        reject(err)
      })
    }

    get(url)
  })
}

async function prepareWindowsPython() {
  const pythonExe = path.join(pythonDir, 'python.exe')
  if (fs.existsSync(pythonExe)) {
    console.log('Windows Python embeddable already exists, skipping download.')
    return
  }

  const zipUrl = 'https://www.python.org/ftp/python/3.13.3/python-3.13.3-embed-amd64.zip'
  const zipPath = path.join(resourcesDir, 'python-embed.zip')

  try {
    await download(zipUrl, zipPath)
    console.log('Extracting Python embeddable...')
    execSync(
      `powershell -Command "Expand-Archive -Path \\"${zipPath}\\" -DestinationPath \\"${pythonDir}\\" -Force"`,
      { stdio: 'inherit' }
    )
    fs.unlinkSync(zipPath)
    console.log('Python embeddable extracted.')

    // Uncomment "import site" in the ._pth file so pip works
    const pthFiles = fs.readdirSync(pythonDir).filter((f) => f.endsWith('._pth'))
    for (const pthFile of pthFiles) {
      const pthPath = path.join(pythonDir, pthFile)
      let content = fs.readFileSync(pthPath, 'utf8')
      content = content.replace(/^#\s*import site\s*$/m, 'import site')
      fs.writeFileSync(pthPath, content, 'utf8')
      console.log(`Patched ${pthFile}: uncommented 'import site'`)
    }

    // Install pip into the embeddable Python
    const getPipPath = path.join(resourcesDir, 'get-pip.py')
    await download('https://bootstrap.pypa.io/get-pip.py', getPipPath)
    console.log('Installing pip into embeddable Python...')
    execSync(`"${pythonExe}" "${getPipPath}"`, { stdio: 'inherit' })
    fs.unlinkSync(getPipPath)
    console.log('pip installed.')
  } catch (err) {
    console.error('ERROR: Failed to prepare Windows Python:', err.message)
    process.exit(1)
  }
}

async function prepareMacPython() {
  const pythonBin = path.join(pythonDir, 'bin', 'python3')
  if (fs.existsSync(pythonBin)) {
    console.log('Mac Python already exists, skipping download.')
    return
  }

  const arch = process.arch === 'arm64' ? 'aarch64' : 'x86_64'
  const tarUrl = `https://github.com/indygreg/python-build-standalone/releases/download/20241016/cpython-3.13.0+20241016-${arch}-apple-darwin-install_only.tar.gz`
  const tarPath = path.join(resourcesDir, 'python-mac.tar.gz')

  try {
    await download(tarUrl, tarPath)
    console.log('Extracting Mac Python...')
    execSync(`tar -xzf "${tarPath}" -C "${pythonDir}" --strip-components=1`, { stdio: 'inherit' })
    fs.unlinkSync(tarPath)
    console.log('Mac Python extracted.')
  } catch (err) {
    console.error('ERROR: Failed to prepare Mac Python:', err.message)
    process.exit(1)
  }
}

async function prepareLinuxPython() {
  const pythonBin = path.join(pythonDir, 'bin', 'python3')
  if (fs.existsSync(pythonBin)) {
    console.log('Linux Python already exists, skipping download.')
    return
  }

  const tarUrl =
    'https://github.com/indygreg/python-build-standalone/releases/download/20241016/cpython-3.13.0+20241016-x86_64-unknown-linux-gnu-install_only.tar.gz'
  const tarPath = path.join(resourcesDir, 'python-linux.tar.gz')

  try {
    await download(tarUrl, tarPath)
    console.log('Extracting Linux Python...')
    execSync(`tar -xzf "${tarPath}" -C "${pythonDir}" --strip-components=1`, { stdio: 'inherit' })
    fs.unlinkSync(tarPath)
    console.log('Linux Python extracted.')
  } catch (err) {
    console.error('ERROR: Failed to prepare Linux Python:', err.message)
    process.exit(1)
  }
}

function hasWheelFile() {
  if (!fs.existsSync(wheelsDir)) return false
  return fs.readdirSync(wheelsDir).some((f) => f.endsWith('.whl'))
}

function buildWheel() {
  if (hasWheelFile()) {
    console.log('Wheel already exists in resources/wheels/, skipping build.')
    return
  }

  console.log('Building pathly-adapters wheel...')
  const systemPython = process.platform === 'win32' ? 'python' : 'python3'
  try {
    execSync(
      `${systemPython} -m build --wheel --outdir "${wheelsDir}"`,
      { stdio: 'inherit', cwd: repoRoot }
    )
    console.log('Wheel built successfully.')

    // Download dependency wheels using the BUNDLED Python so platform tags match
    console.log('Downloading dependency wheels...')
    const bundledPython = process.platform === 'win32'
      ? path.join(pythonDir, 'python.exe')
      : path.join(pythonDir, 'bin', 'python3')
    execSync(
      `"${bundledPython}" -m pip download --dest "${wheelsDir}" pyyaml flask --only-binary=:all:`,
      { stdio: 'inherit' }
    )
    console.log('Dependency wheels downloaded.')
  } catch (err) {
    console.error('ERROR: Failed to build wheel:', err.message)
    process.exit(1)
  }
}

async function main() {
  console.log('Preparing resources for Pathly Studio...')

  ensureDir(pythonDir)
  ensureDir(wheelsDir)

  if (process.platform === 'win32') {
    await prepareWindowsPython()
  } else if (process.platform === 'darwin') {
    await prepareMacPython()
  } else {
    await prepareLinuxPython()
  }

  buildWheel()

  console.log('Resources ready.')
}

main()
