import { rootRoute } from "./routes/__root";
import { Route as indexRoute } from "./routes/index";
import { Route as packagesRoute } from "./routes/packages";
import { Route as invoicesRoute } from "./routes/invoices";
import { Route as analyticsRoute } from "./routes/analytics";

export const routeTree = rootRoute.addChildren([
  indexRoute,
  packagesRoute,
  invoicesRoute,
  analyticsRoute,
]);
