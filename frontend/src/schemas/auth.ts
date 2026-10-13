import * as z from "zod";

export const UsernameAvailabilty = z.object({
  available: z.boolean(),
});

export const RegisterRequest = z
  .object({
    username: z
      .string()
      .min(2, "Username must be at least 2 characters.")
      .optional(),
    email: z.email("Please, provide a valid email address."),
    full_name: z.string().min(1),
    password: z
      .string()
      .min(8, "Password must be at least 8 characters long.")
      .optional(),
    confirm_password: z.string().optional(),
  })
  .refine((values) => values.confirm_password === values.password, {
    error: "Passwords do not match!",
    path: ["confirm_password"],
  });

export const RegisterResponse = z.object({
  message: z.literal(
    "Signup request successfully completed! You will shortly recieve a verification request in your email address...",
  ),
});

export const ResendConfirmationResponse = z.object({
  message: z.string().min(1),
});

// The login's answer for an account awaiting confirmation
export const ConfirmationPendingError = z.object({
  detail: z.string().min(1),
  email: z.email(),
});

export const EmailChangeRequest = z.object({
  email: z.email("Please, provide a valid email address."),
  password: z.string().min(1, "Enter the password you signed up with."),
});

export const EmailChangeResponse = z.object({
  message: z.string().min(1),
  email: z.email(),
});

export const LoginRequest = z.object({
  username: z.string().min(1),
  password: z.string().min(1),
});

export const LoginResponse = z.object({
  user_id: z.number().int(),
  email: z.email(),
  role: z.enum(["admin", "user"]),
  created_at: z.string().min(1),
});

export const LogoutResponse = z.object({
  message: z.literal("User successfully logged out!"),
});

export const PasskeyResponse = z.object({
  id: z.uuid(),
  name: z.string().min(1),
  created_at: z.string().min(1),
  last_used_at: z.string().nullable(),
});

export const PasskeyRegisterRequest = z.object({
  name: z.string().min(1, "Give the passkey a name you recognise.").max(255),
});

const PasskeyCredentialDescriptor = z.object({
  id: z.string().min(1),
  type: z.string().min(1),
  transports: z.array(z.string().min(1)).optional(),
});

export const PasskeyRegistrationOptions = z.object({
  rp: z.object({
    name: z.string().min(1),
    id: z.string().optional(),
  }),
  user: z.object({
    id: z.string().min(1),
    name: z.string().min(1),
    displayName: z.string().min(1),
  }),
  challenge: z.string().min(1),
  pubKeyCredParams: z.array(
    z.object({
      type: z.enum(["public-key"]),
      alg: z.number(),
    }),
  ),
  timeout: z.number().optional(),
  excludeCredentials: z.array(PasskeyCredentialDescriptor).optional(),
  authenticatorSelection: z
    .object({
      authenticatorAttachment: z
        .enum(["cross-platform", "platform"])
        .optional(),
      requireResidentKey: z.boolean().optional(),
      residentKey: z.enum(["discouraged", "preferred", "required"]).optional(),
      userVerification: z
        .enum(["discouraged", "preferred", "required"])
        .optional(),
    })
    .optional(),
  attestation: z.enum(["direct", "enterprise", "indirect", "none"]).optional(),
  hints: z
    .array(z.enum(["hybrid", "security-key", "client-device"]))
    .optional(),
});

export const PasskeyAuthenticationOptions = z.object({
  challenge: z.string().min(1),
  timeout: z.number().optional(),
  rpId: z.string().optional(),
  allowCredentials: z.array(PasskeyCredentialDescriptor).optional(),
  userVerification: z.enum(["discouraged", "preferred", "required"]).optional(),
});
