import { Header } from '@/components/layout/Header'
import { ThemeToggle } from '@/components/layout/ThemeToggle'
import { AuthButton } from '@/components/layout/AuthButton'

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Header>
        <ThemeToggle />
        <AuthButton />
      </Header>
      {children}
    </>
  )
}
