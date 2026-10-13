import { DashboardMenu } from "@/schemas/dashboard";
import { FolderInput, Rocket } from "lucide-react";
import * as z from "zod";
import { ProjectCreateForm } from "../menus/Projects";

export interface MainHeaderProps {
  titleIcon: React.ReactNode;
  title: string;
  subtitle: string;
  actionButton?: React.ReactNode;
}

export const menus: Record<z.infer<typeof DashboardMenu>, MainHeaderProps> = {
  projects: {
    titleIcon: <FolderInput />,
    title: "Projects",
    subtitle: "Create and manage your projects",
    actionButton: <ProjectCreateForm />,
  },

  deployments: {
    titleIcon: <Rocket />,
    title: "Deployments",
    subtitle: "All application and compose deployments in one place.",
  },
};
