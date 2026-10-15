import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Layout } from "./components/Layout";
import { RankingsPage } from "./pages/RankingsPage";
import { SectorPage } from "./pages/SectorPage";
import { TickerPage } from "./pages/TickerPage";
import { ThemeProvider } from "./theme";
import "./styles/theme.css";

const qc = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={qc}>
      <ThemeProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<RankingsPage />} />
              <Route path="nganh" element={<SectorPage />} />
              <Route path="t/:symbol" element={<TickerPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
