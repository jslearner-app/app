import axios from "axios";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
export const api = axios.create({ baseURL: API, withCredentials: true });

const NO_RETRY = ["/auth/refresh", "/auth/login", "/auth/register", "/auth/google/session"];
let refreshing = null;

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config || {};
    const skip = NO_RETRY.some((p) => (original.url || "").includes(p));
    if (error.response?.status === 401 && !original._retry && !skip) {
      original._retry = true;
      try {
        refreshing = refreshing || api.post("/auth/refresh");
        await refreshing;
        refreshing = null;
        return api(original);
      } catch (e) {
        refreshing = null;
      }
    }
    return Promise.reject(error);
  }
);

export function formatApiErrorDetail(detail) {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).filter(Boolean).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export const errMsg = (e) => formatApiErrorDetail(e?.response?.data?.detail) || e?.message;

export async function downloadFile(path, filename) {
  const res = await api.get(path, { responseType: "blob" });
  const url = window.URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export const delay = (ms) => new Promise((r) => setTimeout(r, ms));
