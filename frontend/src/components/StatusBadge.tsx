import { STATUS_LABELS } from "../landlord/labels";
import type { MyListingStatus } from "../landlord/myListingsStore";

const STYLES: Record<MyListingStatus, string> = {
  draft: "bg-canvas-sunken text-ink-soft",
  changes_requested: "bg-warn-soft text-warn",
  pending_moderation: "bg-warn-soft text-warn",
  published: "bg-ok-soft text-ok",
};

/** Where a landlord's listing is on its way to publication. */
export function StatusBadge({ status }: { status: MyListingStatus }) {
  return <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${STYLES[status]}`}>{STATUS_LABELS[status]}</span>;
}
