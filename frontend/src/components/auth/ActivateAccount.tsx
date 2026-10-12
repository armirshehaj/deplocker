import { CheckCircle, Loader2, MailCheck, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { Button } from "../shadcn/button";
import HttpRequest from "@/lib/api/http-request";
import { SuccessReponse } from "@/schemas/shared";
import { ResendConfirmationResponse } from "@/schemas/auth";

type ConfirmationStatus =
  "confirming" | "confirmed" | "failed" | "resending" | "resent";

export function ActivateAccount() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<ConfirmationStatus>("confirming");

  const email = searchParams.get("email");
  const token = searchParams.get("token");

  useEffect(() => {
    const confirmAccount = async () => {
      if (!email || !token) {
        setStatus("failed");
        return;
      }

      const endpointURL = `${API_URL}/auth/account/confirm?email=${email}&token=${token}`;
      const request = new HttpRequest(endpointURL);

      const [result, error] = await request.send(SuccessReponse);
      if (result) {
        setStatus("confirmed");
      }
      if (error) {
        console.error(error);
        setStatus("failed");
      }
    };

    confirmAccount();
    // Runs once on mount to confirm the account from the URL params.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const resendConfirmationEmail = async () => {
    setStatus("resending");
    const endpointURL = `${API_URL}/auth/account/confirm/retry?email=${email}`;
    const request = new HttpRequest(endpointURL);
    const [response, error] = await request.send(ResendConfirmationResponse);

    if (response) {
      setStatus("resent");
    }

    if (error) {
      toast.error(error);
      setStatus("failed");
    }
  };

  const failedContent = {
    icon: <XCircle className="size-12 text-red-500" />,
    title: "Confirmation failed",
    description: "This confirmation link is invalid or has expired.",
  };

  const content = {
    confirming: {
      icon: <Loader2 className="size-12 animate-spin text-muted-foreground" />,
      title: "Confirming your email",
      description: "This only takes a moment.",
    },
    confirmed: {
      icon: <CheckCircle className="size-12 text-green-500" />,
      title: "Email confirmed",
      description: "Your account is active. You can now sign in to Deplocker.",
    },
    failed: failedContent,
    resending: failedContent,
    resent: {
      icon: <MailCheck className="size-12 text-green-500" />,
      title: "Check your inbox",
      description: `A new confirmation link is on its way to ${email}.`,
    },
  }[status];

  const goToLogin = () => navigate("/login");

  return (
    <div className="flex flex-col h-screen items-center gap-12">
      <img
        src="/deplocker.png"
        alt="Deplocker"
        width="200px"
        height="200px"
      ></img>
      <div className="flex flex-col items-center gap-4 w-full max-w-sm px-8 text-center md:px-0">
        {content.icon}
        <div role="status" className="flex flex-col gap-2">
          <h1 className="text-2xl font-bold">{content.title}</h1>
          <p className="text-muted-foreground">{content.description}</p>
        </div>

        <div className="flex flex-col w-full gap-2 mt-4">
          {status === "confirmed" && (
            <Button className="cursor-pointer" onClick={goToLogin}>
              Sign in
            </Button>
          )}

          {(status === "failed" || status === "resending") && email && (
            <Button
              className="cursor-pointer"
              disabled={status === "resending"}
              onClick={resendConfirmationEmail}
            >
              {status === "resending" && <Loader2 className="animate-spin" />}
              Resend confirmation email
            </Button>
          )}

          {(status === "failed" ||
            status === "resending" ||
            status === "resent") && (
            <Button
              variant="link"
              className="cursor-pointer"
              onClick={goToLogin}
            >
              Go to sign in
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
