import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/shadcn/dropdown-menu";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "@/components/shadcn/sidebar";
import useAPIOnMount from "@/lib/hooks/api";
import { getFromLocalStorage } from "@/lib/utils/local-storage";
import { OrganizationSummaries } from "@/schemas/organizations";
import { AddPasskeyForm } from "@/components/auth/AddPasskey";
import {
  ChevronsUpDown,
  Fingerprint,
  Folder,
  Power,
  Rocket,
} from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { logoutUser } from "@/lib/utils/auth";

export default function AppSidebar() {
  const { isMobile, setOpenMobile } = useSidebar();
  const navigate = useNavigate();
  const [email] = useState<string | null>(() => {
    return getFromLocalStorage("email");
  });

  const [response] = useAPIOnMount(`${API_URL}/orgs`, OrganizationSummaries);
  const organizations = response ?? [];

  return (
    <Sidebar variant="floating" collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild className="cursor-pointer">
                <SidebarMenuButton size="lg">
                  <img
                    src="/deplocker.png"
                    className="size-8 rounded-md object-contain"
                  />
                  <span className="truncate">{organizations[0]?.name}</span>
                  <ChevronsUpDown className="ml-auto" />
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                side="right"
                align="start"
                className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg"
              >
                {organizations.map((organization) => (
                  <DropdownMenuItem key={organization.id}>
                    <span>{organization.name}</span>
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Home</SidebarGroupLabel>
          <SidebarMenuItem>
            <SidebarMenuButton
              tooltip="Projects"
              onClick={() => {
                if (isMobile) setOpenMobile(false);
                navigate("/dashboard/projects");
              }}
            >
              <Folder />
              <span>Projects</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton
              tooltip="Deployments"
              onClick={() => {
                if (isMobile) setOpenMobile(false);
                navigate("/dashboard/deployments");
              }}
            >
              <Rocket />
              <span>Deployments</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild className="cursor-pointer">
                <SidebarMenuButton size="lg" tooltip={email ?? "Account"}>
                  <span className="relative flex shrink-0 overflow-hidden h-8 w-8 rounded-lg">
                    <span className="flex h-full w-full items-center justify-center bg-[rgb(66,121,53)] rounded-lg text-white">
                      {email?.[0].toUpperCase()}
                    </span>
                  </span>
                  <div className="grid flex-1 text-left leading-tight">
                    <span className="truncate font-semibold">Account</span>
                    <span className="truncate text-sm">{email}</span>
                  </div>
                  <ChevronsUpDown className="ml-auto" />
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                side="right"
                align="end"
                className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg"
              >
                <AddPasskeyForm>
                  {/* Closing the menu on select would unmount the dialog before it opens. */}
                  <DropdownMenuItem
                    className="cursor-pointer"
                    onSelect={(event) => event.preventDefault()}
                  >
                    <Fingerprint />
                    <span>Add a passkey</span>
                  </DropdownMenuItem>
                </AddPasskeyForm>
                <DropdownMenuItem
                  className="cursor-pointer"
                  onClick={() => logoutUser(navigate)}
                >
                  <Power color="red" />
                  <span>Logout</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
