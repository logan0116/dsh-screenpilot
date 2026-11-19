/**
 * dsh-screenpilot —— 把 rsp/2 屏幕能力包成 screen_* 工具。
 *
 * VNC/RFB、OCR 与协议实现放在 python/ 下的 sidecar，本文件只做工具适配：
 * 参数映射、进程调用、信封校验与错误归一。web 后端（ego-browser）尚未接入。
 */
import { defineTool } from '@deepseek-ai/dsh-tools'
import z from '@deepseek-ai/schemastery'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { existsSync } from 'node:fs'
import { registerRoutes } from './server.js'

const execFileAsync = promisify(execFile)
const HERE = dirname(fileURLToPath(import.meta.url))
const CLI = join(HERE, '..', 'python', 'screen_cli.py')

export const name = 'dsh-screenpilot'
export const inject = ['tools']

// 解释器解析：显式配置 > SCREENPILOT_PYTHON > 包旁 .venv > python3。
// 直连源码目录时依赖通常装在 .venv 里，默认 python3 往往缺 pillow/numpy/rapidocr。
function defaultPython() {
  if (process.env.SCREENPILOT_PYTHON) return process.env.SCREENPILOT_PYTHON
  const venv = join(HERE, '..', '.venv', 'bin', 'python')
  if (existsSync(venv)) return venv
  return 'python3'
}

export const Config = z.object({
  pythonBin: z.string().default(defaultPython()),
  defaultTarget: z.string().default('vnc://192.168.1.68:5900'),
  timeoutMs: z.number().default(120000),
  // VNC 认证密码：非空时通过环境变量传给 sidecar（不进 argv，ps 看不到）
  vncPassword: z.string().default(''),
})

const ENVELOPE = {
  type: 'object',
  additionalProperties: true,
  properties: {
    ok: { type: 'boolean' },
    seq: { type: 'number' },
    session: { type: 'string' },
    // 失败信封与 stop 的 capture 为 null：DSH 的 schema 不支持 type 数组，用 oneOf
    capture: { oneOf: [{ type: 'string' }, { type: 'null' }] },
    screen: { type: 'object', additionalProperties: true },
    data: { type: 'object', additionalProperties: true },
    capabilities: { type: 'array', items: { type: 'string' } },
  },
}

function summarize(value) {
  const parts = []
  if (value.ok === false) {
    const err = value.error || {}
    parts.push(`FAIL ${err.code || 'ERROR'}: ${err.message || ''}`)
    if (err.hint) parts.push(`hint: ${err.hint}`)
    return parts.join(' | ')
  }
  if (value.capture) parts.push(`capture=${value.capture}`)
  if (value.data && value.data.texts) parts.push(`texts=${value.data.texts.length}`)
  if (value.data && value.data.found !== undefined) parts.push(`found=${value.data.found}`)
  if (value.data && value.data.target) parts.push(`target=${JSON.stringify(value.data.target)}`)
  if (value.data && value.data.diff !== undefined) parts.push(`diff=${value.data.diff}`)
  return parts.join(' | ') || 'ok'
}

async function run(cfg, argv, signal) {
  try {
    const { stdout } = await execFileAsync(cfg.pythonBin, [CLI, ...argv], {
      cwd: dirname(CLI),
      timeout: cfg.timeoutMs,
      maxBuffer: 32 * 1024 * 1024,
      env: cfg.vncPassword
        ? { ...process.env, SCREENPILOT_VNC_PASSWORD: cfg.vncPassword }
        : process.env,
      ...(signal ? { signal } : {}),
    })
    return JSON.parse(stdout)
  } catch (err) {
    const raw = String(err && err.stdout ? err.stdout : '').trim()
    const start = raw.indexOf('{')
    if (start >= 0) {
      try {
        return JSON.parse(raw.slice(start))
      } catch {
        // 落到下面的归一错误
      }
    }
    return {
      ok: false,
      seq: 0,
      error: { code: 'PROTOCOL_ERROR', message: String((err && err.message) || err) },
    }
  }
}

