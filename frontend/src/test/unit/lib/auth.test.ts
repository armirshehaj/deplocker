import { describe, it, expect, vi, beforeEach } from "vitest";

const mockSend = vi.hoisted(() => vi.fn());
const mockToastError = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/http-request", () => ({
  default: class MockHttpRequest {
    send = mockSend;
  },
}));

vi.mock("react-toastify", () => ({
  toast: { error: mockToastError },
}));

import { submitDeplockerLogin } from "@/lib/utils/auth";

const credentials = { username: "john", password: "secret123" };

describe("submitDeplockerLogin", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("sends an account awaiting confirmation to its pending page", async () => {
    const navigate = vi.fn();
    mockSend.mockResolvedValue([
      null,
      "Your account is not confirmed yet.",
      {
        detail: "Your account is not confirmed yet.",
        email: "john+deplocker@example.com",
      },
    ]);

    await submitDeplockerLogin(credentials, navigate);

    expect(navigate).toHaveBeenCalledWith(
      "/account/pending?email=john%2Bdeplocker%40example.com",
    );
    expect(mockToastError).not.toHaveBeenCalled();
  });

  it("reports any other failure", async () => {
    const navigate = vi.fn();
    mockSend.mockResolvedValue([
      null,
      "Incorrect credentials were provided.",
      { detail: "Incorrect credentials were provided." },
    ]);

    await submitDeplockerLogin(credentials, navigate);

    expect(navigate).not.toHaveBeenCalled();
    expect(mockToastError).toHaveBeenCalledWith(
      "Incorrect credentials were provided.",
    );
  });
});
