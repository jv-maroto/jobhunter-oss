// Cliente HTTP minimal con fallback a mocks si el backend no responde.
import { mock } from "@/lib/mock";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new ApiError(`API ${path}: ${res.status}`, res.status);
  }
  // 204 No Content
  const text = await res.text();
  return (text ? JSON.parse(text) : null) as T;
}

/**
 * Subida multipart/form-data. NO fija Content-Type a propósito: el navegador
 * debe poner `multipart/form-data; boundary=...` él mismo. Usar `api()` aquí
 * rompería la subida porque fuerza `application/json`.
 */
export async function apiUpload<T>(
  path: string,
  formData: FormData,
  init?: Omit<RequestInit, "body" | "headers">,
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    ...init,
    body: formData,
    cache: "no-store",
  });
  if (!res.ok) {
    throw new ApiError(`API ${path}: ${res.status}`, res.status);
  }
  const text = await res.text();
  return (text ? JSON.parse(text) : null) as T;
}

/**
 * Hace fetch al backend real; si falla (offline / 5xx), devuelve mock.
 * Pensado para que el dashboard sea navegable sin backend corriendo.
 */
export async function apiOrMock<T>(
  path: string,
  mockKey: keyof typeof mock,
  init?: RequestInit,
): Promise<T> {
  try {
    return await api<T>(path, init);
  } catch {
    return mock[mockKey] as unknown as T;
  }
}

export async function ping(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/`, { cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}

export { BASE_URL };
