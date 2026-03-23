import { useEffect, useState } from "react";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function App() {
  const [backendStatus, setBackendStatus] = useState("Checking backend");

  useEffect(() => {
    let cancelled = false;

    async function checkBackend() {
      try {
        const response = await fetch(`${apiBaseUrl}/health`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const payload = await response.json();
        if (!cancelled) {
          setBackendStatus(payload.status === "ok" ? "Backend healthy" : "Backend responded");
        }
      } catch (error) {
        if (!cancelled) {
          setBackendStatus("Backend not reachable yet");
        }
      }
    }

    checkBackend();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="app-shell">
      <section className="hero-card">
        <p className="eyebrow">AutoPilot Local Development</p>
        <h1>Full stack services running in one Compose stack.</h1>
        <p className="lede">
          This frontend is intentionally minimal for TICKET-002. It confirms the Vite
          runtime, the container wiring, and the backend API entry point for later MVP
          work.
        </p>
        <div className="status-grid">
          <article className="status-card">
            <span className="status-label">Frontend</span>
            <strong>Vite dev server running</strong>
          </article>
          <article className="status-card">
            <span className="status-label">Backend</span>
            <strong>{backendStatus}</strong>
          </article>
          <article className="status-card">
            <span className="status-label">API Base URL</span>
            <strong>{apiBaseUrl}</strong>
          </article>
        </div>
      </section>
    </main>
  );
}

export default App;
