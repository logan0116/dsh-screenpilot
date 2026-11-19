/**
 * 侧边栏观察窗的 host 侧：同源路由 + sidecar 直连。
 *
 * 路由 /api/screenpilot：
 *   GET  /state   会话目标与 sidecar 存活
 *   GET  /frame   单帧 JPEG
 *   GET  /stream  SSE，逐帧推 {"jpeg","seq","ts"}
 *   POST /input   手动接管（click/scroll，坐标归一化 0..1）
 *
 * 帧由 sidecar 的 frame 命令产出，Node 直接走 unix socket，不经过 Python CLI，
 * 避免每次调用付 5 秒启动成本。
 */
import { createConnection } from 'node:net'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { homedir } from 'node:os'

export const ROUTE_PREFIX = '/api/screenpilot'

function stateDir() {
  const override = process.env.SCREENPILOT_STATE
  if (override) return dirname(override)
  const cache = process.env.XDG_CACHE_HOME || join(homedir(), '.cache')
  return join(cache, 'screenpilot')
}

export function currentSession() {
  try {
    const data = JSON.parse(readFileSync(join(stateDir(), 'session.json'), 'utf8'))
    if (!data || !data.host || !data.port) return null
    return { host: String(data.host), port: Number(data.port) }
  } catch {
    return null
  }
}

export function socketPath(target) {
  return join(stateDir(), `daemon-${target.host}-${target.port}.sock`)
}

