# Actions

## Purpose

`@action` exposes an async channel method as a client-callable RPC, dispatched over `ac` frames (see `wire-protocol`). Authorization is a reactive gate: an action can require a truthy channel attribute at call time (ADR-0007), per action or channel-wide via `Meta.action_requires`.

## Requirements

### Requirement: Actions are declared with @action on async methods

A client-callable method SHALL be declared with the `@action` decorator and SHALL be `async`; decorating a synchronous method raises `ActionNotAsync` at import time.

#### Scenario: Sync method rejected at import

- **WHEN** `@action` decorates a non-async method
- **THEN** module import fails with `ActionNotAsync`

### Requirement: Only registered actions are callable

An `ac` request naming a method that is not `@action`-decorated — including missing attributes and undecorated channel methods — SHALL be rejected with a 403 error response and SHALL NOT execute.

#### Scenario: Undecorated method called

- **WHEN** the client calls a channel method that lacks `@action`
- **THEN** the response is an error frame with code 403

### Requirement: Positional dispatch with datetime conversion

Action parameters SHALL be passed positionally from the request's `p` array. Parameters type-hinted `datetime` SHALL be converted from ISO-format strings before the method runs; the method's return value is sent back as the response's `r`.

#### Scenario: Parameters and return value round-trip

- **WHEN** the client calls `authorize("password")` on the authorization channel
- **THEN** the method receives the string positionally and its return value (`true`) arrives as the response's `r`

### Requirement: Exceptions map to error responses

An action raising `ForbiddenError` SHALL produce a 403 error response. Any other exception SHALL produce an error response whose code is the exception's `code` attribute, defaulting to 500, and whose message is the exception text.

#### Scenario: Unhandled exception

- **WHEN** an action body raises `ValueError('bad input')`
- **THEN** the client receives an error response `[500, 'bad input']`

### Requirement: Per-action reactive gate via requires

`@action(requires='<field>')` SHALL gate the action on the named channel attribute being truthy at call time. When the attribute is falsy, the call is rejected with a 403 response, the body does not run, and the connection stays open.

#### Scenario: Rejected before authorization

- **WHEN** a client calls `increment` (declared `requires='authorized'`) while `authorized` is `False`
- **THEN** the call rejects with code 403 and `counter` is unchanged

#### Scenario: Granted after the gate flips

- **WHEN** the client first calls `authorize('password')`, which sets `self.authorized = True`, then calls `increment`
- **THEN** `increment` runs and `counter` becomes 1

### Requirement: Channel-wide default gate via Meta.action_requires

A channel declaring `Meta.action_requires = '<field>'` SHALL apply that gate to every action that does not declare its own `requires`. An action's explicit `requires` replaces the channel default rather than combining with it.

#### Scenario: Default gate covers undeclared actions

- **WHEN** a channel declares `Meta.action_requires = 'authorized'` and `increment` carries a bare `@action`
- **THEN** calling `increment` while `authorized` is falsy rejects with 403

### Requirement: anonymous=True bypasses all gates

An action declared `@action(anonymous=True)` SHALL be callable regardless of any per-action or channel-wide gate.

#### Scenario: Anonymous authorize under a channel-wide gate

- **WHEN** a channel gates all actions on `authorized` and declares `authorize` with `anonymous=True`
- **THEN** an unauthorized client can call `authorize` to flip the gate, then call the other actions
