# PoliLoom GUI - Confirmation Interface

This is a modern Next.js application that provides a user interface for confirming extracted politician metadata from the PoliLoom project. Users can review and confirm properties (birth dates, birthplaces) and political positions extracted by LLMs from Wikipedia and other web sources.

## Project Overview

**Purpose**: Allow users to confirm the accuracy of automatically extracted politician data before it gets submitted to Wikidata.

**Tech Stack**:

- Next.js 15+ (App Router)
- React 19+
- TypeScript 5+
- Tailwind CSS 4+
- MediaWiki OAuth for authentication
- Native fetch API for HTTP requests

## Core Features

### 1. Authentication

- **MediaWiki OAuth Integration**: Users authenticate using their Wikipedia/MediaWiki accounts
- **Session Management**: Secure session handling with proper token management
- **Protected Routes**: All confirmation pages require authentication

### 2. Data Evaluation Interface

- **Single Politician View**: Show one politician at a time with their extracted data
- **Sequential Navigation**: Move through politicians one by one
- **Individual Item Actions**: Evaluate each property, position, and birthplace individually
- **Batch Evaluation**: Submit multiple evaluations in a single request

### 3. User Experience

- **Minimal, Clean UI**: Simple interface focused on data verification
- **Single-Task Focus**: Show one politician at a time to avoid cognitive overload
- **Loading States**: Clear feedback during API operations
- **Error Handling**: Graceful error handling with user-friendly messages

## API Integration

The GUI communicates with the PoliLoom API backend:

**Base URL**: `http://localhost:8000` (development) / configurable for production

**Key Endpoints**:

- `GET /politicians/` - Fetch unconfirmed politicians (with pagination)
- `POST /politicians/evaluate` - Submit evaluation decisions for extracted data

**Authentication**: All API calls include MediaWiki OAuth tokens in Authorization headers.

**OpenAPI Documentation**: The complete API specification is available at `http://localhost:8000/openapi.json` when the backend server is running. To fetch it using curl:

```bash
curl http://localhost:8000/openapi.json
```

## Data Types

### Politician Object

```typescript
interface UnconfirmedPolitician {
  id: string;
  name: string;
  wikidata_id: string | null;
  unconfirmed_properties: Property[];
  unconfirmed_positions: Position[];
  unconfirmed_birthplaces: Birthplace[];
}

interface Property {
  id: string;
  type: string;
  value: string;
}

interface Position {
  id: string;
  position_name: string;
  start_date: string | null;
  end_date: string | null;
}

interface Birthplace {
  id: string;
  location_name: string;
  location_wikidata_id: string | null;
}
```

### Evaluation Payload

```typescript
interface EvaluationRequest {
  evaluations: EvaluationItem[];
}

interface EvaluationItem {
  entity_type: string;
  entity_id: string;
  result: "confirmed" | "discarded";
}

interface EvaluationResponse {
  success: boolean;
  message: string;
  processed_count: number;
  errors: string[];
}
```

## Application Structure

```
src/
├── app/
│   ├── page.tsx                 # Main confirmation interface
│   ├── auth/
│   │   ├── login/page.tsx       # MediaWiki OAuth login
│   │   └── callback/page.tsx    # OAuth callback handler
│   └── layout.tsx               # Root layout
├── components/
│   ├── ui/                      # Reusable UI components
│   ├── PoliticianEvaluation.tsx # Main evaluation component
│   ├── PropertyItem.tsx         # Individual property evaluation
│   ├── PositionItem.tsx         # Individual position evaluation
│   ├── BirthplaceItem.tsx       # Individual birthplace evaluation
│   └── Navigation.tsx           # Simple navigation
├── lib/
│   ├── api.ts                   # API client functions
│   ├── auth.ts                  # MediaWiki OAuth helpers
│   └── utils.ts                 # Utility functions
└── types/
    └── index.ts                 # TypeScript type definitions
```

## Key Pages & Components

### 1. Main Evaluation Interface (`/`)

- Single politician display with all extracted data
- Individual confirm/discard actions for each property, position, and birthplace
- "Next" button to move to the next politician
- Progress indicator (e.g., "Politician 5 of 23")

### 2. Login Page (`/auth/login`)

- MediaWiki OAuth login button
- Simple explanation of the tool
- Minimal, focused interface

### 3. Key Components

**PoliticianEvaluation**:

