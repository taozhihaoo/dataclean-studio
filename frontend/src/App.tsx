import { Link, NavLink, Route, Routes, useParams } from "react-router-dom";
import DashboardPage from "./pages/DashboardPage";
import UploadPage from "./pages/UploadPage";
import MergePage from "./pages/MergePage";
import JobLayout from "./pages/JobLayout";
import DatasetPage from "./pages/DatasetPage";
import PipelinePage from "./pages/PipelinePage";
import ValidationPage from "./pages/ValidationPage";
import ExportPage from "./pages/ExportPage";
import ReportPage from "./pages/ReportPage";

function JobRoutes() {
  const { jobId } = useParams();
  return (
    <JobLayout jobId={jobId!}>
      <Routes>
        <Route index element={<DatasetPage />} />
        <Route path="pipeline" element={<PipelinePage />} />
        <Route path="validation" element={<ValidationPage />} />
        <Route path="export" element={<ExportPage />} />
        <Route path="report" element={<ReportPage />} />
      </Routes>
    </JobLayout>
  );
}

export default function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-mark" aria-hidden="true">
            ▤
          </span>
          <span>
            DataClean <strong>Studio</strong>
          </span>
        </Link>
        <nav className="topnav" aria-label="Primary">
          <NavLink to="/" end>
            Dashboard
          </NavLink>
          <NavLink to="/upload">Upload</NavLink>
          <NavLink to="/merge">Merge</NavLink>
        </nav>
        <span className="topbar-note" title="Files are processed locally by the bundled backend">
          local-first · no cloud
        </span>
      </header>
      <main className="content">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/merge" element={<MergePage />} />
          <Route path="/jobs/:jobId/*" element={<JobRoutes />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <footer className="footer">
        DataClean Studio — an independent portfolio project. CSV/Excel cleaning, validation and
        export, running entirely on your machine.
      </footer>
    </div>
  );
}

function NotFound() {
  return (
    <div className="empty-state card">
      <h2>Page not found</h2>
      <p>The page you are looking for does not exist.</p>
      <Link className="btn btn-primary" to="/">
        Back to dashboard
      </Link>
    </div>
  );
}
