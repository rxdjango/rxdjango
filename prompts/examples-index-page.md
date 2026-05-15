# Goal

Implement the index page of the frontend examples app and the first counter example

# Requirements

- The main page of the app should be a list of all examples
- For now, only the Counter example exists
- Put a "RxDjango Demo" title and a boilerplate paragraph
- Below, a bullet list, with link to Counter in first and only item
- Create counter component inside src/app/examples/counter/

## Counter

### Code

channel = useChannel(CounterChannel);

// just use channel.counter and it should be updated

### UI

- A breadcrumb on top: RxDjango Demo -> Counter
  - With link back to index
- Show the counter value
- Show a button
- Click on the button to call channel.increment()
- Counter should increment in UI

# Guidelines

Make it simple, we are doing baby steps.
