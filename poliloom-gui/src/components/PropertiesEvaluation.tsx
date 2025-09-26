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

  // Group properties by section for ordering
  const sections = [
    {
      title: 'Properties',
      properties: properties.filter(p => [PropertyType.P569, PropertyType.P570].includes(p.type))
    },
    {
      title: 'Political Positions',
      properties: properties.filter(p => p.type === PropertyType.P39)
    },
    {
      title: 'Birthplaces',
      properties: properties.filter(p => p.type === PropertyType.P19)
    },
    {
      title: 'Citizenships',
      properties: properties.filter(p => p.type === PropertyType.P27)
    }
  ].filter(section => section.properties.length > 0);

  return (
    <div className="space-y-8">
      {sections.map((section) => (
        <div key={section.title} className="mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">{section.title}</h2>
          <div className="space-y-4">
            {section.properties.map((property) => (
              <EvaluationItem
                key={property.id}
                title={getPropertyTitle(property)}
                onHover={() => {
                  if (property.archived_page && !property.statement_id) {
                    onHover(property);
                  }
                }}
              >
                <PropertyDisplay
                  property={property}
                  evaluations={evaluations}
                  onAction={onAction}
                  onShowArchived={onShowArchived}
                  onHover={onHover}
                  activeArchivedPageId={activeArchivedPageId}
                />
              </EvaluationItem>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}