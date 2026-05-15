# Goal

Create an integration test for the counter

# Requirement

- create at examples/backend/counter/tests/test_integration.py. the test must:
  - use node to run the frontend code
  - run a local webserver for the backend
  - call the increment action
  - see that channel.counter incremented in the front

# Constraint

- Do not implement the actual functionality, the test will fail
