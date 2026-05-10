import React, { useState } from 'react';
import { IndexPage } from './app/IndexPage';
import { CounterPage } from './app/examples/counter/CounterPage';

type View = 'index' | 'counter';

function App() {
  const [view, setView] = useState<View>('index');

  if (view === 'counter') {
    return <CounterPage onBack={() => setView('index')} />;
  }
  return <IndexPage onSelectCounter={() => setView('counter')} />;
}

export default App;
