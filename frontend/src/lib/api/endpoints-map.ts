import { RequestParams } from "./types";

const jsonPayloadHeader = {
  "Content-Type": "application/json",
};

export const parameterLessEndpoints: Record<string, RequestParams> = {
  [`${API_URL}/auth/register`]: {
    method: "POST",
    public: true,
    headers: {
      ...jsonPayloadHeader,
    },
  },
  [`${API_URL}/auth/login`]: {
    method: "POST",
  },
  [`${API_URL}/auth/account/email`]: {
    method: "POST",
    public: true,
    headers: {
      ...jsonPayloadHeader,
    },
  },
  [`${API_URL}/auth/passkeys/login/options`]: {
    method: "POST",
  },
  [`${API_URL}/auth/passkeys/login`]: {
    method: "POST",
    headers: {
      ...jsonPayloadHeader,
    },
  },
  [`${API_URL}/auth/passkeys/register/options`]: {
    method: "POST",
  },
  [`${API_URL}/auth/passkeys/register`]: {
    method: "POST",
    headers: {
      ...jsonPayloadHeader,
    },
  },
  [`${API_URL}/health`]: {
    method: "GET",
    public: true,
  },
  [`${API_URL}/auth/session/check`]: {
    method: "GET",
  },
  [`${API_URL}/projects/create`]: {
    method: "GET",
    headers: {
      ...jsonPayloadHeader,
    },
  },
  [`${API_URL}/orgs`]: {
    method: "GET",
  },
};

export const parameteredEndpoints: Record<string, RequestParams> = {
  [`${API_URL}/auth/check-username?username=:username`]: {
    method: "GET",
    public: true,
  },
  [`${API_URL}/auth/account/confirm?email=:email&token=:token`]: {
    method: "POST",
    public: true,
  },
  [`${API_URL}/auth/account/confirm/retry?email=:email`]: {
    method: "POST",
    public: true,
  },
  [`${API_URL}/auth/logout`]: {
    method: "POST",
  },
};

export function resolveEndpointConfig(url: string): RequestParams {
  if (parameterLessEndpoints[url]) return parameterLessEndpoints[url];

  for (const [pattern, config] of Object.entries(parameteredEndpoints)) {
    const relativePattern = pattern.replace(API_URL, "");

    // Each :param matches one path segment; the query string's `?` matches literally
    const regex = new RegExp(
      relativePattern.replace(/:\w+/g, "[^/]+").replace("?", "\\?"),
    );

    if (regex.test(url)) return config;
  }

  throw new Error(`Configuration not found for the endpoint: ${url}`);
}
