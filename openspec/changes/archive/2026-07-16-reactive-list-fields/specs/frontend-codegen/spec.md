# Frontend Codegen — Delta

## ADDED Requirements

### Requirement: List field types are generated as arrays

For an `rx[list[S]]` field, the generated property type SHALL be the element union mapped to TypeScript and suffixed `[]`, with the union parenthesized when it has more than one member: `list[int]` → `number[]`, `list[int | str]` → `(number | string)[]`, `list[str | None]` elements → `(string | null)[]`. The field-level None union adds `| null` outside the array: `rx[list[int] | None]` → `number[] | null`. The property is initialized to the server default rendered as a TypeScript literal.

#### Scenario: Homogeneous list field

- **WHEN** the server channel declares `items = rx[list[int]]([1, 2])`
- **THEN** the generated class has `items: number[] = [1, 2];`

#### Scenario: Union elements are parenthesized

- **WHEN** the server channel declares `mixed = rx[list[int | str]]([])`
- **THEN** the generated class has `mixed: (number | string)[] = [];`

#### Scenario: Optional list

- **WHEN** the server channel declares `items = rx[list[int] | None]()`
- **THEN** the generated class has `items: number[] | null = null;`
