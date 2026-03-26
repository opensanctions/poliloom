import { Property, PropertyType } from '@/types'
import { EntityLink } from '@/components/ui/EntityLink'

export function GroupTitle({ property }: { property: Property }) {
  switch (property.type) {
    case PropertyType.P569:
      return <>Birth Date</>
    case PropertyType.P570:
      return <>Death Date</>
    case PropertyType.P39:
    case PropertyType.P19:
    case PropertyType.P27:
      return <EntityLink entityId={property.entity_id!} entityName={property.entity_name!} />
    default:
      return <>{property.entity_name || property.entity_id || 'Unknown Property'}</>
  }
}
