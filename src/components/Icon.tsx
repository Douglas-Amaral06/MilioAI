type Name =
  | "plus"
  | "search"
  | "panel"
  | "close"
  | "arrow"
  | "edit"
  | "trash"
  | "copy"
  | "check"
  | "down"
  | "pending";
const paths: Record<Name, string> = {
  copy: "M9 8h11v13H9zM15 8V3H4v13h5",
  check: "m5 12 4 4L19 6",
  down: "M12 5v14m-6-6 6 6 6-6",
  pending: "M5 12h.01M12 12h.01M19 12h.01",
  plus: "M12 5v14M5 12h14",
  search: "m16 16 4 4M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0",
  panel:
    "M9 3v18M4 3h16a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1",
  close: "m6 6 12 12M6 18 18 6",
  arrow: "M12 19V5m-6 6 6-6 6 6",
  edit: "m15 4 5 5M4 20l5-1L20 8a2 2 0 0 0-5-5L4 14v6",
  trash: "M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7",
};
export function Icon({ name }: { name: Name }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name]} />
    </svg>
  );
}
