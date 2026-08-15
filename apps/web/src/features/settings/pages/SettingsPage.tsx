import { useEffect, useState } from 'react'
import { LogIn, LogOut, Settings2 } from 'lucide-react'
import { Button, FeedbackState } from '../../../shared/components'
import { refreshInventory } from '../../inventory'
import { clearSteamSession, getSteamSession, startSteamLogin, type SteamSession } from '../api/settingsApi'
import '../settings.css'

export function SettingsPage() {
  const [session, setSession] = useState<SteamSession | null>(null)
  const [loading, setLoading] = useState(true)
  const [polling, setPolling] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [syncMessage, setSyncMessage] = useState<string | null>(null)
  async function load() { setLoading(true); try { setSession(await getSteamSession()) } catch { setError('无法读取 Steam 会话状态') } finally { setLoading(false) } }
  useEffect(() => { void load() }, [])
  useEffect(() => {
    if (!polling) return
    let cancelled = false
    let timer = 0
    const poll = async () => {
      try {
        const next = await getSteamSession()
        if (cancelled) return
        setSession(next)
        if (next.status === 'active') {
          const refreshed = await refreshInventory()
          if (!cancelled) {
            setSyncMessage(`库存同步完成，共读取 ${refreshed.asset_count} 件资产。`)
            setPolling(false)
          }
          return
        }
        if (!next.login_running) {
          setPolling(false)
          setError(next.error ? `Steam 登录失败：${next.error}` : 'Steam 登录窗口已关闭，未检测到有效会话。')
          return
        }
        timer = window.setTimeout(() => void poll(), 1000)
      } catch (reason) {
        if (!cancelled) {
          setPolling(false)
          setError(reason instanceof Error ? reason.message : '无法读取 Steam 会话状态')
        }
      }
    }
    timer = window.setTimeout(() => void poll(), 1000)
    return () => { cancelled = true; window.clearTimeout(timer) }
  }, [polling])
  async function login() {
    setError(null); setSyncMessage(null)
    try { const next = await startSteamLogin(); setSession(next); setPolling(true) }
    catch (reason) { setError(reason instanceof Error ? reason.message : '当前运行模式无法打开登录窗口，请使用 Skinflow 桌面版') }
  }
  async function logout() { setPolling(false); setSyncMessage(null); await clearSteamSession(); await load() }
  return <div className="workspace-page"><header className="module-header"><div><span className="eyebrow">SKINFLOW / SETTINGS</span><h1>系统设置</h1><p>平台连接、本地存储和安全边界</p></div><Settings2 size={22} aria-hidden="true" /></header><section className="settings-list"><div><strong>行情平台</strong><span>csqaq 候选 · BUFF 匿名 · Steam 匿名行情</span></div><div><strong>数据库</strong><span>SQLite WAL · 单机本地存储 · 旧账本只迁移一次</span></div><div className="settings-session"><div><strong>Steam 会话</strong><span>{session?.status === 'active' ? `已连接账号 ${session.steamid64}` : polling ? '等待 Steam 登录完成，完成后将自动同步库存。' : '库存同步和挂单提交需要 Steam 会话；行情扫描不需要账号。'}</span>{syncMessage ? <small className="settings-success">{syncMessage}</small> : null}</div>{loading ? <span>读取中…</span> : session?.status === 'active' ? <Button variant="ghost" icon={<LogOut size={16} />} onClick={logout}>清除会话</Button> : <Button icon={<LogIn size={16} />} loading={polling || session?.login_running} onClick={login}>打开 Steam 登录</Button>}</div></section>{error ? <FeedbackState kind="error" title="连接操作失败" description={error} /> : null}</div>
}
