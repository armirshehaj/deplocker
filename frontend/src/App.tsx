import {
  BrowserRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
} from "react-router-dom";
import { SignupForm } from "./components/auth/SignupForm";
import { ActivateAccount } from "./components/auth/ActivateAccount";
import { ConfirmationPending } from "./components/auth/ConfirmationPending";
import Login from "./components/auth/Login";
import Dashboard from "./components/dashboard/Dashboard";
import { AuthContext, AuthProvider } from "./contexts/AuthContext";
import { MenuContext, MenuContextProvider } from "./contexts/MenuContext";
import { useContext } from "react";

export default function App() {
  const isSessionActive = useContext(AuthContext);
  const [currentMenu] = useContext(MenuContext);

  return (
    <BrowserRouter>
      <Routes>
        {/* Public pages */}
        <Route
          path="/login"
          element={
            !isSessionActive ? (
              <Login />
            ) : (
              <Navigate to={`/dashboard/${currentMenu}`} replace />
            )
          }
        />
        <Route path="/register" element={<SignupForm />} />
        <Route path="/account/confirm" element={<ActivateAccount />} />
        <Route path="/account/pending" element={<ConfirmationPending />} />

        {/* Protected pages: a visitor without a session is sent to /login */}
        <Route
          element={
            <AuthProvider>
              <Outlet />
            </AuthProvider>
          }
        >
          <Route
            path="/"
            element={<Navigate to="/dashboard/projects" replace />}
          />
          <Route
            element={
              <MenuContextProvider>
                <Outlet />
              </MenuContextProvider>
            }
          >
            <Route path="/dashboard/:menu" element={<Dashboard />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
