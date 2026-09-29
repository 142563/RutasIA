import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navigate, Outlet, RouterProvider, createBrowserRouter, useLocation } from "react-router";
import { Toaster } from "sonner";
import { AppShell } from "@/components/layout/AppShell";
import { ErrorNote, Spinner } from "@/components/ui/misc";
import { setUnauthorizedHandler } from "@/lib/api";
import { UserContext, homeFor, useSession } from "@/lib/auth";
import type { Role } from "@/lib/types";
import { DriverStopPage } from "@/pages/driver/DriverStopPage";
import { DriverTodayPage } from "@/pages/driver/DriverTodayPage";
import { HomePage } from "@/pages/Home";
import { AnalysisLayout } from "@/pages/analysis/AnalysisLayout";
import { LabPage } from "@/pages/lab/LabPage";
import { LoginPage } from "@/pages/Login";
import { OrdersPage } from "@/pages/orders/OrdersPage";
import { PlannerPage } from "@/pages/planner/PlannerPage";
import { ReportsPage } from "@/pages/reports/ReportsPage";
import { RouteDetailPage } from "@/pages/routes/RouteDetailPage";
import { RoutesPage } from "@/pages/routes/RoutesPage";
import { TrafficPage } from "@/pages/traffic/TrafficPage";
import { ComingSoonPage, NotFoundPage } from "@/pages/Placeholder";

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
  if (roles && !roles.includes(session.data.role)) return <Navigate to={homeFor(session.data.role)} replace />;
  return (
    <UserContext.Provider value={session.data}>
      <Outlet />
    </UserContext.Provider>
  );
}

const soon = (title: string, when: string, description: string) => <ComingSoonPage title={title} when={when} description={description} />;

const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    element: <RequireSession roles={["admin", "dispatcher"]} />,
    children: [
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
            element: <AnalysisLayout />,
            children: [
              { index: true, element: <Navigate to="laboratorio" replace /> },
              { path: "laboratorio", element: <LabPage /> },
              { path: "trafico", element: <TrafficPage /> },
              { path: "reportes", element: <ReportsPage /> },
            ],
          },
          // Direcciones anteriores: Monitoreo vive ahora en Hoy, y lo de la tesis en Análisis
          { path: "monitoreo", element: <Navigate to="/" replace /> },
          { path: "laboratorio", element: <Navigate to="/analisis/laboratorio" replace /> },
          { path: "trafico", element: <Navigate to="/analisis/trafico" replace /> },
          { path: "reportes", element: <Navigate to="/analisis/reportes" replace /> },
          { path: "configuracion", element: soon("Configuración", "Semana 3", "Usuarios, bodegas, nodos y calibración.") },
          { path: "*", element: <NotFoundPage /> },
        ],
      },
    ],
  },
  {
    element: <RequireSession roles={["driver"]} />,
    children: [
      { path: "/conductor", element: <DriverTodayPage /> },
      { path: "/conductor/paradas/:stopId", element: <DriverStopPage /> },
    ],
  },
]);

setUnauthorizedHandler(() => {
  queryClient.setQueryData(["session"], null);
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster position="bottom-right" toastOptions={{ className: "font-sans" }} />
    </QueryClientProvider>
  );
}
