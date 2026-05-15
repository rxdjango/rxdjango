# Goal

Implement rxdjango.ts.channels.create_app_channels.

# Reference

See how it was done in rxdjango-0.0.x, just for reference, but implement the minimum for the CounterChannel in the examples/backend/counter to work

See python/src/rxdjango/sdk.py.

# Requirements

- Create a class in {RX_FRONTEND_DIR}/{app}/app.channels.ts
  - This should extend ContextChannel from @rxdjango/react
- Class must declare a field for each rx[type] field
  - For now, map type int -> number and str -> string
- You will also need to implement _rx_fields scan in ContextChannelMeta

# Guidelines

Keep it simple, minimal. We are doing baby steps. The goal is the counter. We are adding string only, to have more than one type mapped.

# Constraints

- Do not implement the base ContextChannel class, just trust it
- Do not implement any pairing of _rx_fields, the properties will just be declared and overriden later
