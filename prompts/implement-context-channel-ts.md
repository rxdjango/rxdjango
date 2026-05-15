# Goal

Create the @rxdjango/react typescript package at packages/react

# Requirements

- Follow npm packaging best practices
- Create an empty ContextChannel class as boilerplate
- Create a useChannel empty hook as boilerplate, receiving a ContextChannel subclass as parameter
  - Returns a ContextChannel instance
- Implement basic wiring with useSyncExternalStore
  - declare subscribe
  - make a basic incrementing getVersion() as getSnapshot
  - make a stub for async callAction(action: string, params: any[])