- Main component showing politician name and Wikidata ID
- Links to Wikipedia/Wikidata
- Contains all PropertyItem, PositionItem, and BirthplaceItem components
- "Next Politician" navigation

**PropertyItem**:

- Shows property type and extracted value
- Individual confirm/discard buttons
- Minimal, inline design

**PositionItem**:

- Shows position name and dates
- Individual confirm/discard buttons
- Clear, compact layout

**BirthplaceItem**:

- Shows location name and Wikidata ID (if available)
- Individual confirm/discard buttons
- Consistent layout with other items

## Environment Configuration

Create `.env.local`:

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
MEDIAWIKI_OAUTH_CLIENT_ID=your_client_id
MEDIAWIKI_OAUTH_CLIENT_SECRET=your_client_secret
MEDIAWIKI_OAUTH_CALLBACK_URL=http://localhost:3000/auth/callback
NEXTAUTH_SECRET=your_nextauth_secret
NEXTAUTH_URL=http://localhost:3000
```

## Development Setup

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Start production server
npm start
```

## Dependencies

**Core**:

- `next`: ^15.0.0
- `react`: ^19.0.0
- `typescript`: ^5.6.0

**UI & Styling**:

- `tailwindcss`: ^4.0.0
- `@headlessui/react`: ^2.0.0 (for accessible UI components)
- `lucide-react`: ^0.400.0 (icons)

**Authentication**:

- `next-auth`: ^5.0.0 (for session management)
- Custom MediaWiki OAuth implementation

**API & Data**:

- Native fetch API: HTTP client with built-in error handling
- `swr`: Data fetching and caching

**Development**:

- `eslint`: Code linting
- `prettier`: Code formatting

## Design Guidelines

### Visual Design

- Clean, professional interface suitable for data verification
- Clear visual hierarchy with proper spacing
- Consistent color scheme (consider accessibility)
- Clear CTAs for confirm/discard actions

### UX Principles

- **Clarity**: Always show source of extracted data
- **Efficiency**: Minimize clicks needed for common actions
- **Safety**: Clear confirmation before irreversible actions
- **Feedback**: Always show status of operations

### Responsive Breakpoints

- Mobile: Not supported (redirect to desktop)
- Desktop: 1024px+ (optimized for desktop use)

## Error Handling

- **Network Errors**: Retry mechanisms with user feedback
- **Authentication Errors**: Clear re-login prompts
- **Validation Errors**: Inline error messages
- **Server Errors**: Graceful fallbacks with error reporting

## Security Considerations

- **OAuth Token Security**: Secure storage and transmission
- **CSRF Protection**: Built-in Next.js CSRF protection
- **Input Validation**: Client-side validation with server-side verification
- **XSS Prevention**: Proper sanitization of displayed content

## Performance Optimization

- **Code Splitting**: Automatic with Next.js App Router
- **Image Optimization**: Next.js Image component for any politician photos
- **Data Caching**: SWR for efficient data fetching
- **Bundle Analysis**: Regular bundle size monitoring

## Accessibility

- **Keyboard Navigation**: Full keyboard accessibility
- **Screen Readers**: Proper ARIA labels and semantic HTML
- **Color Contrast**: WCAG AA compliance
- **Focus Management**: Clear focus indicators

## Testing Strategy

**Minimal Testing Approach**:
Focus only on critical functionality that could break the confirmation workflow.

**What to Test**:

- Authentication flow (OAuth login/logout)
- Politician data display and rendering
- Confirm/discard actions for properties, positions, and birthplaces
- Navigation to next politician
- Basic error handling

**What NOT to Test**:

- Complex user interactions
- Performance testing
- Accessibility testing (beyond basic checks)
- Cross-browser compatibility (focus on Chrome/Firefox)

**Testing Tools**:

- Jest + React Testing Library for critical component tests
- Simple integration tests for API calls
- Manual testing for OAuth flow

**Test Files**:

```
__tests__/
├── components/
│   ├── PoliticianEvaluation.test.tsx
│   ├── PropertyItem.test.tsx
│   ├── PositionItem.test.tsx
│   └── BirthplaceItem.test.tsx
└── lib/
    └── api.test.ts
```

## Deployment

**Development**: Vercel (recommended) or similar platform
**Production**: TBD based on infrastructure requirements

**Environment Variables**: Secure management of OAuth credentials and API endpoints

---
