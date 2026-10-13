import ErrorPage from "@/components/dashboard/sections/ErrorPage";
import { DashboardMenu } from "@/schemas/dashboard";
import React from "react";
import { useParams } from "react-router-dom";
import * as z from "zod";

export const MenuContext = React.createContext<
  [
    z.infer<typeof DashboardMenu>,
    React.Dispatch<React.SetStateAction<z.infer<typeof DashboardMenu>>>,
  ]
>(["projects", () => {}]);

export function MenuContextProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const { menu } = useParams();

  // The URL param alone decides the active menu; an invalid one renders the
  // error page.
  let activeMenu: z.infer<typeof DashboardMenu>;
  try {
    activeMenu = DashboardMenu.parse(menu);
  } catch (error) {
    if (error instanceof z.ZodError) {
      return <ErrorPage />;
    }
    throw error;
  }

  return (
    <MenuContext.Provider value={[activeMenu, () => {}]}>
      {children}
    </MenuContext.Provider>
  );
}
