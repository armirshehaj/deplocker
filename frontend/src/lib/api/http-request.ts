import { toast } from "react-toastify";
import { resolveEndpointConfig } from "./endpoints-map";
import { networkErrorToasterMessage } from "@/globals";
import { APICallParams, RequestParams } from "./types";
import * as z from "zod";

// The third element is a failed response's body, for callers that read fields beyond `detail`
export type APICallResult<T> = [T | null, string | null, unknown?];

export default class HttpRequest {
  endpointURL: string;
  apiCallParams?: APICallParams;

  constructor(endpointURL: string, apiCallParams?: APICallParams) {
    this.endpointURL = endpointURL;
    this.apiCallParams = apiCallParams;
  }

  async send<S extends z.ZodType>(
    schema?: S,
  ): Promise<APICallResult<z.infer<S>>> {
    let endpointConfig: RequestParams;

    try {
      endpointConfig = resolveEndpointConfig(this.endpointURL);
    } catch (error) {
      const errorMessage = String(error);
      return [null, errorMessage];
    }

    const init: RequestInit = {
      method: endpointConfig.method,
      credentials: endpointConfig.public ? "same-origin" : "include",
    };

    if (endpointConfig.headers) {
      init.headers = endpointConfig.headers;
    }

    const requestPayload = this.apiCallParams?.body;
    if (requestPayload) {
      if (requestPayload instanceof FormData) init.body = requestPayload;
      else if (requestPayload instanceof Object)
        init.body = JSON.stringify(requestPayload);
    }

    try {
      const response = await fetch(this.endpointURL, init);

      const contentType = response.headers.get("content-type");
      if (!contentType?.includes("application/json")) {
        const url = this.endpointURL.split("?")[0];
        throw new Error(
          `${url} answered HTTP ${response.status} with ${contentType ?? "no content type"} instead of JSON`,
        );
      }

      const data = await response.json();

      if (!response.ok) {
        const serverErrorDetail = data.detail;
        return [null, serverErrorDetail, data];
      }

      if (schema) {
        try {
          const validated = await schema.parseAsync(data);
          return [validated, null];
        } catch (error) {
          if (error instanceof z.ZodError) {
            return [null, `Invalid response shape: ${z.prettifyError(error)}`];
          }
          throw error;
        }
      }

      return [data, null];
    } catch (error) {
      let errorMessage: string;

      if (error instanceof TypeError) {
        errorMessage = networkErrorToasterMessage;
      } else if (error instanceof Error) {
        errorMessage = `An unexpected error ocurred: ${error.message}`;
      } else {
        errorMessage = `An unexpected error ocurred: ${error}`;
      }

      // A message already on screen is not shown again
      toast.error(errorMessage, { toastId: errorMessage });
      return [null, errorMessage];
    }
  }
}
