import { useCallback, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { api } from "@/lib/api";

const EVENT = "ledger:history-changed";

export const notifyHistoryChanged = () => window.dispatchEvent(new Event(EVENT));

export function useReviewCount(field = "needs_review") {
  const [count, setCount] = useState(0);
  const { pathname } = useLocation();

  const load = useCallback(() => {
    api.get("/history/review-count").then(({ data }) => setCount(data[field])).catch(() => {});
  }, [field]);

  useEffect(() => {
    load();
  }, [load, pathname]);

  useEffect(() => {
    window.addEventListener(EVENT, load);
    return () => window.removeEventListener(EVENT, load);
  }, [load]);

  return count;
}
