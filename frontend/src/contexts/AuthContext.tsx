import useCheckAuthSession from "@/lib/hooks/auth-session";
import { Loader2 } from "lucide-react";
import React from "react";

export const AuthContext = React.createContext<boolean | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const isSessionActive = useCheckAuthSession();

  // Protected pages render only for a confirmed session
  if (!isSessionActive) {
    return (
      <div className="flex justify-center items-center h-screen">
        <Loader2 className="animate-spin" />
      </div>
    );
  }

  return (
    <AuthContext.Provider value={isSessionActive}>
      {children}
    </AuthContext.Provider>
  );
}
