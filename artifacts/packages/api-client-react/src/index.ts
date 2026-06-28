// Typed API client for the ASSISTRAN backend.
//
// This module mirrors the shape of an OpenAPI-codegen output: the request /
// response types are derived from openapi.yaml and `useTranslate` is a
// TanStack Query mutation hook. Consumers call it exactly like a generated
// hook:
//
//   const translate = useTranslate();
//   translate.mutate({ data: { text, source, target } });
//   // onSuccess(data) -> data.translation is the string

export type { UseMutationResult } from "@tanstack/react-query";

export interface TranslateRequest {
  text: string;
  source: string;
  target: string;
}

export interface TranslateResponse {
  translation: string;
}

export interface TranslateMutationVariables {
  data: TranslateRequest;
}

/**
 * Base URL for the API. Relative by default so the proxy can route /api to the
 * Express server and / to the Vite frontend. Never hardcode a port.
 */
const API_BASE = "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function translate({ data }: TranslateMutationVariables): Promise<TranslateResponse> {
  const res = await fetch(`${API_BASE}/translate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });

  if (!res.ok) {
    let message = `Request failed with status ${res.status}`;
    try {
      const body = (await res.json()) as { error?: string };
      if (body?.error) message = body.error;
    } catch {
      // body was not JSON — keep the default message
    }
    throw new ApiError(res.status, message);
  }

  return (await res.json()) as TranslateResponse;
}

export { useTranslate } from "./useTranslate";
