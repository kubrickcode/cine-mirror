interface StarRatingProps {
  value: number | null;
  onChange: (rating: number | null) => void;
}

const HALF_STEPS = Array.from({ length: 11 }, (_, i) => i * 0.5); // 0.0 ~ 5.0

export function StarRating({ value, onChange }: StarRatingProps) {
  const filled = value ?? 0;

  return (
    <div className="flex items-center gap-2">
      <div className="flex">
        {[1, 2, 3, 4, 5].map((star) => {
          const full = filled >= star;
          const half = !full && filled >= star - 0.5;
          return (
            <span key={star} className="relative cursor-pointer text-2xl select-none">
              <span className="text-gray-200">★</span>
              {(full || half) && (
                <span
                  className="absolute inset-0 text-yellow-400 overflow-hidden"
                  style={{ width: full ? "100%" : "50%" }}
                >
                  ★
                </span>
              )}
              {/* 0.5 단위 입력: 왼쪽 절반 = star-0.5, 오른쪽 절반 = star */}
              <button
                type="button"
                className="absolute inset-y-0 left-0 w-1/2"
                onClick={() => onChange(filled === star - 0.5 ? null : star - 0.5)}
                aria-label={`${star - 0.5}점`}
              />
              <button
                type="button"
                className="absolute inset-y-0 right-0 w-1/2"
                onClick={() => onChange(filled === star ? null : star)}
                aria-label={`${star}점`}
              />
            </span>
          );
        })}
      </div>
      <span className="text-sm text-gray-500">
        {value != null ? `${value}점` : "평점 없음"}
      </span>
      {value != null && (
        <button
          type="button"
          onClick={() => onChange(null)}
          className="text-xs text-gray-400 hover:text-gray-600"
        >
          초기화
        </button>
      )}
      <select
        value={value ?? ""}
        onChange={(e) =>
          onChange(e.target.value === "" ? null : Number(e.target.value))
        }
        className="ml-2 text-sm border border-gray-200 rounded px-1 py-0.5"
        aria-label="평점 직접 입력"
      >
        <option value="">-</option>
        {HALF_STEPS.map((v) => (
          <option key={v} value={v}>
            {v}
          </option>
        ))}
      </select>
    </div>
  );
}
