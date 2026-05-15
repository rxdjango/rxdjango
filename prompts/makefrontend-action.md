# Goal

Implement actions on makefrontend

# Requirements

- makefrontend command must generate one method in the frontend class for each method decorated with @action
- the same parameters declared in backend, with same types, must be declared in the frontend class
- the method must just return await this.rx.callAction('method_name', [param,...])
  - the same parameters declared at the action must be forwarded to callAction

## Testing

- Declare an action in testing.channels.TestingChannel with an int and string as parameters
- Declare an inert method, non-action
- Test that the action was declared in frontend, with proper int and str type
- Test that the inert method was not declared as action
- In counter.channels.CounterChannel, test that increment action was declared
