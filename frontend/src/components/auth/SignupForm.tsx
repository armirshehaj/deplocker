import * as z from "zod";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/shadcn/card";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/shadcn/field";
import { Input } from "@/components/shadcn/input";
import { useForm, Controller } from "react-hook-form";
import {
  RegisterRequest,
  RegisterResponse,
  UsernameAvailabilty,
} from "@/schemas/auth";
import { zodResolver } from "@hookform/resolvers/zod";
import HttpRequest from "@/lib/api/http-request";
import { toast } from "react-toastify";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../shadcn/button";
import GoogleIcon from "@/lib/icons/GoogleIcon";
import { Eye, EyeOff } from "lucide-react";

export function SignupForm({ ...props }: React.ComponentProps<typeof Card>) {
  const navigate = useNavigate();
  const [usernameAvailable, setUsernameAvailable] = useState<boolean | null>(
    null,
  );
  const [showPassword, setShowPassword] = useState(false);

  const form = useForm<z.infer<typeof RegisterRequest>>({
    resolver: zodResolver(RegisterRequest),
    defaultValues: {
      username: "",
      email: "",
      full_name: "",
      password: "",
      confirm_password: "",
    },
  });

  // react-hook-form's watch() cannot be memoized by the React Compiler; this is
  // the documented way to observe a field value.
  // eslint-disable-next-line react-hooks/incompatible-library
  const username = form.watch("username");

  useEffect(() => {
    setUsernameAvailable(null);
    if (!username || username.length < 3) return;
    const timer = setTimeout(async () => {
      const request = new HttpRequest(
        `${API_URL}/auth/check-username?username=${username}`,
      );
      const [result, error] = await request.send(UsernameAvailabilty);
      if (result) {
        setUsernameAvailable(result.available);
      }

      if (error) {
        toast.error(error);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [username]);

  const onToggglePasswordVisibility = () => {
    setShowPassword((prevState) => !prevState);
  };

  const onSubmit = async (data: z.infer<typeof RegisterRequest>) => {
    const endpointURL = `${API_URL}/auth/register`;

    // Checked client-side only; the register endpoint doesn't take it
    delete data["confirm_password"];

    const request = new HttpRequest(endpointURL, {
      body: data,
    });

    const [response, error] = await request.send(RegisterResponse);
    if (response) {
      navigate(`/account/pending?email=${encodeURIComponent(data.email)}`);
    }

    if (error) {
      toast.error(error);
    }
  };

  return (
    <div className="flex flex-col items-center m-8 text-base gap-12">
      <div className="flex flex-col items-center">
        <img src="/deplocker.png" width="200px" height="200px"></img>
        <h1 className="text-2xl font-bold">Sign up for Deplocker</h1>
      </div>
      <Card {...props} className="w-full md:w-[35%]">
        <CardHeader>
          <CardTitle>Create an account</CardTitle>
          <CardDescription>
            Enter your information below to create your account
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <FieldGroup>
              <Controller
                name="username"
                control={form.control}
                render={({ field, fieldState }) => (
                  <Field>
                    <FieldLabel htmlFor="username">Username</FieldLabel>
                    <Input
                      {...field}
                      id="username"
                      type="text"
                      placeholder="john.doe"
                      required
                    />
                    {fieldState.invalid && (
                      <FieldError
                        errors={[{ message: fieldState.error?.message }]}
                      />
                    )}
                    {username &&
                      username.length > 2 &&
                      usernameAvailable != null &&
                      (usernameAvailable === false ? (
                        <FieldError
                          errors={[
                            { message: `${username} is already taken.` },
                          ]}
                        />
                      ) : (
                        <FieldDescription className="text-green-600">
                          {username} is available ✓
                        </FieldDescription>
                      ))}
                  </Field>
                )}
              />
              <Controller
                name="email"
                control={form.control}
                render={({ field, fieldState }) => (
                  <Field>
                    <FieldLabel htmlFor="email">Email</FieldLabel>
                    <Input
                      {...field}
                      id="email"
                      type="email"
                      placeholder="m@example.com"
                      required
                    />
                    {fieldState.invalid ? (
                      <FieldError
                        errors={[{ message: fieldState.error?.message }]}
                      />
                    ) : (
                      <FieldDescription>
                        We&apos;ll use this to contact you. We will not share
                        your email with anyone else.
                      </FieldDescription>
                    )}
                  </Field>
                )}
              />
              <Controller
                name="full_name"
                control={form.control}
                render={({ field, fieldState }) => (
                  <Field>
                    <FieldLabel htmlFor="full-name">Full Name</FieldLabel>
                    <Input
                      {...field}
                      id="full-name"
                      type="text"
                      placeholder="John Doe"
                      required
                    />
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
                    <div className="relative">
                      <Input
                        {...field}
                        id="password"
                        type={showPassword ? "text" : "password"}
                        className="pr-9"
                        required
                      />
                      <button
                        type="button"
                        onClick={onToggglePasswordVisibility}
                        aria-label={
                          showPassword ? "Hide password" : "Show password"
                        }
                        className="absolute inset-y-0 right-0 flex items-center pr-3 text-muted-foreground hover:text-foreground cursor-pointer"
                      >
                        {showPassword ? (
                          <EyeOff className="size-4" />
                        ) : (
                          <Eye className="size-4" />
                        )}
                      </button>
                    </div>
                    {fieldState.invalid ? (
                      <FieldError
                        errors={[{ message: fieldState.error?.message }]}
                      />
                    ) : (
                      <FieldDescription>
                        Must be at least 8 characters long.
                      </FieldDescription>
                    )}
                  </Field>
                )}
              />
              <Controller
                name="confirm_password"
                control={form.control}
                render={({ field, fieldState }) => (
                  <Field>
                    <FieldLabel htmlFor="confirm-password">
                      Confirm Password
                    </FieldLabel>
                    <div className="relative">
                      <Input
                        {...field}
                        id="confirm-password"
                        type={showPassword ? "text" : "password"}
                        className="pr-9"
                        required
                      />
                      <button
                        type="button"
                        onClick={onToggglePasswordVisibility}
                        aria-label={
                          showPassword ? "Hide password" : "Show password"
                        }
                        className="absolute inset-y-0 right-0 flex items-center pr-3 text-muted-foreground hover:text-foreground cursor-pointer"
                      >
                        {showPassword ? (
                          <EyeOff className="size-4" />
                        ) : (
                          <Eye className="size-4" />
                        )}
                      </button>
                    </div>
                    {fieldState.invalid ? (
                      <FieldError
                        errors={[{ message: fieldState.error?.message }]}
                      />
                    ) : (
                      <FieldDescription>
                        Please confirm your password.
                      </FieldDescription>
                    )}
                  </Field>
                )}
              />
              <FieldGroup>
                <Field>
                  <Button type="submit" className="cursor-pointer">
                    Create Account
                  </Button>
                  <Button
                    variant="outline"
                    type="button"
                    className="cursor-pointer"
                  >
                    <GoogleIcon /> Sign up with Google
                  </Button>
                  <FieldDescription className="px-6 text-center">
                    Already have an account?{" "}
                    <a href="/login" className="hover:text-blue-500!">
                      Sign in
                    </a>
                  </FieldDescription>
                </Field>
              </FieldGroup>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
