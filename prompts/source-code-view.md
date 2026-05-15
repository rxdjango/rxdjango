# Goal

Allow source code of the examples to be rendered at the frontend

# Task

Create view in testing app (examples/backend/testing/views.py) that serves the source code

# Requirements

- Receive two arguments, in URL: app and filename
  - app must match [a-z_]+
  - filename must match [a-zA-A0-9_.-]+
- App must be validated
  - must be one valid installed app, present in folder examples/backend/app
  - testing app is invalid
- Filename must be validated to be either one of:
  - channels.py, models.py
  - app.channels.ts
- Directory is determined by file extension, either from backend or frontend folder
- It serves the file directly
- URL must be registered at urls.py
- Path will be something like /src/{app}/{filename}
