import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { gzipSync } from 'node:zlib'

const BUDGET_KB = 90
const assetsDir = join(process.cwd(), 'dist', 'assets')

let entries
try {
  entries = readdirSync(assetsDir).filter(
    (name) => name.startsWith('index-') && name.endsWith('.js'),
  )
} catch {
  console.error('dist/assets is missing. Run "pnpm build" first.')
  process.exit(1)
}

if (entries.length !== 1) {
  console.error(
    `Expected exactly one entry chunk (index-*.js), found ${entries.length}: ${entries.join(', ')}`,
  )
  process.exit(1)
}

const file = join(assetsDir, entries[0])
const gzipBytes = gzipSync(readFileSync(file), { level: 9 }).length
const gzipKb = gzipBytes / 1024

console.log(
  `Entry bundle ${entries[0]}: ${gzipKb.toFixed(2)} kB gzip (budget ${BUDGET_KB} kB)`,
)

if (gzipKb >= BUDGET_KB) {
  console.error(`Entry bundle exceeds the ${BUDGET_KB} kB gzip budget.`)
  process.exit(1)
}
