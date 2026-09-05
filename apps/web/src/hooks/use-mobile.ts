import { useSyncExternalStore } from "react";

const MOBILE_QUERY = "(max-width: 767px)";
const NARROW_WORKSPACE_QUERY = "(max-width: 1099px)";

function subscribeTo(query: string, onStoreChange: () => void) {
  const media = window.matchMedia(query);
  media.addEventListener("change", onStoreChange);
  return () => media.removeEventListener("change", onStoreChange);
}

const subscribeMobile = (onStoreChange: () => void) => subscribeTo(MOBILE_QUERY, onStoreChange);
const subscribeNarrowWorkspace = (onStoreChange: () => void) => subscribeTo(NARROW_WORKSPACE_QUERY, onStoreChange);
const mobileSnapshot = () => window.matchMedia(MOBILE_QUERY).matches;
const narrowWorkspaceSnapshot = () => window.matchMedia(NARROW_WORKSPACE_QUERY).matches;
const serverSnapshot = () => false;

export function useIsMobile() {
  return useSyncExternalStore(subscribeMobile, mobileSnapshot, serverSnapshot);
}

export function useIsNarrowWorkspace() {
  return useSyncExternalStore(subscribeNarrowWorkspace, narrowWorkspaceSnapshot, serverSnapshot);
}
