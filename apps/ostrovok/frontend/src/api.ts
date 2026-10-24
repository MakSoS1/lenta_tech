import type { Capabilities, HistoryItem, TripState } from "./types";
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...options,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch (problem) {
    if (problem instanceof DOMException && problem.name === "AbortError")
      throw problem;
    throw new ApiError(
      0,
      "Не удалось связаться с агентом. Проверьте подключение и попробуйте снова.",
    );
  }
  let data;
  try {
    data = await response.json();
  } catch {
    throw new ApiError(
      response.status,
      "Агент временно недоступен. Попробуйте снова или обновите страницу.",
    );
  }
  if (!response.ok)
    throw new ApiError(
      response.status,
      typeof data.detail === "string"
        ? data.detail
        : "Проверьте введённые условия и попробуйте снова.",
    );
  return data as T;
}
export const api = {
  capabilities: () => request<Capabilities>("/api/capabilities"),
  history: () => request<{ trips: HistoryItem[] }>("/api/trips"),
  trip: (id: string, signal?: AbortSignal) =>
    request<TripState>(`/api/trips/${encodeURIComponent(id)}`, { signal }),
  create: (message: string, signal?: AbortSignal) =>
    request<TripState>("/api/trips", {
      method: "POST",
      body: JSON.stringify({ message }),
      signal,
    }),
  mutate: (
    id: string,
    path: string,
    body: unknown,
    signal?: AbortSignal,
    headers?: Record<string, string>,
  ) =>
    request<TripState>(`/api/trips/${encodeURIComponent(id)}/${path}`, {
      method: "POST",
      body: JSON.stringify(body),
      signal,
      headers,
    }),
  preferences: () =>
    request<{ preferences: Record<string, unknown> }>("/api/preferences"),
  savePreferences: (preferences: Record<string, unknown>) =>
    request<{ preferences: Record<string, unknown> }>("/api/preferences", {
      method: "PUT",
      body: JSON.stringify({ preferences }),
    }),
  deletePreferences: () =>
    request<{ preferences: Record<string, unknown> }>("/api/preferences", {
      method: "DELETE",
    }),
  service: (id: string) =>
    request<{ request_id: string; status: string; message: string }>(
      `/api/trips/${encodeURIComponent(id)}/service-requests`,
      {
        method: "POST",
        body: JSON.stringify({
          kind: "early_checkin",
          message: "Прошу уточнить возможность раннего заселения.",
        }),
      },
    ),
};
