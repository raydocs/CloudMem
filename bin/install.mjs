#!/usr/bin/env node
import { chmodSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { basename, dirname, join, resolve } from 'node:path'
import { homedir } from 'node:os'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))

// 仓库根目录（bin/ 的父目录）
const REPO_ROOT = resolve(__dirname, '..')
const CLAUDE_DIR = join(homedir(), '.claude')
const SETTINGS_PATH = join(CLAUDE_DIR, 'settings.json')

// 仓库内真实 hooks（根据脚本语义与注释确认 event）
const CLOUDMEM_HOOKS = [
  // hooks/post-session.sh: "post-session" 会话收尾/落盘逻辑
  { file: 'hooks/post-session.sh', event: 'SessionEnd' },
  // hooks/mempal_save_hook.sh: 注释中明确写为 Claude Code "Stop" hook
  { file: 'hooks/mempal_save_hook.sh', event: 'Stop' },
  // hooks/mempal_precompact_hook.sh: 注释中明确写为 "PreCompact" hook
  { file: 'hooks/mempal_precompact_hook.sh', event: 'PreCompact' },
]

function readJson(path, fallback = {}) {
  if (!existsSync(path)) return fallback
  try {
    return JSON.parse(readFileSync(path, 'utf-8'))
  } catch (error) {
    throw new Error(`Invalid JSON: ${path} (${error.message})`)
  }
}

function writeJson(path, data) {
  mkdirSync(dirname(path), { recursive: true })
  writeFileSync(path, JSON.stringify(data, null, 2) + '\n')
}

function ensureExecutable(relativeHookPath) {
  const absPath = resolve(REPO_ROOT, relativeHookPath)
  if (!existsSync(absPath)) {
    throw new Error(`Hook file not found: ${absPath}`)
  }
  chmodSync(absPath, 0o755)
  return absPath
}

function findExactCommandIndex(entries, commandPath) {
  for (let i = 0; i < entries.length; i++) {
    const hooks = Array.isArray(entries[i]?.hooks) ? entries[i].hooks : []
    for (const hook of hooks) {
      if (hook?.type === 'command' && hook?.command === commandPath) {
        return i
      }
    }
  }
  return -1
}

function updateSameScriptPath(entries, commandPath, scriptBasename) {
  for (let i = 0; i < entries.length; i++) {
    const hooks = Array.isArray(entries[i]?.hooks) ? entries[i].hooks : []
    for (let j = 0; j < hooks.length; j++) {
      const hook = hooks[j]
      if (hook?.type !== 'command' || typeof hook?.command !== 'string') continue
      if (basename(hook.command) === scriptBasename) {
        if (hook.command !== commandPath) {
          hooks[j] = { ...hook, command: commandPath }
          return 'updated'
        }
        return 'skipped'
      }
    }
  }
  return null
}

function upsertHook(settings, event, commandPath, scriptBasename) {
  if (!settings || typeof settings !== 'object') settings = {}
  if (!settings.hooks || typeof settings.hooks !== 'object') settings.hooks = {}

  const existingEntries = Array.isArray(settings.hooks[event]) ? settings.hooks[event] : []

  if (findExactCommandIndex(existingEntries, commandPath) !== -1) {
    settings.hooks[event] = existingEntries
    return 'skipped'
  }

  const updated = updateSameScriptPath(existingEntries, commandPath, scriptBasename)
  if (updated) {
    settings.hooks[event] = existingEntries
    return updated
  }

  existingEntries.push({
    hooks: [{ type: 'command', command: commandPath }],
  })
  settings.hooks[event] = existingEntries
  return 'installed'
}

function main() {
  try {
    const settings = readJson(SETTINGS_PATH, {})
    const results = []

    for (const hook of CLOUDMEM_HOOKS) {
      const absPath = ensureExecutable(hook.file)
      const status = upsertHook(settings, hook.event, absPath, basename(hook.file))
      results.push({ event: hook.event, path: absPath, status })
    }

    writeJson(SETTINGS_PATH, settings)

    console.log('CloudMem hooks installation complete:')
    for (const result of results) {
      console.log(`- [${result.status}] ${result.event} -> ${result.path}`)
    }
  } catch (error) {
    console.error(`Install failed: ${error.message}`)
    process.exit(1)
  }
}

main()
