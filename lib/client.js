/**
 * 侧边栏观察窗的 client 侧：在右侧栏注册一个 tab，用 SSE 播放远端画面，
 * 点击画面即可手动接管（等价 screen_act click xy）。
 *
 * 帧来自 host 侧 /api/screenpilot/stream，与页面同源，不新开端口。
 */
window.__ModuleLoader__.load({
  id: 'dsh-screenpilot',
  factory: (require) => {
    var module = { exports: {} }
    var exports = module.exports
    var React = require('react')
    var h = React.createElement

    var ROUTE = '/api/screenpilot'
    var TAB_ID = 'dsh-screenpilot:watch'
    var TAB_KIND = 'screenpilot:watch'

    var ICON = function() {
      return h('svg', { width: 16, height: 16, viewBox: '0 0 16 16', 'aria-hidden': 'true' },
        h('rect', { x: 1.5, y: 2.5, width: 13, height: 9, rx: 1.5, fill: 'none', stroke: 'currentColor', strokeWidth: 1.3 }),
        h('path', { d: 'M5.5 13.5h5', stroke: 'currentColor', strokeWidth: 1.3, strokeLinecap: 'round' }),
        h('circle', { cx: 8, cy: 7, r: 1.6, fill: 'currentColor' }))
    }

    function useStream(paused) {
      var frameState = React.useState(null)
      var frame = frameState[0]
      var setFrame = frameState[1]
      var statusState = React.useState('连接中…')
      var status = statusState[0]
      var setStatus = statusState[1]

      React.useEffect(function() {
        if (paused) return undefined
        var es = new EventSource(ROUTE + '/stream')
        es.onmessage = function(ev) {
          try {
            var data = JSON.parse(ev.data)
            if (data.error) {
              setStatus(data.error.message || data.error.code || '不可用')
              return
            }
            setFrame(data)
            var time = new Date(data.ts).toLocaleTimeString()
            setStatus('帧 ' + data.seq + ' · ' + time)
          } catch (err) {
            setStatus('帧解析失败')
          }
        }
        es.onerror = function() {
          setStatus('流已断开，自动重连中…')
        }
        return function() { es.close() }
      }, [paused])

      return { frame: frame, status: status }
    }

    function WatchPanel() {
      var pausedState = React.useState(false)
      var paused = pausedState[0]
      var setPaused = pausedState[1]
      var noteState = React.useState('')
      var note = noteState[0]
      var setNote = noteState[1]
      var stream = useStream(paused)
      var frame = stream.frame

      var onClick = function(ev) {
        if (!frame) return
        var rect = ev.currentTarget.getBoundingClientRect()
        var nx = (ev.clientX - rect.left) / rect.width
        var ny = (ev.clientY - rect.top) / rect.height
        setNote('发送点击…')
        fetch(ROUTE + '/input', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ kind: 'click', nx: nx, ny: ny })
        }).then(function(res) {
          return res.json()
        }).then(function(data) {
          if (data.ok) {
            var t = data.data && data.data.target
            setNote(t ? '已点击 ' + t.x + ',' + t.y : '已点击')
          } else {
            var err = data.error || {}
            setNote('失败：' + (err.message || err.code || '未知错误'))
          }
        }).catch(function(err) {
          setNote('请求失败：' + err.message)
        })
      }

      var header = h('div', {
        style: {
          display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px',
          borderBottom: '1px solid var(--dsw-alias-border-subtle, rgba(128,128,128,.25))',
          fontSize: 12, color: 'inherit', opacity: .9
        }
      },
        h('span', { style: { fontWeight: 600 } }, '远程屏幕'),
        h('span', { style: { opacity: .7 } }, stream.status),
        h('button', {
          type: 'button',
          onClick: function() { setPaused(!paused) },
          style: {
            marginLeft: 'auto', fontSize: 12, padding: '2px 8px', borderRadius: 6,
            border: '1px solid var(--dsw-alias-border-subtle, rgba(128,128,128,.35))',
            background: 'transparent', color: 'inherit', cursor: 'pointer'
          }
        }, paused ? '继续' : '暂停'))

      var body
      if (!frame) {
        body = h('div', {
          style: { padding: 16, fontSize: 12, opacity: .75, lineHeight: 1.7 }
        },
          h('div', null, '还没有画面。'),
          h('div', null, '先让 agent 调用 screen_start 建立会话，连上后这里会自动出现画面。'),
          h('div', { style: { marginTop: 8, opacity: .8 } }, stream.status))
      } else {
        body = h('div', { style: { flex: 1, minHeight: 0, overflow: 'auto', padding: 8 } },
          h('img', {
            src: 'data:image/jpeg;base64,' + frame.jpeg,
            alt: '远端屏幕',
            onClick: onClick,
            style: {
              display: 'block', width: '100%', height: 'auto', cursor: 'crosshair',
              borderRadius: 6, border: '1px solid var(--dsw-alias-border-subtle, rgba(128,128,128,.25))'
            }
          }))
      }

      var footer = h('div', {
        style: {
          padding: '4px 10px 8px', fontSize: 11, opacity: .7, display: 'flex',
          gap: 8, alignItems: 'center'
        }
      },
        h('span', null, frame ? (frame.host + ':' + frame.port) : '未连接'),
        h('span', { style: { marginLeft: 'auto' } }, note))

      return h('div', {
        style: { display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0, color: 'inherit' }
      }, header, body, footer)
    }

    function apply(ctx) {
      if (!ctx || typeof ctx.inject !== 'function') return
      ctx.inject(['sidebarRight', 'sidebarRightTabs'], function(sidebarCtx) {
        var sidebar = typeof sidebarCtx.get === 'function' ? sidebarCtx.get('sidebarRight') : undefined
        var tabs = typeof sidebarCtx.get === 'function' ? sidebarCtx.get('sidebarRightTabs') : undefined
        if (!tabs || typeof tabs.register !== 'function') return undefined

        var disposeType = tabs.register({
          id: TAB_ID,
          kind: TAB_KIND,
          keepMounted: true,
          priority: 'extension',
          title: function() { return '远程屏幕' },
          guide: [{
            id: 'screenpilot-watch',
            order: 80,
            title: function() { return '远程屏幕' },
            icon: ICON
          }]
        })
        var disposeBody = sidebarCtx.slots.register({
          name: 'sidebar.right.pane.tab',
          key: TAB_ID,
          inject: function() { return { ctx: sidebarCtx } }
        }, WatchPanel)

        return function() {
          try { disposeBody() } catch (e) { /* noop */ }
          try { disposeType() } catch (e) { /* noop */ }
        }
      })
    }

    exports.apply = apply
    exports.inject = ['slots']
    exports.name = 'screenpilot'
    return module.exports
  }
})
