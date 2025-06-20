"use client";

import { useState } from 'react';
import { Politician, Property, Position, ConfirmationRequest } from '@/types';
import { confirmPolitician } from '@/lib/api';

interface PoliticianConfirmationProps {
  politician: Politician;
  accessToken: string;
  onNext: () => void;
}

export function PoliticianConfirmation({ politician, accessToken, onNext }: PoliticianConfirmationProps) {
  const [confirmedProperties, setConfirmedProperties] = useState<Set<string>>(new Set());
  const [discardedProperties, setDiscardedProperties] = useState<Set<string>>(new Set());
  const [confirmedPositions, setConfirmedPositions] = useState<Set<string>>(new Set());
  const [discardedPositions, setDiscardedPositions] = useState<Set<string>>(new Set());
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

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      const confirmationData: ConfirmationRequest = {
        confirmed_properties: Array.from(confirmedProperties),
        discarded_properties: Array.from(discardedProperties),
        confirmed_positions: Array.from(confirmedPositions),
        discarded_positions: Array.from(discardedPositions),
      };

      await confirmPolitician(politician.id, confirmationData, accessToken);
      onNext();
    } catch (error) {
      console.error('Error confirming politician:', error);
      alert('Error submitting confirmation. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto bg-white shadow-lg rounded-lg p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">{politician.name}</h1>
        <p className="text-gray-600">Country: {politician.country}</p>
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

      <div className="flex justify-end">
        <button
          onClick={handleSubmit}
          disabled={isSubmitting}
          className="px-6 py-3 bg-indigo-600 text-white font-medium rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSubmitting ? 'Submitting...' : 'Next Politician'}
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
          <a
            href={property.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:text-blue-800 text-sm mt-2 inline-block"
          >
            View Source →
          </a>
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
            {position.start_date} - {position.end_date}
          </p>
          <a
            href={position.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:text-blue-800 text-sm mt-2 inline-block"
          >
            View Source →
          </a>
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