import { describe, it, expect } from "vitest";
import {
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterResponse,
} from "@/schemas/auth";

describe("RegisterRequest", () => {
  const validPayload = {
    username: "john",
    email: "john.doe@gmail.com",
    full_name: "John Doe",
    password: "secret123",
    confirm_password: "secret123",
  };

  it("passes with valid data", async () => {
    await expect(
      RegisterRequest.parseAsync(validPayload),
    ).resolves.toMatchObject(validPayload);
  });

  it("fails when username is empty", async () => {
    await expect(
      RegisterRequest.parseAsync({ ...validPayload, username: "" }),
    ).rejects.toThrow();
  });

  it("fails when email is empty", async () => {
    await expect(
      RegisterRequest.parseAsync({ ...validPayload, email: "" }),
    ).rejects.toThrow();
  });

  it("fails when full_name is empty", async () => {
    await expect(
      RegisterRequest.parseAsync({ ...validPayload, full_name: "" }),
    ).rejects.toThrow();
  });

  it("fails when password is empty", async () => {
    await expect(
      RegisterRequest.parseAsync({ ...validPayload, password: "" }),
    ).rejects.toThrow();
  });

  it("fails when passwords do not match", async () => {
    await expect(
      RegisterRequest.parseAsync({
        ...validPayload,
        confirm_password: "SECRET123",
      }),
    ).rejects.toThrow();
  });
});

describe("RegisterResponse", () => {
  const validResponse = {
    message:
      "Signup request successfully completed! You will shortly recieve a verification request in your email address...",
  };

  it("passes with valid data", async () => {
    await expect(
      RegisterResponse.parseAsync(validResponse),
    ).resolves.toMatchObject(validResponse);
  });

  it("fails with unexpected message", async () => {
    await expect(
      RegisterResponse.parseAsync({
        ...validResponse,
        message: "User successfully registered!",
      }),
    ).rejects.toThrow();
  });
});

describe("LoginRequest", () => {
  it("passes with valid data", async () => {
    await expect(
      LoginRequest.parseAsync({ username: "john", password: "secret" }),
    ).resolves.toMatchObject({ username: "john", password: "secret" });
  });

  it("fails when username is empty", async () => {
    await expect(
      LoginRequest.parseAsync({ username: "", password: "secret" }),
    ).rejects.toThrow();
  });

  it("fails when password is empty", async () => {
    await expect(
      LoginRequest.parseAsync({ username: "john", password: "" }),
    ).rejects.toThrow();
  });

  it("fails when username is missing", async () => {
    await expect(
      LoginRequest.parseAsync({ password: "secret" }),
    ).rejects.toThrow();
  });

  it("fails when password is missing", async () => {
    await expect(
      LoginRequest.parseAsync({ username: "john" }),
    ).rejects.toThrow();
  });
});

describe("LoginResponse", () => {
  const validResponse = {
    user_id: 1,
    email: "john@example.com",
    role: "user",
    created_at: "2024-01-01T00:00:00Z",
  };

  it("passes with valid data", async () => {
    await expect(
      LoginResponse.parseAsync(validResponse),
    ).resolves.toMatchObject(validResponse);
  });

  it("fails when user_id is missing", async () => {
    const { user_id: _, ...rest } = validResponse;
    await expect(LoginResponse.parseAsync(rest)).rejects.toThrow();
  });

  it("fails when email is missing", async () => {
    const { email: _, ...rest } = validResponse;
    await expect(LoginResponse.parseAsync(rest)).rejects.toThrow();
  });

  it("fails when role is missing", async () => {
    const { role: _, ...rest } = validResponse;
    await expect(LoginResponse.parseAsync(rest)).rejects.toThrow();
  });

  it("fails when role is incorrect", async () => {
    await expect(
      LoginResponse.parseAsync({ ...validResponse, role: "invalid-role" }),
    ).rejects.toThrow();
  });

  it("fails when created_at is missing", async () => {
    const { created_at: _, ...rest } = validResponse;
    await expect(LoginResponse.parseAsync(rest)).rejects.toThrow();
  });

  it("strips unknown fields", async () => {
    const result = await LoginResponse.parseAsync({
      ...validResponse,
      extra: "field",
    });
    expect(result).not.toHaveProperty("extra");
  });
});
