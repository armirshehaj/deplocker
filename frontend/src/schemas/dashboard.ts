import * as z from "zod";

export const DashboardMenu = z.enum(["projects", "deployments"]);

export const ProjectCreateRequest = z.object({
  name: z.string().min(1),
  description: z.string().min(1),
});

export const ProjectCreateResponse = z
  .object({
    id: z.uuid(),
    slug: z.string().min(1),
    created_at: z.iso.datetime(),
    updated_at: z.iso.datetime(),
    status: z.literal("created"),
  })
  .extend(ProjectCreateRequest.shape);
