import { Property, PropertyType } from '@/types';
import { groupPropertiesForDisplay } from '@/lib/propertyUtils';
import { EvaluationItem } from './EvaluationItem';
import { PropertyDisplay } from './PropertyDisplay';

interface PropertiesEvaluationProps {
  properties: Property[];
  evaluations: Map<string, boolean>;
  onAction: (propertyId: string, action: 'confirm' | 'discard') => void;
  onShowArchived: (property: Property) => void;
  onHover: (property: Property) => void;
  activeArchivedPageId: string | null;
}

export function PropertiesEvaluation({
  properties,
  evaluations,
  onAction,
  onShowArchived,
  onHover,
  activeArchivedPageId,
}: PropertiesEvaluationProps) {
  const groups = groupPropertiesForDisplay(properties);

  if (groups.length === 0) {
    return null;
  }

  const getGroupTitle = (group: typeof groups[0]) => {
    if (group.type === PropertyType.P39) {
      // For positions, group by entity (like the old PositionGroup)
      const entitiesByName = new Map<string, Property[]>();

      group.properties.forEach(property => {
        const key = property.entity_id || property.entity_name || 'Unknown';
        if (!entitiesByName.has(key)) {
          entitiesByName.set(key, []);
        }
        entitiesByName.get(key)!.push(property);
      });

      return Array.from(entitiesByName.entries()).map(([entityKey, entityProperties]) => {
        const firstProperty = entityProperties[0];
        const entityName = firstProperty.entity_name || firstProperty.entity_id || 'Unknown Position';

        const title = firstProperty.entity_id ?
          `<a href="https://www.wikidata.org/wiki/${firstProperty.entity_id}" target="_blank" rel="noopener noreferrer" class="hover:underline">${entityName} <span class="text-gray-500 font-normal">(${firstProperty.entity_id})</span></a>` :
          entityName;

        return {
          title,
          properties: entityProperties,
          key: entityKey
        };
      });
    }

    // For other types, show all properties in a single group
    return [{
      title: group.title,
      properties: group.properties,
      key: group.type
    }];
  };

  return (
    <div className="space-y-8">
      {groups.map((group) => {
        const subGroups = getGroupTitle(group);

        return (
          <div key={group.type} className="mb-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">{group.title}</h2>
            <div className="space-y-4">
              {subGroups.map((subGroup) => (
                <EvaluationItem
                  key={subGroup.key}
                  title={subGroup.title}
                  onHover={() => {
                    const firstWithArchive = subGroup.properties.find(
                      (p) => p.archived_page && !p.statement_id
                    );
                    if (firstWithArchive) {
                      onHover(firstWithArchive);
                    }
                  }}
                >
                  {subGroup.properties.map((property, index) => (
                    <div key={property.id}>
                      {index > 0 && <hr className="border-gray-300 my-2" />}
                      <PropertyDisplay
                        property={property}
                        evaluations={evaluations}
                        onAction={onAction}
                        onShowArchived={onShowArchived}
                        onHover={onHover}
                        activeArchivedPageId={activeArchivedPageId}
                      />
                    </div>
                  ))}
                </EvaluationItem>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}