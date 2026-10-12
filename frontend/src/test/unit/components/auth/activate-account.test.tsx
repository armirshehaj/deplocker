import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

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

import { ActivateAccount } from "@/components/auth/ActivateAccount";

function renderPage(query = "?email=john@example.com&token=abc") {
  render(
    <MemoryRouter initialEntries={[`/account/confirm${query}`]}>
      <Routes>
        <Route path="/account/confirm" element={<ActivateAccount />} />
        <Route path="/login" element={<p>Login page</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ActivateAccount", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows the confirmed state and leads to sign in", async () => {
    mockSend.mockResolvedValue([{ message: "Activated" }, null]);
    renderPage();

    expect(
      await screen.findByRole("heading", { name: "Email confirmed" }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(screen.getByText("Login page")).toBeInTheDocument();
  });

  it("offers a new email when the link is invalid or expired", async () => {
    mockSend.mockResolvedValue([null, "Activation token has expired."]);
    renderPage();

    expect(
      await screen.findByRole("heading", { name: "Confirmation failed" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Resend confirmation email" }),
    ).toBeEnabled();
  });

  it("fails without calling the API when the token is missing", async () => {
    renderPage("?email=john@example.com");

    expect(
      await screen.findByRole("heading", { name: "Confirmation failed" }),
    ).toBeInTheDocument();
    expect(mockSend).not.toHaveBeenCalled();
  });

  it("hides the resend button when the link has no email", async () => {
    renderPage("?token=abc");

    await screen.findByRole("heading", { name: "Confirmation failed" });
    expect(
      screen.queryByRole("button", { name: "Resend confirmation email" }),
    ).not.toBeInTheDocument();
  });

  it("sends a new email", async () => {
    mockSend
      .mockResolvedValueOnce([null, "Activation token has expired."])
      .mockResolvedValueOnce([{ message: "Sent" }, null]);
    renderPage();

    fireEvent.click(
      await screen.findByRole("button", { name: "Resend confirmation email" }),
    );

    expect(
      await screen.findByRole("heading", { name: "Check your inbox" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/john@example\.com/)).toBeInTheDocument();
  });

  it("returns to the failed state when the new email cannot be sent", async () => {
    mockSend
      .mockResolvedValueOnce([null, "Activation token has expired."])
      .mockResolvedValueOnce([null, "Service unavailable"]);
    renderPage();

    fireEvent.click(
      await screen.findByRole("button", { name: "Resend confirmation email" }),
    );

    await waitFor(() =>
      expect(mockToastError).toHaveBeenCalledWith("Service unavailable"),
    );
    expect(
      screen.getByRole("button", { name: "Resend confirmation email" }),
    ).toBeEnabled();
  });
});
