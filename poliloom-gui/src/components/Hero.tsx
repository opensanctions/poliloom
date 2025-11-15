import { ReactNode } from 'react'

interface HeroProps {
  title: string
  description: string | ReactNode
  children?: ReactNode
}

export function Hero({ title, description, children }: HeroProps) {
  return (
    <div className="bg-gradient-to-br from-indigo-600 via-indigo-700 to-indigo-800 text-white">
      <div className="max-w-6xl mx-auto px-8 py-12">
        <div className="max-w-3xl">
          <h1 className="text-4xl font-bold mb-4">{title}</h1>
          <p className="text-lg text-indigo-100 leading-relaxed">{description}</p>
          {children}
        </div>
      </div>
    </div>
  )
}
