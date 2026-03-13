import { Link } from "react-router";

export function HomePage() {
  return (
    <div className="text-center py-12">
      <h1 className="text-3xl font-bold text-gray-900 mb-4">🎬 CineMirror</h1>
      <p className="text-gray-600 mb-8">나만의 영화 기록 저널</p>
      <Link
        to="/search"
        className="inline-block px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
      >
        영화 검색하기
      </Link>
    </div>
  );
}
