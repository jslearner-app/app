import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";

export function useClients() {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    try {
      const { data } = await api.get("/clients");
      setClients(data);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  return { clients, loading, reload };
}
