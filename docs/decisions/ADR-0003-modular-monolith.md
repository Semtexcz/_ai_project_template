# ADR-0003: Use Feature-Oriented Modular Monoliths

> Status: Accepted
> Date: 2026-07-31

## Context

Projects should start small while keeping clear architecture and growth paths.

## Options

- Flat scripts only
- Layered technical packages
- Feature-oriented modular monolith
- Microservices

## Decision

Use feature-oriented modules for backend and frontend. Backend dependencies flow from domain to application to infrastructure to API wiring. Frontend pages compose feature components, composables, and shared UI.

## Consequences

### Positive

- The first vertical slice stays small.
- Domain code remains testable.
- New modules can be added without premature distributed infrastructure.

### Negative

- Architecture checks must prevent shared folders from becoming dumping grounds.

## Revisit When

Independent deployment becomes a proven operational requirement.
