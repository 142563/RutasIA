import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Outlet, RouterProvider, createBrowserRouter, useLocation } from "react-router";
import { MotionConfig } from "motion/react";
import { Toaster } from "sonner";
import { AppShell } from "@/components/layout/AppShell";
import { ErrorNote, Spinner } from "@/components/ui/misc";
import { Skeleton } from "@/components/ui/motion";
import { setUnauthorizedHandler } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import { UserContext, homeFor, useSession } from "@/lib/auth";
import { replaceSession } from "@/lib/sessionCache";
import type { Role } from "@/lib/types";
import { HomePage } from "@/pages/Home";
import { LoginPage } from "@/pages/Login";
import { OrdersPage } from "@/pages/orders/OrdersPage";
import { PlannerPage } from "@/pages/planner/PlannerPage";
import { RouteDetailPage } from "@/pages/routes/RouteDetailPage";
import { RoutesPage } from "@/pages/routes/RoutesPage";
import { NotFoundPage } from "@/pages/Placeholder";

const AnalysisLayout = lazy(() => import("@/pages/analysis/AnalysisLayout").then((m) => ({ default: m.AnalysisLayout })));
const LabPage = lazy(() => import("@/pages/lab/LabPage").then((m) => ({ default: m.LabPage })));
const TrafficPage = lazy(() => import("@/pages/traffic/TrafficPage").then((m) => ({ default: m.TrafficPage })));
const ReportsPage = lazy(() => import("@/pages/reports/ReportsPage").then((m) => ({ default: m.ReportsPage })));
const SettingsPage = lazy(() => import("@/pages/settings/SettingsPage").then((m) => ({ default: m.SettingsPage })));
const DriverTodayPage = lazy(() => import("@/pages/driver/DriverTodayPage").then((m) => ({ default: m.DriverTodayPage })));
const ChangePasswordPage = lazy(() => import("@/pages/account/ChangePasswordPage").then((m) => ({ default: m.ChangePasswordPage })));
const TrackingPage = lazy(() => import("@/pages/tracking/TrackingPage").then((m) => ({ default: m.TrackingPage })));
const DriverStopPage = lazy(() => import("@/pages/driver/DriverStopPage").then((m) => ({ default: m.DriverStopPage })));
const RoutePrintPage = lazy(() => import("@/pages/routes/RoutePrintPage").then((m) => ({ default: m.RoutePrintPage })));

/** Cada página reserva espacio mientras carga, sin ocultar la navegación. */
function DeferredPage({ children }: { children: ReactNode }) {
  return <Suspense fallback={(
    <div className="min-h-[60vh] space-y-6 p-6 lg:p-8" role="status" aria-label="Cargando pantalla">
      <Skeleton className="h-8 w-48" /><Skeleton className="h-64 w-full rounded-xl" />
    </div>
  )}>{children}</Suspense>;
}

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
});

/** Exige sesión y, opcionalmente, ciertos roles. */
function RequireSession({ roles }: { roles?: Role[] }) {
  const session = useSession();
  const location = useLocation();
  if (session.isPending) return <div className="p-8"><Spinner /></div>;
  if (session.error) return <div className="p-8"><ErrorNote error={session.error} /></div>;
  if (!session.data) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  // Con contraseña temporal solo se puede cambiarla (cualquier rol)
  if (session.data.must_change_password && location.pathname !== "/cambiar-contrasena") {
    return <Navigate to="/cambiar-contrasena" replace />;
  }
  if (roles && !roles.includes(session.data.role)) return <Navigate to={homeFor(session.data.role)} replace />;
  return (
    <UserContext.Provider value={session.data}>
      <Outlet />
    </UserContext.Provider>
  );
}


const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  // Público: el cliente final sigue su pedido con el enlace del correo, sin cuenta
  { path: "/seguimiento/:token", element: <DeferredPage><TrackingPage /></DeferredPage> },
  {
    // Cualquier rol con sesión: cambio obligatorio de la contraseña temporal
    element: <RequireSession />,
    children: [{ path: "/cambiar-contrasena", element: <DeferredPage><ChangePasswordPage /></DeferredPage> }],
  },
  {
    element: <RequireSession roles={["admin", "dispatcher"]} />,
    children: [
      { path: "rutas/:routeId/imprimir", element: <DeferredPage><RoutePrintPage /></DeferredPage> },
      {
        element: <AppShell />,
        children: [
          { index: true, element: <HomePage /> },
          { path: "pedidos", element: <OrdersPage /> },
          { path: "planificar", element: <PlannerPage /> },
          { path: "rutas", element: <RoutesPage /> },
          { path: "rutas/:routeId", element: <RouteDetailPage /> },
          {
            path: "analisis",
            element: <DeferredPage><AnalysisLayout /></DeferredPage>,
            children: [
              { index: true, element: <Navigate to="laboratorio" replace /> },
              { path: "laboratorio", element: <DeferredPage><LabPage /></DeferredPage> },
              { path: "trafico", element: <DeferredPage><TrafficPage /></DeferredPage> },
              { path: "reportes", element: <DeferredPage><ReportsPage /></DeferredPage> },
            ],
          },
          // Direcciones anteriores: Monitoreo vive ahora en Hoy, y lo de la tesis en Análisis
          { path: "monitoreo", element: <Navigate to="/" replace /> },
          { path: "laboratorio", element: <Navigate to="/analisis/laboratorio" replace /> },
          { path: "trafico", element: <Navigate to="/analisis/trafico" replace /> },
          { path: "reportes", element: <Navigate to="/analisis/reportes" replace /> },
          { path: "configuracion/*", element: <DeferredPage><SettingsPage /></DeferredPage> },
          { path: "*", element: <NotFoundPage /> },
        ],
      },
    ],
  },
  {
    element: <RequireSession roles={["driver"]} />,
    children: [
      { path: "/conductor", element: <DeferredPage><DriverTodayPage /></DeferredPage> },
      { path: "/conductor/paradas/:stopId", element: <DeferredPage><DriverStopPage /></DeferredPage> },
    ],
  },
]);

setUnauthorizedHandler(() => {
  replaceSession(queryClient, null);
});

export function App() {
  const theme = useTheme();
  return (
    <QueryClientProvider client={queryClient}>
      {/* "user": con "reducir movimiento" del sistema, Motion salta directo al estado final */}
      <MotionConfig reducedMotion="user">
        <RouterProvider router={router} />
      </MotionConfig>
      <Toaster position="bottom-right" theme={theme.resolved} toastOptions={{ className: "font-sans" }} />
    </QueryClientProvider>
  );
}
