import React from 'react';
import { render, screen } from '@testing-library/react';
import App from './App';

test('renders home pitch', () => {
  render(<App />);
  expect(
    screen.getByText(/typed React SDK/i),
  ).toBeInTheDocument();
});
