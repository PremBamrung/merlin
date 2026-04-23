import type { ReactNode } from 'react'
import Sidebar from './Sidebar'
import AddSourceModal from '@/components/sources/AddSourceModal'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="flex h-full w-full overflow-hidden bg-[#0d0d0d]">
      <Sidebar />
      <main className="flex-1 overflow-y-auto min-w-0">
        {children}
      </main>
      <AddSourceModal />
    </div>
  )
}
