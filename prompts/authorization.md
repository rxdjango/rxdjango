# Goal

Implement the "requires" parameter to the @action decorator to allow authorization

# Requirements

- The example on backend/authorization/channels.py must work
- If action is called without authorization, 403 code should be returned (see other errors 400 and 500 in code)
- Write integration tests for authorization/channels.py
  - One test checking the sequence with proper increment after sending password
  - One test receiving 403 without receiving password
