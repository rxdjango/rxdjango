# Goal

Create tests for the makefrontend command with the counter app

# Requirements

- create examples/backend/counter/tests/test_makefrontend.py, that will:
  - create_app_channels for counter
  - check the generated typescript
    - there must be a proper ContextChannel class
    - inside, there must be a counter: int = 0

# Constraints

- Do not make tests pass, they will fail
