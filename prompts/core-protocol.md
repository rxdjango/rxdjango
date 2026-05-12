# Goal

Specify the websocket protocol between Python and React

## Task

Create ADR 002 with protocol core definition

## Protocol

### t key

Every message carries "t" key, with a string indicating message type, which may be:

- ready: first message sent by server on connection
- rx: a rx field being reactively updated by server
- ac: an action, first message by client, answer by server with same type

#### t: ready

ready type carries:

- protocol: an string with semantic version of the protocol

#### t: rx

rx type carries:

- f: string with the field being updated
- v: value of the field being updated (optional)
- o: operation that will be used (optional)

either v or o must be set, or both.

without operation, the value will be set to the field.
operation can be, for example "append", then with a value, or "pop", with no value.

#### t: ac

ac type carries, when initiated by client

- a: the action method being called
- id: a uid created by the client
- p: the parameters to the action

when responding:

- id: the same uid
- r: the result

note: actions starting with '_' are reserved internal actions and cannot be used
by developer.
