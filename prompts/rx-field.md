# Goal

Implement rx[int]() field for ContextChannel

## Instructions

Implement RxField class, which will be available to be imported as rx.

The interface is the one at examples/backend/counter/channels.py

The RxField must:
- store the type it was given, so later the typescript interface can be generated.
- store an initial value
- implement getter and setter

This is an early implementation, so do not:
- verify the typing
- do anything with the setter other than setting the value

The file should be saved at packages/core/src/rxdjango/rx.py