/** 发一条命令给 sidecar；连不上时返回 NOT_STARTED 而不是抛错。 */
export function daemonRequest(target, cmd, args = {}, timeoutMs = 60000) {
  return new Promise((resolve) => {
    if (!target) {
      resolve({ ok: false, error: { code: 'NOT_STARTED', message: '还没有会话，先调用 screen_start' } })
      return
    }
    let done = false
    const sock = createConnection({ path: socketPath(target) })
    let buffer = ''
    const finish = (value) => {
      if (done) return
      done = true
      try { sock.destroy() } catch { /* noop */ }
      resolve(value)
    }
    sock.setTimeout(timeoutMs, () => finish({
      ok: false,
      error: { code: 'TIMEOUT', message: `sidecar 超过 ${Math.round(timeoutMs / 1000)} 秒没有回应` },
    }))
    sock.on('connect', () => sock.write(`${JSON.stringify({ cmd, args })}\n`))
    sock.on('data', (chunk) => {
      buffer += chunk.toString('utf8')
      if (!buffer.includes('\n')) return
      try {
        finish(JSON.parse(buffer.slice(0, buffer.indexOf('\n'))))
      } catch (err) {
        finish({ ok: false, error: { code: 'PROTOCOL_ERROR', message: String(err) } })
      }
    })
    sock.on('error', (err) => finish({
      ok: false,
      error: { code: 'NOT_STARTED', message: `没有常驻会话（${err.code || err.message}）` },
    }))
  })
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

function sendJson(res, status, body) {
  const payload = JSON.stringify(body)
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' })
  res.end(payload)
}

function readBody(req, limit = 65536) {
  return new Promise((resolve) => {
    let size = 0
    let data = ''
    req.on('data', (chunk) => {
      size += chunk.length
      if (size > limit) { req.destroy(); resolve(null); return }
      data += chunk.toString('utf8')
    })
    req.on('end', () => {
      try { resolve(JSON.parse(data || '{}')) } catch { resolve(null) }
    })
    req.on('error', () => resolve(null))
  })
}

export function registerRoutes(webServer, options = {}) {
  if (!webServer || typeof webServer.register !== 'function') return undefined
  const frameOptions = { scale: options.scale ?? 0.5, quality: options.quality ?? 60 }
  // 观察窗最后看到的画面尺寸：手动接管按它把归一化坐标换算回原图坐标
  let lastScreen = null

  const handler = async (req, resRaw) => {
    const res = resRaw
    const url = new URL(req.url || '/', 'http://127.0.0.1')
    const route = url.pathname.slice(ROUTE_PREFIX.length) || '/'
    const target = currentSession()

    if (route === '/state' && req.method === 'GET') {
      const probe = target ? await daemonRequest(target, 'ping', {}, 2000) : null
      sendJson(res, 200, {
        ok: true,
        session: target,
        daemon: { alive: Boolean(probe && probe.ok), pid: probe?.screen?.pid ?? null, screen: probe?.screen ?? null },
        stream: { scale: frameOptions.scale, quality: frameOptions.quality },
      })
      return
    }

    if (route === '/frame' && req.method === 'GET') {
      const frame = await daemonRequest(target, 'frame', frameOptions, 30000)
      if (!frame.ok) { sendJson(res, 503, frame); return }
      lastScreen = { w: frame.screen.w, h: frame.screen.h, imgW: frame.data.w, imgH: frame.data.h }
      const image = Buffer.from(frame.data.jpeg, 'base64')
      res.writeHead(200, { 'Content-Type': 'image/jpeg', 'Content-Length': image.length, 'Cache-Control': 'no-store' })
      res.end(image)
      return
    }

    if (route === '/stream' && req.method === 'GET') {
      res.writeHead(200, {
        'Content-Type': 'text/event-stream; charset=utf-8',
        'Cache-Control': 'no-store',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      })
      if (typeof res.flushHeaders === 'function') res.flushHeaders()
      let closed = false
      let seq = 0
      req.on('close', () => { closed = true })
      res.on('close', () => { closed = true })
      while (!closed) {
        const frame = await daemonRequest(target, 'frame', frameOptions, 30000)
        if (closed) break
        if (!frame.ok) {
          res.write(`data: ${JSON.stringify({ error: frame.error })}\n\n`)
          await sleep(2000)
          continue
        }
        seq += 1
        lastScreen = { w: frame.screen.w, h: frame.screen.h, imgW: frame.data.w, imgH: frame.data.h }
        res.write(`data: ${JSON.stringify({
          jpeg: frame.data.jpeg,
          w: frame.data.w,
          h: frame.data.h,
          seq,
          ts: frame.data.ts,
          host: target.host,
          port: target.port,
        })}\n\n`)
      }
      return
    }

    if (route === '/input' && req.method === 'POST') {
      if (!target) { sendJson(res, 200, { ok: false, error: { code: 'NOT_STARTED', message: '还没有会话，先调用 screen_start' } }); return }
      const body = await readBody(req)
      if (!body) { sendJson(res, 400, { ok: false, error: { code: 'PROTOCOL_ERROR', message: '请求体必须是 JSON' } }); return }
      if (!lastScreen) {
        const probe = await daemonRequest(target, 'ping', {}, 2000)
        if (probe && probe.ok && probe.screen && probe.screen.w) {
          lastScreen = { w: probe.screen.w, h: probe.screen.h, imgW: probe.screen.w, imgH: probe.screen.h }
        }
      }
      if (!lastScreen) { sendJson(res, 200, { ok: false, error: { code: 'NOT_STARTED', message: '还没有画面，先等观察窗出帧' } }); return }
      const kind = body.kind === 'scroll' ? 'scroll' : 'click'
      const args = { kind }
      if (kind === 'click') {
        if (typeof body.nx !== 'number' || typeof body.ny !== 'number') {
          sendJson(res, 400, { ok: false, error: { code: 'PROTOCOL_ERROR', message: 'click 需要归一化坐标 nx/ny' } })
          return
        }
        args.xy = [
          Math.round(Math.min(1, Math.max(0, body.nx)) * (lastScreen.w - 1)),
          Math.round(Math.min(1, Math.max(0, body.ny)) * (lastScreen.h - 1)),
        ]
      } else {
        args.dy = Number(body.dy) || 3
      }
      const result = await daemonRequest(target, 'act', args, 60000)
      sendJson(res, 200, result)
      return
    }

    sendJson(res, 404, { ok: false, error: { code: 'NOT_FOUND', message: `未知路由 ${route}` } })
  }

  return webServer.register({ kind: 'prefix', path: ROUTE_PREFIX, handler })
}
