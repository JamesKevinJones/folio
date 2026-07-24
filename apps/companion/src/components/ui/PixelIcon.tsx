type PixelIconProps = {
  name:
    | "mic"
    | "search"
    | "link"
    | "news"
    | "export"
    | "settings"
    | "grid"
    | "marquee"
    | "warn"
    | "mark";
  active?: boolean;
  size?: number;
};

const paths: Record<PixelIconProps["name"], string> = {
  mark: "M2 2h4v2H4v8h2v2H2V2zm8 0h4v12h-2V4h-2V2z",
  mic: "M6 2h4v6H6V2zm-2 7h8v2H4V9zm3 2h2v3H7v-3zm-3 3h8v2H4v-2z",
  search: "M3 3h6v6H3V3zm7 2h1v1h-1V5zm1 1h1v1h-1V6zm1 1h1v1h-1V7zm1 1h2v2h-2V8zM4 4h4v4H4V4z",
  link: "M3 6h5v2H3V6zm5 0h2v1H8V6zm0 3h2v1H8V9zm2-2h3v2h-3V7zM3 9h5v2H3V9z",
  news: "M2 3h12v2H2V3zm0 3h8v2H2V6zm0 3h12v2H2V9zm0 3h8v2H2v-2z",
  export: "M7 2h2v7H7V2zM4 7h2v2H4V7zm6 0h2v2h-2V7zM2 11h12v3H2v-3z",
  settings: "M6 2h4v2H6V2zM2 6h4v4H2V6zm8 0h4v4h-4V6zM6 12h4v2H6v-2z",
  grid: "M2 2h5v5H2V2zm7 0h5v5H9V2zM2 9h5v5H2V9zm7 0h5v5H9V9z",
  marquee: "M2 6h2v4H2V6zm3 0h2v4H5V6zm3 0h2v4H8V6zm3 0h2v4h-2V6z",
  warn: "M7 2h2v8H7V2zm0 10h2v2H7v-2z",
};

export function PixelIcon({ name, active = false, size = 16 }: PixelIconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      aria-hidden
      style={{
        imageRendering: "pixelated",
        color: active ? "var(--folio-yellow)" : "var(--folio-muted)",
        flexShrink: 0,
      }}
    >
      <path fill="currentColor" d={paths[name]} />
    </svg>
  );
}
