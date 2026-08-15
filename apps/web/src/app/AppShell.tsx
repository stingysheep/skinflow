import {
  Boxes,
  ChartNoAxesCombined,
  History,
  ClipboardList,
  PackageSearch,
  Settings,
  WalletCards,
} from 'lucide-react'

import { SystemStatus } from '../features/system-status/SystemStatus'
import { Link, Outlet } from '@tanstack/react-router'

const navigation = [
  { label: '扫描选品', icon: PackageSearch, to: '/' },
  { label: '库存', icon: Boxes, to: '/inventory' },
  { label: '持仓', icon: WalletCards, to: '/holdings' },
  { label: '成交历史', icon: History, to: '/history' },
  { label: '挂单记录', icon: ClipboardList, to: '/listings' },
  { label: '设置', icon: Settings, to: '/settings' },
]

export function AppShell() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-main">
          <div className="brand-block">
            <div className="brand-mark" aria-hidden="true">
              <ChartNoAxesCombined size={20} />
            </div>
            <div>
              <strong>Skinflow</strong>
              <span>CS2 交易工作台</span>
            </div>
          </div>

          <nav aria-label="主导航">
            {navigation.map((item) => {
              const Icon = item.icon
              return (
                <Link className="nav-item" activeProps={{ className: 'nav-item is-active' }} key={item.label} to={item.to} aria-label={item.label}><Icon aria-hidden="true" size={18} /><span>{item.label}</span></Link>
              )
            })}
          </nav>
        </div>

        <div className="sidebar-footer">
          <SystemStatus />
        </div>
      </aside>

      <main className="workspace">
        <Outlet />
      </main>
    </div>
  )
}
