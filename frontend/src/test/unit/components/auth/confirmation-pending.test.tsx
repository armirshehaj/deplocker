import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

const mockRequest = vi.hoisted(() => vi.fn());
const mockSend = vi.hoisted(() => vi.fn());
const mockToastError = vi.hoisted(() => vi.fn());
const mockToastSuccess = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/http-request", () => ({
  default: class MockHttpRequest {
    constructor(...args: unknown[]) {
      mockRequest(...args);
    }
    send = mockSend;
  },
}));

vi.mock("react-toastify", () => ({
  toast: { error: mockToastError, success: mockToastSuccess },
}));

import { ConfirmationPending } from "@/components/auth/ConfirmationPending";

function renderPage(query = "?email=jhon%2Bdeplocker%40example.com") {
  render(
    <MemoryRouter initialEntries={[`/account/pending${query}`]}>
      <Routes>
        <Route path="/account/pending" element={<ConfirmationPending />} />
        <Route path="/register" element={<p>Signup page</p>} />
        <Route path="/login" element={<p>Login page</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

async function submitEmailChange() {
  fireEvent.click(
    screen.getByRole("button", { name: "Wrong address? Change it" }),
  );
  fireEvent.change(screen.getByLabelText("Correct email address"), {
    target: { value: "john+deplocker@example.com" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "secret123" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Send the link there" }));
}

describe("ConfirmationPending", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows the address the link went to", () => {
    renderPage();

    expect(
      screen.getByRole("heading", { name: "Confirm your email" }),
    ).toBeInTheDocument();
    expect(screen.getByText("jhon+deplocker@example.com")).toBeInTheDocument();
  });

  it("sends the page to signup without an address", () => {
    renderPage("");

    expect(screen.getByText("Signup page")).toBeInTheDocument();
  });

  it("resends the link to the address", async () => {
    mockSend.mockResolvedValue([{ message: "Sent" }, null]);
    renderPage();

    fireEvent.click(
      screen.getByRole("button", { name: "Resend confirmation email" }),
    );

    await waitFor(() => expect(mockToastSuccess).toHaveBeenCalledWith("Sent"));
    expect(mockRequest).toHaveBeenCalledWith(
      expect.stringContaining(
        "/auth/account/confirm/retry?email=jhon%2Bdeplocker%40example.com",
      ),
    );
  });

  it("moves the account to the corrected address", async () => {
    mockSend.mockResolvedValue([
      { message: "Sent", email: "john+deplocker@example.com" },
      null,
    ]);
    renderPage();

    await submitEmailChange();

    expect(
      await screen.findByText("john+deplocker@example.com"),
    ).toBeInTheDocument();
    expect(mockRequest).toHaveBeenCalledWith(
      expect.stringContaining("/auth/account/email"),
      {
        body: {
          identifier: "jhon+deplocker@example.com",
          password: "secret123",
          email: "john+deplocker@example.com",
        },
      },
    );
    expect(
      screen.getByRole("button", { name: "Resend confirmation email" }),
    ).toBeInTheDocument();
  });

  it("keeps the address when the change fails", async () => {
    mockSend.mockResolvedValue([null, "Incorrect credentials were provided."]);
    renderPage();

    await submitEmailChange();

    await waitFor(() =>
      expect(mockToastError).toHaveBeenCalledWith(
        "Incorrect credentials were provided.",
      ),
    );
    expect(screen.getByText("jhon+deplocker@example.com")).toBeInTheDocument();
  });
});