// describe 的清单渲染：模型要按文字定位，就必须看得见 text/x/y。
// 170+ 条会撑爆上下文，默认按 reading order 取前 40 条，可用 limit 调，0 = 只回摘要。
const DESCRIBE_LIMIT = 40
const DESCRIBE_MAX_CHARS = 4000

function describeText(args, value) {
  const head = summarize(value)
  if (!value.ok || !value.data || !Array.isArray(value.data.texts)) return head
  const limit = Math.max(0, Math.min(200, Number(args && args.limit !== undefined ? args.limit : DESCRIBE_LIMIT)))
  if (limit === 0) return head
  const items = [...value.data.texts]
    .sort((a, b) => (a.y - b.y) || (a.x - b.x))
    .slice(0, limit)
  const lines = [head]
  let chars = head.length
  for (let i = 0; i < items.length; i += 1) {
    const t = items[i]
    const line = `[${i}] ${t.text} (${Math.round(t.x)},${Math.round(t.y)}) ${Number(t.score || 0).toFixed(2)}`
    if (chars + line.length + 1 > DESCRIBE_MAX_CHARS) break
    lines.push(line)
    chars += line.length + 1
  }
  return lines.join('\n')
}

function tool(name, description, parameters, buildArgs, render) {
  return defineTool({
    name,
    description,
    parameters,
    output: {
      schema: ENVELOPE,
      render: render || ((_args, value) => [{ type: 'text', text: summarize(value) }]),
    },
    timeoutMs: 180000,
    execute: async (args, exec) => buildArgs(args, exec),
  })
}

