"use client";

import { useState } from 'react';
import { Politician, Property, Position, Birthplace, EvaluationRequest, EvaluationItem } from '@/types';
import { submitEvaluations } from '@/lib/api';

interface PoliticianEvaluationProps {
  politician: Politician;
  accessToken: string;
  onNext: () => void;
}

export function PoliticianEvaluation({ politician, accessToken, onNext }: PoliticianEvaluationProps) {
  const [confirmedProperties, setConfirmedProperties] = useState<Set<string>>(new Set());
  const [discardedProperties, setDiscardedProperties] = useState<Set<string>>(new Set());
  const [confirmedPositions, setConfirmedPositions] = useState<Set<string>>(new Set());
  const [discardedPositions, setDiscardedPositions] = useState<Set<string>>(new Set());
  const [confirmedBirthplaces, setConfirmedBirthplaces] = useState<Set<string>>(new Set());
  const [discardedBirthplaces, setDiscardedBirthplaces] = useState<Set<string>>(new Set());
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handlePropertyAction = (propertyId: string, action: 'confirm' | 'discard') => {
    if (action === 'confirm') {
      setConfirmedProperties(prev => new Set(prev).add(propertyId));
      setDiscardedProperties(prev => {
        const newSet = new Set(prev);
        newSet.delete(propertyId);
        return newSet;
      });
    } else {
      setDiscardedProperties(prev => new Set(prev).add(propertyId));
      setConfirmedProperties(prev => {
        const newSet = new Set(prev);
        newSet.delete(propertyId);
        return newSet;
      });
    }
  };

  const handlePositionAction = (positionId: string, action: 'confirm' | 'discard') => {
    if (action === 'confirm') {
      setConfirmedPositions(prev => new Set(prev).add(positionId));
      setDiscardedPositions(prev => {
        const newSet = new Set(prev);
        newSet.delete(positionId);
        return newSet;
      });
    } else {
      setDiscardedPositions(prev => new Set(prev).add(positionId));
      setConfirmedPositions(prev => {
        const newSet = new Set(prev);
        newSet.delete(positionId);
        return newSet;
      });
    }
  };

  const handleBirthplaceAction = (birthplaceId: string, action: 'confirm' | 'discard') => {
    if (action === 'confirm') {
      setConfirmedBirthplaces(prev => new Set(prev).add(birthplaceId));
      setDiscardedBirthplaces(prev => {
        const newSet = new Set(prev);
        newSet.delete(birthplaceId);
        return newSet;
      });
    } else {
      setDiscardedBirthplaces(prev => new Set(prev).add(birthplaceId));
      setConfirmedBirthplaces(prev => {
        const newSet = new Set(prev);
        newSet.delete(birthplaceId);
        return newSet;
      });
    }
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      const evaluations: EvaluationItem[] = [
        ...Array.from(confirmedProperties).map(id => ({
          entity_type: 'property',
          entity_id: id,
          result: 'confirmed' as const
        })),
        ...Array.from(discardedProperties).map(id => ({
          entity_type: 'property',
          entity_id: id,
          result: 'discarded' as const
        })),
        ...Array.from(confirmedPositions).map(id => ({
          entity_type: 'position',
          entity_id: id,
          result: 'confirmed' as const
        })),
        ...Array.from(discardedPositions).map(id => ({
          entity_type: 'position',
          entity_id: id,
          result: 'discarded' as const
        })),
        ...Array.from(confirmedBirthplaces).map(id => ({
          entity_type: 'birthplace',
          entity_id: id,
          result: 'confirmed' as const
        })),
        ...Array.from(discardedBirthplaces).map(id => ({
          entity_type: 'birthplace',
          entity_id: id,
          result: 'discarded' as const
        }))
      ];

      const evaluationData: EvaluationRequest = {
        evaluations
      };

      const response = await submitEvaluations(evaluationData, accessToken);
      if (response.success) {
        onNext();
      } else {
        console.error('Evaluation errors:', response.errors);
        alert(`Error submitting evaluations: ${response.message}`);
      }
    } catch (error) {
      console.error('Error submitting evaluations:', error);
      alert('Error submitting evaluations. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto bg-white shadow-lg rounded-lg p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">{politician.name}</h1>
        {politician.wikidata_id && (
          <p className="text-gray-600">Wikidata ID: {politician.wikidata_id}</p>
        )}
      </div>

      {politician.unconfirmed_properties.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Properties</h2>
          <div className="space-y-4">
            {politician.unconfirmed_properties.map((property) => (
              <PropertyItem
                key={property.id}
                property={property}
                isConfirmed={confirmedProperties.has(property.id)}
                isDiscarded={discardedProperties.has(property.id)}
                onAction={(action) => handlePropertyAction(property.id, action)}
              />
            ))}
          </div>
        </div>
      )}

      {politician.unconfirmed_positions.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Political Positions</h2>
          <div className="space-y-4">
            {politician.unconfirmed_positions.map((position) => (
              <PositionItem
                key={position.id}
                position={position}
                isConfirmed={confirmedPositions.has(position.id)}
                isDiscarded={discardedPositions.has(position.id)}
                onAction={(action) => handlePositionAction(position.id, action)}
              />
            ))}
          </div>
        </div>
      )}

      {politician.unconfirmed_birthplaces.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Birthplaces</h2>
          <div className="space-y-4">
            {politician.unconfirmed_birthplaces.map((birthplace) => (
              <BirthplaceItem
                key={birthplace.id}
                birthplace={birthplace}
                isConfirmed={confirmedBirthplaces.has(birthplace.id)}
                isDiscarded={discardedBirthplaces.has(birthplace.id)}
                onAction={(action) => handleBirthplaceAction(birthplace.id, action)}
              />
            ))}
          </div>
        </div>
      )}

      <div className="flex justify-end">
        <button
          onClick={handleSubmit}
          disabled={isSubmitting}
          className="px-6 py-3 bg-indigo-600 text-white font-medium rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSubmitting ? 'Submitting...' : 'Submit Evaluations & Next'}
        </button>
      </div>
    </div>
  );
}

