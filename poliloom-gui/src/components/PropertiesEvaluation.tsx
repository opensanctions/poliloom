import { Property, PropertyType } from '@/types';
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
  if (properties.length === 0) {
    return null;
  }

  const getPropertyTitle = (property: Property): string => {
    switch (property.type) {
      case PropertyType.P569:
        return 'Birth Date';
      case PropertyType.P570:
        return 'Death Date';
      case PropertyType.P39:
        // For positions, show the position name with Wikidata link
        const positionName = property.entity_name || property.entity_id || 'Unknown Position';
        return property.entity_id ?
          `<a href="https://www.wikidata.org/wiki/${property.entity_id}" target="_blank" rel="noopener noreferrer" class="hover:underline">${positionName} <span class="text-gray-500 font-normal">(${property.entity_id})</span></a>` :
          positionName;
      case PropertyType.P19:
        // For birthplaces, show the place name with Wikidata link
        const birthplaceName = property.entity_name || property.entity_id || 'Unknown Place';
        return property.entity_id ?
          `<a href="https://www.wikidata.org/wiki/${property.entity_id}" target="_blank" rel="noopener noreferrer" class="hover:underline">${birthplaceName} <span class="text-gray-500 font-normal">(${property.entity_id})</span></a>` :
          birthplaceName;
      case PropertyType.P27:
        // For citizenship, show the country name with Wikidata link
        const citizenshipName = property.entity_name || property.entity_id || 'Unknown Country';
        return property.entity_id ?
          `<a href="https://www.wikidata.org/wiki/${property.entity_id}" target="_blank" rel="noopener noreferrer" class="hover:underline">${citizenshipName} <span class="text-gray-500 font-normal">(${property.entity_id})</span></a>` :
          citizenshipName;
      default:
        return property.entity_name || property.entity_id || 'Unknown Property';
    }
  };

  const getGroupedProperties = () => {
    const sections = [];

    // Group properties by type for section organization
    const propertiesByType = new Map<PropertyType, Property[]>();
    properties.forEach(property => {
      if (!propertiesByType.has(property.type)) {
        propertiesByType.set(property.type, []);
      }
      propertiesByType.get(property.type)!.push(property);
    });

    // Process each property type
    propertiesByType.forEach((typeProperties, propertyType) => {
      const sectionTitle = getSectionTitle(propertyType);
      const hasEntity = typeProperties.some(p => p.entity_id || p.entity_name);

      if (hasEntity) {
        // Entity-based properties: group by entity
        const entityGroups = new Map<string, Property[]>();

        typeProperties.forEach(property => {
          const key = property.entity_id || property.entity_name || 'Unknown';
          if (!entityGroups.has(key)) {
            entityGroups.set(key, []);
          }
          entityGroups.get(key)!.push(property);
        });

        sections.push({
          title: sectionTitle,
          items: Array.from(entityGroups.entries()).map(([entityKey, entityProperties]) => {
            const firstProperty = entityProperties[0];
            return {
              title: getPropertyTitle(firstProperty),
              properties: entityProperties,
              key: entityKey
            };
          })
        });
      } else {
        // Value-based properties: group by property type
        sections.push({
          title: sectionTitle,
          items: [{
            title: getPropertyTitle(typeProperties[0]),
            properties: typeProperties,
            key: propertyType
          }]
        });
      }
    });

    return sections;
  };

  const getSectionTitle = (propertyType: PropertyType): string => {
    switch (propertyType) {
      case PropertyType.P569:
      case PropertyType.P570:
        return 'Properties';
      case PropertyType.P39:
        return 'Political Positions';
      case PropertyType.P19:
        return 'Birthplaces';
      case PropertyType.P27:
        return 'Citizenships';
      default:
        return 'Other Properties';
    }
  };

  const sections = getGroupedProperties();

  return (
    <div className="space-y-8">
      {sections.map((section) => (
        <div key={section.title} className="mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">{section.title}</h2>
          <div className="space-y-4">
            {section.items.map((item) => (
              <EvaluationItem
                key={item.key}
                title={item.title}
                onHover={() => {
                  const firstWithArchive = item.properties.find(
                    (p) => p.archived_page && !p.statement_id
                  );
                  if (firstWithArchive) {
                    onHover(firstWithArchive);
                  }
                }}
              >
                {item.properties.map((property, index) => (
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
      ))}
    </div>
  );
}