import { useEffect, useState } from "react";
import HttpRequest from "../api/http-request";
import * as z from "zod";
import { toast } from "react-toastify";
import { APICallParams } from "../api/types";

// Calls an endpoint once, on mount, and returns its validated response and its
// error, which is also shown as a toast
export default function useAPIOnMount<S extends z.ZodType>(
  endpointURL: string,
  responseSchema: S,
  apiCallParams?: APICallParams,
) {
  const [response, setResponse] = useState<z.infer<S> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const callAPI = async () => {
      const request = new HttpRequest(endpointURL, apiCallParams);
      const [response, error] = await request.send(responseSchema);

      if (response) {
        setResponse(response);
      }

      if (error) {
        setError(error);
        toast.error(error);
      }
    };

    callAPI();
    // Fetches once on mount; the endpoint/schema/params are treated as fixed
    // for the lifetime of the component.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return [response, error] as const;
}
