import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

const mockSend = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/http-request", () => ({
  default: class MockHttpRequest {
    send = mockSend;
  },
}));

import { AuthProvider } from "@/contexts/AuthContext";

const protectedPageMounted = vi.fn();

function ProtectedPage() {
  protectedPageMounted();
  return <p>Projects page</p>;
}

function renderProtectedPage() {
  render(
    <MemoryRouter initialEntries={["/dashboard/projects"]}>
      <Routes>
        <Route
          path="/dashboard/projects"
          element={
            <AuthProvider>
              <ProtectedPage />
            </AuthProvider>
          }
        />
        <Route path="/login" element={<p>Login page</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("AuthProvider", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the protected page for an active session", async () => {
    mockSend.mockResolvedValue([{ email: "john@example.com" }, null]);
    renderProtectedPage();

    expect(await screen.findByText("Projects page")).toBeInTheDocument();
  });

  it("sends a visitor without a session to /login without rendering the protected page", async () => {
    mockSend.mockResolvedValue([null, "Unauthorized"]);
    renderProtectedPage();

    expect(await screen.findByText("Login page")).toBeInTheDocument();
    expect(protectedPageMounted).not.toHaveBeenCalled();
  });
});
