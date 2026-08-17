import { useEffect, useState } from 'react'
import { CircleCheck, CircleX, ExternalLink, LogIn, LogOut, RefreshCw, Settings2 } from 'lucide-react'
import { Button, FeedbackState } from '../../../shared/components'
import { refreshInventory } from '../../inventory'
import { clearSteamSession, getCsqaqConfiguration, getSteamSession, saveCsqaqConfiguration, startSteamLogin, validateCsqaqConfiguration, type CsqaqConfiguration, type SteamSession } from '../api/settingsApi'
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
  return <div className="workspace-page"><header className="module-header"><div><span className="eyebrow">SKINFLOW / SETTINGS</span><h1>系统设置</h1><p>平台连接、本地存储和安全边界</p></div><Settings2 size={22} aria-hidden="true" /></header><section className="settings-list"><div><strong>行情平台</strong><span>CSQAQ 候选 · BUFF 匿名 · Steam 匿名行情</span></div><CsqaqSettings /><div><strong>数据库</strong><span>SQLite WAL · 单机本地存储 · 旧账本只迁移一次</span></div><div className="settings-session"><div><strong>Steam 会话</strong><span>{session?.status === 'active' ? `已连接账号 ${session.steamid64}` : polling ? '等待 Steam 登录完成，完成后将自动同步库存。' : '库存同步和挂单提交需要 Steam 会话；行情扫描不需要账号。'}</span>{syncMessage ? <small className="settings-success">{syncMessage}</small> : null}</div>{loading ? <span>读取中…</span> : session?.status === 'active' ? <Button variant="ghost" icon={<LogOut size={16} />} onClick={logout}>清除会话</Button> : <Button icon={<LogIn size={16} />} loading={polling || session?.login_running} onClick={login}>打开 Steam 登录</Button>}</div></section>{error ? <FeedbackState kind="error" title="连接操作失败" description={error} /> : null}</div>
}

function CsqaqSettings() {
  const [configuration, setConfiguration] = useState<CsqaqConfiguration | null>(null)
  const [token, setToken] = useState('')
  const [tokenChanged, setTokenChanged] = useState(false)
  const [whitelistIp, setWhitelistIp] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const next = await getCsqaqConfiguration()
      setConfiguration(next)
      setWhitelistIp(next.whitelist_ip)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '无法读取 CSQAQ 连接状态')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      const next = await saveCsqaqConfiguration({
        ...(tokenChanged ? { token } : {}),
        whitelist_ip: whitelistIp,
      })
      setConfiguration(next)
      setToken('')
      setTokenChanged(false)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '无法保存 CSQAQ 配置')
    } finally {
      setSaving(false)
    }
  }

  const validate = async () => {
    setSaving(true)
    setError(null)
    try { setConfiguration(await validateCsqaqConfiguration()) }
    catch (reason) { setError(reason instanceof Error ? reason.message : '无法验证 CSQAQ 连接') }
    finally { setSaving(false) }
  }

  const status = configuration?.status ?? 'unavailable'
  const ready = status === 'ready'
  const label = ready ? '可用' : status === 'missing' ? '未配置' : status === 'access_denied' ? '被拒绝' : '未验证'
  const detail = ready ? '令牌与当前 CSQAQ 连接验证成功。' : status === 'missing' ? '填写并保存 API 令牌后才能开始扫描。' : status === 'access_denied' ? 'CSQAQ 拒绝了令牌或当前网络 IP。请在 CSQAQ 白名单中更新公网 IP。' : '暂时无法连接 CSQAQ，请检查网络或稍后重新验证。'
  const tone = ready ? 'ready' : status === 'access_denied' || status === 'missing' ? 'danger' : 'warning'

  return <div className="settings-csqaq"><div className="settings-csqaq-heading"><div><strong>CSQAQ API</strong><span>每次开始扫描前都会重新校验令牌与 CSQAQ 白名单 IP。</span></div><span className={`settings-connection settings-connection-${tone}`} role="status">{ready ? <CircleCheck size={16} aria-hidden="true" /> : <CircleX size={16} aria-hidden="true" />}{loading ? '检查中' : label}</span></div><form onSubmit={(event) => { event.preventDefault(); void save() }}><label>API 令牌<input name="csqaq-token" type="password" autoComplete="off" value={token} onChange={(event) => { setToken(event.target.value); setTokenChanged(true) }} placeholder={configuration?.token_configured ? '已安全保存；输入新令牌可替换' : '粘贴 CSQAQ API 令牌'} /></label><label>白名单 IP<input name="csqaq-whitelist-ip" value={whitelistIp} onChange={(event) => setWhitelistIp(event.target.value)} placeholder="填写已在 CSQAQ 中配置的当前公网 IP" /></label><p className="settings-hint">本程序仅保存你填写的 IP，不会替你修改 CSQAQ 的远程白名单。请注册并登录 CSQAQ，点击右上角头像查看 API 令牌，将本机当前公网 IP 加入白名单后再保存。</p><div className="settings-csqaq-actions"><Button type="submit" loading={saving}>保存并验证</Button><Button variant="ghost" icon={<RefreshCw size={16} />} loading={saving} onClick={() => void validate()}>重新检查</Button><a className="settings-csqaq-link" href="https://www.csqaq.com/" target="_blank" rel="noreferrer">打开 CSQAQ <ExternalLink size={14} aria-hidden="true" /></a></div></form><small className={`settings-status-detail settings-status-detail-${tone}`} role={ready ? 'status' : 'alert'}>{detail}</small>{error ? <small className="settings-status-detail settings-status-detail-danger" role="alert">{error}</small> : null}</div>
}
