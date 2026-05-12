# Goal

Implement the @memo decorator

# Requirement

- memo/channels.py and carousel/channels.py have the exact same functionality for the UI
- @memo decorator makes a property, that is recalculated everytime the parameter passed to it changes
- @memo supports a list of parameters, and if any element in the list changes, value is recalculated
- value is not recalculated if an event occurs but dependency is not updated
