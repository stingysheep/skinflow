import type { HTMLAttributes, ReactNode } from 'react'

type DataTableFrameProps = HTMLAttributes<HTMLDivElement> & {
  children: ReactNode
}

export function DataTableFrame({ children, className, ...props }: DataTableFrameProps) {
  const classes = ['data-table-frame', className].filter(Boolean).join(' ')
  return <div {...props} className={classes}><div className="data-table-scroll">{children}</div></div>
}
