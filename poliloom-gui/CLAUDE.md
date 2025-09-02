# PoliLoom GUI - Project Specification

## Project Purpose

The PoliLoom GUI is a web application that provides a user interface for confirming the accuracy of politician metadata automatically extracted by the PoliLoom project. Users review and validate properties (birth dates, birthplaces) and political positions extracted by LLMs from government portals, Wikipedia, and other web sources before the data is submitted to Wikidata.

## Technical Requirements

- Modern web application using Next.js with App Router
- React-based user interface with TypeScript
- Responsive design with Tailwind CSS
- MediaWiki OAuth integration for authentication
- RESTful API integration with the PoliLoom backend

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
- **Archived Pages**: Access and display archived web pages from government portals, Wikipedia, and other sources for verification
- **Text Highlighting**: Automatic highlighting of proof text within archived pages using CSS Custom Highlight API

### 3. User Experience

- **Minimal, Clean UI**: Simple interface focused on data verification
- **Single-Task Focus**: Show one politician at a time to avoid cognitive overload
- **Loading States**: Clear feedback during API operations
- **Error Handling**: Graceful error handling with user-friendly messages

## API Integration Requirements

The application integrates with the PoliLoom API backend to:

- Fetch unconfirmed politician data with pagination support
- Submit evaluation decisions for extracted data
- Handle authentication via MediaWiki OAuth tokens
- Support configurable API base URL for different environments
- Retrieve archived web pages from various sources for context and verification

The API specification is available via OpenAPI documentation from the backend service (runs at `http://localhost:8000` in development) at `/openapi.json`.

## Data Model

### Core Entities

**Politicians**: Each politician contains:

- Basic identification (ID, name, Wikidata ID)
- Unconfirmed properties (birth date, etc.)
- Unconfirmed political positions (with dates)
- Unconfirmed birthplaces (with location data)

**Evaluations**: Users can confirm or discard individual entities with:

- Entity type and ID reference
- Confirmation result (confirmed/discarded)
- Batch submission support

## Application Architecture

### Page Structure

- **Main Interface**: Single-politician evaluation workflow
- **Authentication**: MediaWiki OAuth login and callback handling
- **Protected Routes**: All evaluation pages require authentication

### Component Architecture

- **Evaluation Components**: Individual UI for confirming properties, positions, and birthplaces
- **Navigation**: Simple sequential navigation between politicians
- **Text Highlighting System**: CSS Custom Highlight API implementation for highlighting proof text in archived pages
- **Iframe Integration**: Secure display of archived web pages with automatic highlighting
- **Reusable UI**: Consistent design components throughout

## User Interface Requirements

### Main Evaluation Interface

- Display one politician at a time with all extracted data
- Individual confirm/discard actions for each data item
- Sequential navigation between politicians
- Progress indicator showing current position
- Links to external resources (Wikipedia/Wikidata)
- Embedded archived web pages with highlighted proof text for source verification

### Authentication Interface

- MediaWiki OAuth login integration
- Clear explanation of the tool's purpose
- Minimal, focused login experience

## User Experience Requirements

### Design Principles

- Clean, professional interface suitable for data verification
- Clear visual hierarchy with proper spacing
- Accessible design with good color contrast
- Clear call-to-action buttons for confirm/discard actions

### Usability Requirements

- **Clarity**: Show source context for extracted data
- **Efficiency**: Minimize clicks for common evaluation actions
- **Safety**: Clear feedback before irreversible actions
- **Responsiveness**: Optimized for desktop use (1024px+)

### Target Platform

- **Evergreen** Only support modern evergreen browsers, no fallbacks.

## Testing Strategy

**IMPORTANT**: The development server is already running

**Framework**: Vitest + React Testing Library for fast, modern testing with excellent TypeScript support.

**Approach**: Minimal, behavior-focused testing that covers critical functionality without over-engineering.

**Testing Priorities**:

- Authentication flow (OAuth login/logout)
- Core evaluation workflow (confirm/discard actions)
- Politician data display and navigation
- API integration and error handling

**Testing Scope**:

- Focus on user-facing behavior rather than implementation details
- Manual testing for OAuth integration
- Automated testing for core evaluation components using Vitest
- Basic error scenario coverage
