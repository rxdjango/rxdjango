# Goal

Make integration testing interface more generic

# Task

Refactor backend/testing/integration.py so that any sequence of actions may be done to get a result:

- execute() becomes eval()
- setup() also becomes eval()
- wait_for() and get_result() remains
- get_result is still the last one to be called
- each eval() and wait_for() append to a list of instructions
- each instruction is a type of Instruction, with render() interface
  - there will be EvalInstruction and WaitInstruction
- eval() renders to the instruction itself
- wait_for() renders to a loop waiting for condition, with optional timeout (default 2000)
- get_result renders the whole code
