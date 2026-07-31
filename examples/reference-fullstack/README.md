# Reference Full-Stack Feature

This example is intentionally outside the default generated project. Enable it with `include_reference_feature: true` when you want a concrete architecture reference.

The feature is a small `todos` module showing:

- backend domain -> application use case -> repository port -> infrastructure adapter -> FastAPI route
- frontend page -> feature component -> composable -> API client -> shared UI
- unit, integration, component, contract, and E2E test locations
