import { getLanguages, getCountries } from '@/lib/api-auth'
import { HomeContent } from './HomeContent'

export default async function Home() {
  const [languages, countries] = await Promise.all([getLanguages(), getCountries()])
  return <HomeContent languages={languages} countries={countries} />
}
