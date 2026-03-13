import { Link, Outlet } from "react-router";

export function Layout() {
  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="max-w-3xl mx-auto flex items-center gap-6">
          <Link to="/" className="text-lg font-semibold text-gray-900">
            🎬 CineMirror
          </Link>
          <Link
            to="/search"
            className="text-sm text-gray-600 hover:text-gray-900"
          >
            영화 검색
          </Link>
        </div>
      </nav>
      <main className="max-w-3xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
