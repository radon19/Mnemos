/** Mnemos monogram. Keep the geometry in sync with public/icon.svg. */
export function BrandMark(): React.ReactNode {
  return (
    <svg className="brand-mark" viewBox="0 0 32 32" fill="none" aria-hidden="true" focusable="false">
      <rect className="brand-mark-tile" width="32" height="32" rx="9" />
      <path className="brand-mark-glyph" d="M8 23V9h3l5 8 5-8h3v14h-3v-8l-5 7-5-7v8H8Z" />
    </svg>
  );
}
