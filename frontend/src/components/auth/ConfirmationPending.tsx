import * as z from "zod";
import { Loader2, MailCheck } from "lucide-react";
import { useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "react-toastify";
import { Button } from "../shadcn/button";
import { Input } from "../shadcn/input";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "../shadcn/field";
import HttpRequest from "@/lib/api/http-request";
import {
  EmailChangeRequest,
  EmailChangeResponse,
  ResendConfirmationResponse,
} from "@/schemas/auth";

export function ConfirmationPending() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const [resending, setResending] = useState(false);
  const [changingEmail, setChangingEmail] = useState(false);

  const form = useForm<z.infer<typeof EmailChangeRequest>>({
    resolver: zodResolver(EmailChangeRequest),
    defaultValues: { email: "", password: "" },
  });

  const email = searchParams.get("email");
  if (!email) {
    return <Navigate to="/register" replace />;
  }

  const resendConfirmationEmail = async () => {
    setResending(true);
    const request = new HttpRequest(
      `${API_URL}/auth/account/confirm/retry?email=${encodeURIComponent(email)}`,
    );
    const [response, error] = await request.send(ResendConfirmationResponse);
    setResending(false);

    if (response) {
      toast.success(response.message);
    }

    if (error) {
      toast.error(error);
    }
  };

  const changeEmail = async (data: z.infer<typeof EmailChangeRequest>) => {
    const request = new HttpRequest(`${API_URL}/auth/account/email`, {
      body: { identifier: email, password: data.password, email: data.email },
    });
    const [response, error] = await request.send(EmailChangeResponse);

    if (response) {
      setSearchParams({ email: response.email }, { replace: true });
      setChangingEmail(false);
      form.reset();
      toast.success(response.message);
    }

    if (error) {
      toast.error(error);
    }
  };

  const cancelEmailChange = () => {
    setChangingEmail(false);
    form.reset();
  };

  return (
    <div className="flex flex-col min-h-screen items-center gap-12 mb-8">
      <img
        src="/deplocker.png"
        alt="Deplocker"
        width="200px"
        height="200px"
      ></img>
      <div className="flex flex-col items-center gap-4 w-full max-w-sm px-8 text-center md:px-0">
        <MailCheck className="size-12 text-green-500" />
        <div role="status" className="flex flex-col gap-2">
          <h1 className="text-2xl font-bold">Confirm your email</h1>
          <p className="text-muted-foreground">
            We sent a confirmation link to{" "}
            <span className="font-medium text-foreground">{email}</span>.
          </p>
          <p className="text-sm text-muted-foreground">
            Confirm within 24 hours of signing up. After that, the account is
            removed, and you can sign up again.
          </p>
        </div>

        {changingEmail ? (
          <form
            className="w-full mt-4 text-left"
            onSubmit={form.handleSubmit(changeEmail)}
          >
            <FieldGroup>
              <Controller
                name="email"
                control={form.control}
                render={({ field, fieldState }) => (
                  <Field>
                    <FieldLabel htmlFor="new-email">
                      Correct email address
                    </FieldLabel>
                    <Input {...field} id="new-email" type="email" required />
                    {fieldState.invalid && (
                      <FieldError
                        errors={[{ message: fieldState.error?.message }]}
                      />
                    )}
                  </Field>
                )}
              />
              <Controller
                name="password"
                control={form.control}
                render={({ field, fieldState }) => (
                  <Field>
                    <FieldLabel htmlFor="password">Password</FieldLabel>
                    <Input {...field} id="password" type="password" required />
                    {fieldState.invalid ? (
                      <FieldError
                        errors={[{ message: fieldState.error?.message }]}
                      />
                    ) : (
                      <FieldDescription>
                        The one you signed up with. It shows the account is
                        yours.
                      </FieldDescription>
                    )}
                  </Field>
                )}
              />
              <Field>
                <Button
                  type="submit"
                  className="cursor-pointer"
                  disabled={form.formState.isSubmitting}
                >
                  {form.formState.isSubmitting && (
                    <Loader2 className="animate-spin" />
                  )}
                  Send the link there
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="cursor-pointer"
                  onClick={cancelEmailChange}
                >
                  Cancel
                </Button>
              </Field>
            </FieldGroup>
          </form>
        ) : (
          <div className="flex flex-col w-full gap-2 mt-4">
            <Button
              className="cursor-pointer"
              disabled={resending}
              onClick={resendConfirmationEmail}
            >
              {resending && <Loader2 className="animate-spin" />}
              Resend confirmation email
            </Button>
            <Button
              variant="outline"
              className="cursor-pointer"
              onClick={() => setChangingEmail(true)}
            >
              Wrong address? Change it
            </Button>
            <Button
              variant="link"
              className="cursor-pointer"
              onClick={() => navigate("/login")}
            >
              Go to sign in
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
