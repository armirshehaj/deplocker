import * as z from "zod";
import {
  ConfirmationPendingError,
  LoginRequest,
  LoginResponse,
  LogoutResponse,
  PasskeyAuthenticationOptions,
  PasskeyRegistrationOptions,
  PasskeyResponse,
} from "@/schemas/auth";
import { setOnLocalStorage } from "./local-storage";
import { toast } from "react-toastify";
import { NavigateFunction } from "react-router-dom";
import HttpRequest from "@/lib/api/http-request";
import {
  startAuthentication,
  startRegistration,
} from "@simplewebauthn/browser";

export async function submitDeplockerLogin(
  data: z.infer<typeof LoginRequest>,
  navigate: NavigateFunction,
): Promise<void> {
  const formData = new FormData();
  formData.append("username", data.username);
  formData.append("password", data.password);

  const request = new HttpRequest(`${API_URL}/auth/login`, {
    body: formData,
  });
  const [response, error, errorBody] = await request.send(LoginResponse);

  if (response) {
    setOnLocalStorage("email", response.email);
    navigate("/dashboard/projects");
  }

  const pending = ConfirmationPendingError.safeParse(errorBody);
  if (pending.success) {
    navigate(
      `/account/pending?email=${encodeURIComponent(pending.data.email)}`,
    );
    return;
  }

  if (error) {
    toast.error(error);
  }
}

// Dismissing the browser's passkey prompt is a choice, not a failure to report.
function reportCeremonyError(error: unknown): void {
  if (error instanceof Error && error.name !== "NotAllowedError") {
    toast.error(`The passkey prompt failed: ${error.message}`);
  }
}

export async function submitPasskeyLogin(
  navigate: NavigateFunction,
): Promise<void> {
  let request = new HttpRequest(`${API_URL}/auth/passkeys/login/options`);
  const [options, optionsError] = await request.send(
    PasskeyAuthenticationOptions,
  );

  if (!options) {
    toast.error(optionsError);
    return;
  }

  let authenticationCredential;
  try {
    authenticationCredential = await startAuthentication({
      optionsJSON: options,
    });
  } catch (error) {
    // WebAuthn deliberately reports cancel, timeout, failed verification and "no passkey here" all as NotAllowedError.
    if (error instanceof Error && error.name === "NotAllowedError") {
      toast.info(
        "Passkey sign-in didn't complete.\nIf you do not have a passkey registered, sign in another way, then add one from the sidebar.",
        { style: { whiteSpace: "pre-line" } },
      );
    }
    reportCeremonyError(error);
    return;
  }

  request = new HttpRequest(`${API_URL}/auth/passkeys/login`, {
    body: { credential: authenticationCredential },
  });
  const [response, error] = await request.send(LoginResponse);

  if (response) {
    setOnLocalStorage("email", response.email);
    navigate("/dashboard/projects");
  }

  if (error) {
    toast.error(error);
  }
}

export async function enrolPasskey(name: string): Promise<void> {
  let request = new HttpRequest(`${API_URL}/auth/passkeys/register/options`);
  const [options, optionsError] = await request.send(
    PasskeyRegistrationOptions,
  );

  if (!options) {
    toast.error(optionsError);
    return;
  }

  let registrationCredential;
  try {
    registrationCredential = await startRegistration({ optionsJSON: options });
  } catch (error) {
    reportCeremonyError(error);
    return;
  }

  request = new HttpRequest(`${API_URL}/auth/passkeys/register`, {
    body: { name, credential: registrationCredential },
  });
  const [response, error] = await request.send(PasskeyResponse);

  if (response) {
    toast.success(`'${response.name}' can now sign you in to Deplocker.`);
  }

  if (error) {
    toast.error(error);
  }
}

export async function logoutUser(navigate: NavigateFunction): Promise<void> {
  localStorage.clear();

  const request = new HttpRequest(`${API_URL}/auth/logout`);
  const [response, error] = await request.send(LogoutResponse);

  if (response) {
    navigate("/login");
  }

  if (error) {
    toast.error(error);
  }
}
