import React from 'react';

const App = () => {
  const [count, setCount] = React.useState(0);

  return (
    <div>
      <h1>Mock App</h1>
      <p>Count: {count}</p>
      <button onClick={() => setCount((c) => c + 1)}>Increment</button>
    </div>
  );
};

export default App;
