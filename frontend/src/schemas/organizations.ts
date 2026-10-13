import * as z from "zod";

export const OrganizationSummary = z.object({
  id: z.uuid(),
  name: z.string().min(1),
  slug: z.string().min(1),
});

export const OrganizationSummaries = z.array(OrganizationSummary);
