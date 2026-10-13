import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import HttpRequest from "@/lib/api/http-request";
import { LoginResponse } from "@/schemas/auth";
import {
  clearLocalStorage,
  getFromLocalStorage,
  setOnLocalStorage,
} from "@/lib/utils/local-storage";

export default function useCheckAuthSession() {
  const [isSessionActive, setIsSessionActive] = useState<boolean | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const checkSession = async () => {
      const endpointURL = `${API_URL}/auth/session/check`;
      const request = new HttpRequest(endpointURL);

      const [response, error] = await request.send(LoginResponse);

      if (response) {
        if (!getFromLocalStorage("email")) {
          setOnLocalStorage("email", response.email);
        }
        setIsSessionActive(true);
      }
      if (error) {
        setIsSessionActive(false);
        clearLocalStorage();
        navigate("/login");
      }
    };

    checkSession();
    // `navigate` is stable across renders and intentionally excluded.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSessionActive]);

  return isSessionActive;
}
