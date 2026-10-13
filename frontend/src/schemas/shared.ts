import * as z from "zod";

export const SuccessReponse = z.object({
  message: z.string().min(1),
});
