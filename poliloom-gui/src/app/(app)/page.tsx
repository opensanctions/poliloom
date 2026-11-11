import { getLanguages, getCountries } from '@/lib/api-auth'
import { HomeContent } from './HomeContent'

interface HomeProps {
  searchParams: Promise<{ empty?: string }>
}

export default async function Home({ searchParams }: HomeProps) {
  const [languages, countries, { empty }] = await Promise.all([
    getLanguages(),
    getCountries(),
    searchParams,
  ])
  return (
    <HomeContent languages={languages} countries={countries} initialEmptyResult={empty === '1'} />
  )
}
