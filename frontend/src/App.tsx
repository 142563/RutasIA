import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navigate, Outlet, RouterProvider, createBrowserRouter, useLocation } from "react-router";
import { Toaster } from "sonner";
import { AppShell } from "@/components/layout/AppShell";
import { ErrorNote, Spinner } from "@/components/ui/misc";
import { setUnauthorizedHandler } from "@/lib/api";
import { UserContext, homeFor, useSession } from "@/lib/auth";
import type { Role } from "@/lib/types";
import { HomePage } from "@/pages/Home";
import { LabPage } from "@/pages/lab/LabPage";
import { LoginPage } from "@/pages/Login";
import { OrdersPage } from "@/pages/orders/OrdersPage";
import { PlannerPage } from "@/pages/planner/PlannerPage";
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
          { path: "rutas", element: soon("Rutas", "Semana 3", "Lista y detalle de las rutas asignadas.") },
          { path: "monitoreo", element: soon("Monitoreo", "Semana 3", "Rutas en curso, incidentes y recálculos.") },
          { path: "trafico", element: soon("Tráfico", "Semana 2 · Día 10", "Red nacional coloreada por franja horaria.") },
          { path: "laboratorio", element: <LabPage /> },
          { path: "reportes", element: soon("Reportes", "Semana 3", "Minutos ahorrados, puntualidad y experimentos.") },
          { path: "configuracion", element: soon("Configuración", "Semana 3", "Usuarios, bodegas, nodos y calibración.") },
          { path: "*", element: <NotFoundPage /> },
        ],
      },
    ],
  },
  {
    element: <RequireSession roles={["driver"]} />,
    children: [
      { path: "/conductor", element: soon("Mi ruta de hoy", "Semana 3 · Día 11", "Tus paradas en orden con la hora estimada de llegada.") },
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
