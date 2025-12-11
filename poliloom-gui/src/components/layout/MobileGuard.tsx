'use client'

import { ReactNode } from 'react'
import { CenteredCard } from '@/components/ui/CenteredCard'

interface MobileGuardProps {
  children: ReactNode
}

export function MobileGuard({ children }: MobileGuardProps) {
  return (
    <>
      {/* Mobile/tablet screen message - shown on small screens */}
      <div className="lg:hidden h-screen">
        <CenteredCard emoji="🖥️" title="Larger Screen Required">
          PoliLoom displays data and sources side by side for verification.
        </CenteredCard>
      </div>

      {/* Main content - hidden on small screens */}
      <div className="hidden lg:contents">{children}</div>
    </>
  )
}
