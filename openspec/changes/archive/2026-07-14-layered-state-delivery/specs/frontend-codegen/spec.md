# Frontend Codegen — Delta: layered-state-delivery

## MODIFIED Requirements

### Requirement: Typed model interfaces per app

For every serializer reachable from an app's `rx.model` fields (transitively through nesting), the generator SHALL emit a TypeScript interface in `<app>/<app>.models.ts` matching the serializer's output shape — the `Serializer` suffix stripped from the name, DRF field types mapped to TypeScript types, `allow_null` adding `| null`. Each generated model interface SHALL carry the discriminant `_loaded: true`, and relation slots SHALL be typed as a discriminated union with the unloaded stub shape (`{ id, _loaded: false }`), so partial state during delivery is expressed in the types without casts: a nested single relation types as `Company | Unloaded` (plus `| null` when `allow_null`), a nested list as `(Task | Unloaded)[]`. The channels file imports these types for its model-field properties.

#### Scenario: Nested serializers become interfaces

- **WHEN** `UserSerializer` (name, nested company) feeds a `rx.model` field
- **THEN** `nested_model.models.ts` exports `interface User` with `_loaded: true` and `company: Company | Unloaded`, and `interface Company` with `_loaded: true`
- **AND** the generated channel declares `user: User | null = null`

#### Scenario: Narrowing on the discriminant

- **WHEN** a component reads `user.company`
- **THEN** checking `company._loaded` narrows the type to `Company` in the true branch and to the unloaded stub in the false branch, with no cast
