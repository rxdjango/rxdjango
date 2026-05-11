import React from 'react';
import { render, screen } from '@testing-library/react';
import App from './App';

test('renders overview copy', () => {
  render(<App />);
  expect(
    screen.getByText(/RxDjango demo/i),
  ).toBeInTheDocument();
});