export function apply(ctx, config) {
  const cfg = { ...config }

  // 观察窗：同源路由挂在 DSH 的 webServer 上，卸载时注销。
  // 先用 cordis 的正规注入拿服务，拿不到再退回 ctx.get（两条路都打日志，便于排查）。
  const mountRoutes = (scope, how) => {
    const webServer = typeof scope.get === 'function' ? scope.get('webServer') : undefined
    console.log('[screenpilot] mountRoutes via', how, '| webServer=', Boolean(webServer), '| register=', typeof (webServer && webServer.register))
    if (!webServer || typeof webServer.register !== 'function') return undefined
    const dispose = registerRoutes(webServer, { scale: 0.5, quality: 60 })
    console.log('[screenpilot] routes registered:', dispose !== undefined)
    return () => { if (typeof dispose === 'function') dispose() }
  }

  if (typeof ctx.inject === 'function') {
    ctx.inject(['webServer'], (scopedCtx) => mountRoutes(scopedCtx, 'inject'))
  }
  if (typeof ctx.effect === 'function') {
    ctx.effect(() => mountRoutes(ctx, 'ctx.get'), 'screenpilot: watch panel routes')
  }

  // defaultTarget 逐次透传，避免 sidecar 内置缺省与插件配置各有一套真相
  const base = ['--default', cfg.defaultTarget]

  ctx.tools.register(
    tool(
      'screen_start',
      '建立屏幕会话。target 形如 vnc://host:port 或 web://url；当前只实现 vnc。返回 capabilities 与 screen.source（target/session/default/builtin），调用方据此确认连的哪台台架。',
      {
        target: { type: 'string', description: 'vnc://192.168.1.68:5900 或 web://192.168.1.155:8088，缺省用配置的 defaultTarget' },
      },
      async (args, exec) => {
        const argv = ['start', ...base, '--timeout', '8']
        if (args.target) argv.push('--target', args.target)
        const res = await run(cfg, argv, exec.signal)
        if (!res.ok) return res
        return {
          ...res,
          session: res.session || 'default',
          capabilities: res.capabilities || ['text', 'xy'],
        }
      },
    ),
  )

  ctx.tools.register(
    tool(
      'screen_describe',
      '取当前画面并返回元素清单（文本 + 坐标）。region 为 x0,y0,x1,y1，限定识别范围；小字区域必须提供。渲染默认按阅读序给出前 40 条（limit 可调，0=只回摘要）。',
      {
        region: { type: 'string', description: 'x0,y0,x1,y1' },
        limit: { type: 'number', description: '渲染清单条数，默认 40，最大 200，0 表示只回摘要' },
      },
      async (args, exec) => {
        const argv = ['describe', ...base]
        if (args.region) argv.push('--region', args.region)
        return run(cfg, argv, exec.signal)
      },
      (_args, value) => [{ type: 'text', text: describeText(_args, value) }],
    ),
  )

  ctx.tools.register(
    tool(
      'screen_act',
      '执行输入动作。kind=click/type/key/scroll；by=text/ref/xy 决定 value 的含义。key 支持组合键（ctrl+space、alt+f4、ctrl+shift+s），也支持单按修饰键（shift）切换输入法。返回动作前后两帧证据。',
      {
        kind: { type: 'string', required: true, description: 'click / type / key / scroll' },
        by: { type: 'string', description: 'text（默认）/ ref / xy' },
        value: { type: 'string', description: '文本、ref、"x,y"，或组合键（如 ctrl+space）' },
        region: { type: 'string', description: 'x0,y0,x1,y1，限定文字定位范围' },
        dy: { type: 'number', description: 'scroll 方向与幅度，正数向下' },
        wait: { type: 'number', description: '动作后等待秒数再取帧，默认 0.6' },
        retry_on_no_change: { type: 'boolean', description: '画面几乎无变化时补抓一帧（多花约1.2秒），默认关闭' },
      },
      async (args, exec) => {
        const by = args.by || 'text'
        if (by === 'ref') {
          return {
            ok: false,
            seq: 0,
            error: { code: 'UNSUPPORTED', message: 'vnc 后端没有语义 ref', hint: '改用 by=text 或 by=xy' },
          }
        }
        const argv = ['act', ...base, '--kind', args.kind]
        if (args.kind === 'click') {
          if (by === 'xy') argv.push('--xy', args.value)
          else argv.push('--text', args.value)
        } else if (args.kind === 'type') {
          argv.push('--text', args.value)
        } else if (args.kind === 'key') {
          argv.push('--text', args.value)
        } else if (args.kind === 'scroll') {
          argv.push('--dy', String(args.dy ?? 3))
          if (args.value) argv.push('--xy', args.value)
        }
        if (args.region) argv.push('--region', args.region)
        if (args.wait !== undefined) argv.push('--wait', String(args.wait))
        if (args.retry_on_no_change) argv.push('--retry-on-no-change')
        return run(cfg, argv, exec.signal)
      },
    ),
  )

  ctx.tools.register(
    tool(
      'screen_verify',
      '断言当前画面。kind=text/absent/url/changed；ok 表示断言执行完成，data.satisfied 才是结论。',
      {
        kind: { type: 'string', description: 'text / absent / url / changed' },
        value: { type: 'string', description: '用于断言的目标文本或 URL 片段' },
        region: { type: 'string', description: 'x0,y0,x1,y1' },
      },
      async (args, exec) => {
        const argv = ['verify', ...base, '--kind', args.kind || 'text']
        if (args.value) argv.push('--text', args.value)
        if (args.region) argv.push('--region', args.region)
        return run(cfg, argv, exec.signal)
      },
    ),
  )

  ctx.tools.register(
    tool(
      'screen_settle',
      '等待画面稳定。判据是两帧差异像素占比 ≤ tolerance（默认 0.002），可用 region 限定关注区域以躲开区域外的心跳刷新。超时也回最后一帧与 changedRatio。',
      {
        timeout: { type: 'number', description: '超时秒数，默认 8' },
        region: { type: 'string', description: 'x0,y0,x1,y1，只在该区域判稳定' },
        tolerance: { type: 'number', description: '允许的变化像素占比，默认 0.002（0.2%）' },
      },
      async (args, exec) => {
        const argv = ['settle', ...base, '--timeout', String(args.timeout ?? 8)]
        if (args.region) argv.push('--region', args.region)
        if (args.tolerance !== undefined) argv.push('--tolerance', String(args.tolerance))
        return run(cfg, argv, exec.signal)
      },
    ),
  )

  ctx.tools.register(
    tool(
      'screen_stop',
      '释放屏幕会话：常驻进程退出、VNC 连接断开、socket 与会话文件清理。重复调用返回 NOT_STARTED，且不会为关停而拉起进程。',
      {},
      async (_args, exec) => run(cfg, ['stop', ...base], exec.signal),
    ),
  )
}
