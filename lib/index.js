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

const execFileAsync = promisify(execFile)
const HERE = dirname(fileURLToPath(import.meta.url))
const CLI = join(HERE, '..', 'python', 'screen_cli.py')

export const name = 'dsh-screenpilot'
export const inject = ['tools']

export const Config = z.object({
  pythonBin: z.string().default('python3'),
  defaultTarget: z.string().default('vnc://192.168.1.68:5900'),
  timeoutMs: z.number().default(120000),
})

const ENVELOPE = {
  type: 'object',
  additionalProperties: true,
  properties: {
    ok: { type: 'boolean' },
    seq: { type: 'number' },
    session: { type: 'string' },
    capture: { type: 'string' },
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
      env: process.env,
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

function tool(name, description, parameters, buildArgs) {
  return defineTool({
    name,
    description,
    parameters,
    output: {
      schema: ENVELOPE,
      render: (_args, value) => [{ type: 'text', text: summarize(value) }],
    },
    timeoutMs: 180000,
    execute: async (args, exec) => buildArgs(args, exec),
  })
}

export function apply(ctx, config) {
  const cfg = { ...config }
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
      '取当前画面并返回元素清单（文本 + 坐标）。region 为 x0,y0,x1,y1，限定识别范围；小字区域必须提供。',
      {
        region: { type: 'string', description: 'x0,y0,x1,y1' },
      },
      async (args, exec) => {
        const argv = ['describe', ...base]
        if (args.region) argv.push('--region', args.region)
        return run(cfg, argv, exec.signal)
      },
    ),
  )

  ctx.tools.register(
    tool(
      'screen_act',
      '执行输入动作。kind=click/type/key/scroll；by=text/ref/xy 决定 value 的含义。返回动作前后两帧证据。',
      {
        kind: { type: 'string', required: true, description: 'click / type / key / scroll' },
        by: { type: 'string', description: 'text（默认）/ ref / xy' },
        value: { type: 'string', description: '文本、ref 或 "x,y"' },
        region: { type: 'string', description: 'x0,y0,x1,y1，限定文字定位范围' },
        dy: { type: 'number', description: 'scroll 方向与幅度，正数向下' },
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
      '等待画面稳定（连续两次快照一致）。动作前后各调用一次可以避免读到过渡帧。',
      {
        timeout: { type: 'number', description: '超时秒数，默认 8' },
      },
      async (args, exec) => {
        const argv = ['settle', ...base, '--timeout', String(args.timeout ?? 8)]
        return run(cfg, argv, exec.signal)
      },
    ),
  )
}
