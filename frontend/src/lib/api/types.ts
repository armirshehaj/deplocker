export type RequestMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

type RequestBody = object | FormData;

export interface APICallParams {
  body?: RequestBody;
  public?: boolean;
  headers?: HeadersInit;
}

export interface RequestParams extends APICallParams {
  method: RequestMethod;
}
