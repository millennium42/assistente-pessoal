import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import App from "./App";

function renderApp() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

test("renderiza dashboard sem depender de segredos", () => {
  renderApp();
  expect(screen.getByText("Assistente Pessoal V1")).toBeInTheDocument();
  expect(screen.getByText("Privacidade")).toBeInTheDocument();
  expect(screen.getByText("Chat")).toBeInTheDocument();
});