interface PropertyItemProps {
  property: Property;
  isConfirmed: boolean;
  isDiscarded: boolean;
  onAction: (action: 'confirm' | 'discard') => void;
}

function PropertyItem({ property, isConfirmed, isDiscarded, onAction }: PropertyItemProps) {
  return (
    <div className="border border-gray-200 rounded-lg p-4">
      <div className="flex justify-between items-start">
        <div className="flex-1">
          <h3 className="font-medium text-gray-900">{property.type}</h3>
          <p className="text-gray-700 mt-1">{property.value}</p>
          <div className="mt-2">
            {property.source_urls.map((url, index) => (
              <a
                key={index}
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:text-blue-800 text-sm inline-block mr-3"
              >
                Source {index + 1} →
              </a>
            ))}
          </div>
        </div>
        <div className="flex space-x-2 ml-4">
          <button
            onClick={() => onAction('confirm')}
            className={`px-3 py-1 rounded text-sm font-medium ${
              isConfirmed
                ? 'bg-green-100 text-green-800 border border-green-300'
                : 'bg-gray-100 text-gray-700 hover:bg-green-50 hover:text-green-700'
            }`}
          >
            ✓ Confirm
          </button>
          <button
            onClick={() => onAction('discard')}
            className={`px-3 py-1 rounded text-sm font-medium ${
              isDiscarded
                ? 'bg-red-100 text-red-800 border border-red-300'
                : 'bg-gray-100 text-gray-700 hover:bg-red-50 hover:text-red-700'
            }`}
          >
            ✗ Discard
          </button>
        </div>
      </div>
    </div>
  );
}

interface PositionItemProps {
  position: Position;
  isConfirmed: boolean;
  isDiscarded: boolean;
  onAction: (action: 'confirm' | 'discard') => void;
}

function PositionItem({ position, isConfirmed, isDiscarded, onAction }: PositionItemProps) {
  return (
    <div className="border border-gray-200 rounded-lg p-4">
      <div className="flex justify-between items-start">
        <div className="flex-1">
          <h3 className="font-medium text-gray-900">{position.position_name}</h3>
          <p className="text-gray-700 mt-1">
            {position.start_date || 'Unknown'} - {position.end_date || 'Present'}
          </p>
          <div className="mt-2">
            {position.source_urls.map((url, index) => (
              <a
                key={index}
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:text-blue-800 text-sm inline-block mr-3"
              >
                Source {index + 1} →
              </a>
            ))}
          </div>
        </div>
        <div className="flex space-x-2 ml-4">
          <button
            onClick={() => onAction('confirm')}
            className={`px-3 py-1 rounded text-sm font-medium ${
              isConfirmed
                ? 'bg-green-100 text-green-800 border border-green-300'
                : 'bg-gray-100 text-gray-700 hover:bg-green-50 hover:text-green-700'
            }`}
          >
            ✓ Confirm
          </button>
          <button
            onClick={() => onAction('discard')}
            className={`px-3 py-1 rounded text-sm font-medium ${
              isDiscarded
                ? 'bg-red-100 text-red-800 border border-red-300'
                : 'bg-gray-100 text-gray-700 hover:bg-red-50 hover:text-red-700'
            }`}
          >
            ✗ Discard
          </button>
        </div>
      </div>
    </div>
  );
}

interface BirthplaceItemProps {
  birthplace: Birthplace;
  isConfirmed: boolean;
  isDiscarded: boolean;
  onAction: (action: 'confirm' | 'discard') => void;
}

function BirthplaceItem({ birthplace, isConfirmed, isDiscarded, onAction }: BirthplaceItemProps) {
  return (
    <div className="border border-gray-200 rounded-lg p-4">
      <div className="flex justify-between items-start">
        <div className="flex-1">
          <h3 className="font-medium text-gray-900">{birthplace.location_name}</h3>
          {birthplace.location_wikidata_id && (
            <p className="text-gray-600 text-sm mt-1">Wikidata: {birthplace.location_wikidata_id}</p>
          )}
          <div className="mt-2">
            {birthplace.source_urls.map((url, index) => (
              <a
                key={index}
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:text-blue-800 text-sm inline-block mr-3"
              >
                Source {index + 1} →
              </a>
            ))}
          </div>
        </div>
        <div className="flex space-x-2 ml-4">
          <button
            onClick={() => onAction('confirm')}
            className={`px-3 py-1 rounded text-sm font-medium ${
              isConfirmed
                ? 'bg-green-100 text-green-800 border border-green-300'
                : 'bg-gray-100 text-gray-700 hover:bg-green-50 hover:text-green-700'
            }`}
          >
            ✓ Confirm
          </button>
          <button
            onClick={() => onAction('discard')}
            className={`px-3 py-1 rounded text-sm font-medium ${
              isDiscarded
                ? 'bg-red-100 text-red-800 border border-red-300'
                : 'bg-gray-100 text-gray-700 hover:bg-red-50 hover:text-red-700'
            }`}
          >
            ✗ Discard
          </button>
        </div>
      </div>
    </div>
  );
}